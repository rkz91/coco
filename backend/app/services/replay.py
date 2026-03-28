"""Agent Replay Service — parses stream-json output into a replayable HTML timeline."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import insert, select, delete

from app.db.session import get_db
from app.db.tables import agent_replays, agent_output, agents

log = structlog.get_logger()

REPLAYS_DIR = Path.home() / ".coco" / "replays"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
MAX_EVENTS = 1000
MAX_DIFF_BYTES = 500 * 1024  # 500KB


def _ensure_replays_dir():
    REPLAYS_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReplayService:
    """Parses agent stream-json output and generates self-contained HTML replays."""

    def parse_stream_json(self, raw_output: str) -> list[dict]:
        """Parse stream-json output into structured timeline events.

        Each event: {timestamp, type, content, file_path, diff, cost_delta}
        """
        events: list[dict] = []
        total_diff_bytes = 0

        for line in raw_output.strip().splitlines():
            if len(events) >= MAX_EVENTS:
                break

            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Not JSON — store as raw text event
                events.append({
                    "timestamp": None,
                    "type": "text",
                    "content": line[:2000],
                    "file_path": None,
                    "diff": None,
                    "cost_delta": None,
                })
                continue

            event = self._parse_event(obj, total_diff_bytes)
            if event:
                # Track diff bytes
                if event.get("diff"):
                    total_diff_bytes += len(event["diff"].encode("utf-8"))
                events.append(event)

        return events

    def _parse_event(self, obj: dict, current_diff_bytes: int) -> dict | None:
        """Parse a single stream-json object into a timeline event."""
        event_type = obj.get("type", "")
        timestamp = obj.get("timestamp") or obj.get("ts")

        # Claude Code stream-json event types
        if event_type == "assistant" or event_type == "content_block_delta":
            # Text response from the model
            content = ""
            if "content" in obj:
                if isinstance(obj["content"], list):
                    for block in obj["content"]:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                content += block.get("text", "")
                            elif block.get("type") == "thinking":
                                return {
                                    "timestamp": timestamp,
                                    "type": "thinking",
                                    "content": block.get("thinking", "")[:2000],
                                    "file_path": None,
                                    "diff": None,
                                    "cost_delta": None,
                                }
                elif isinstance(obj["content"], str):
                    content = obj["content"]
            elif "delta" in obj:
                delta = obj["delta"]
                if isinstance(delta, dict):
                    content = delta.get("text", "")
                else:
                    content = str(delta)

            if content:
                return {
                    "timestamp": timestamp,
                    "type": "text",
                    "content": content[:5000],
                    "file_path": None,
                    "diff": None,
                    "cost_delta": None,
                }

        elif event_type == "tool_use" or event_type == "content_block_start":
            tool_name = obj.get("name", "")
            tool_input = obj.get("input", {})
            if not tool_name and "content_block" in obj:
                block = obj["content_block"]
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})

            if not tool_name:
                return None

            file_path = (
                tool_input.get("file_path")
                or tool_input.get("path")
                or tool_input.get("command", "")[:200]
            )

            diff = None
            if tool_name in ("Edit", "Write", "MultiEdit"):
                diff_content = tool_input.get("new_string", "") or tool_input.get("content", "")
                if diff_content:
                    diff_bytes = len(diff_content.encode("utf-8"))
                    if current_diff_bytes + diff_bytes <= MAX_DIFF_BYTES:
                        diff = diff_content[:10000]
                    else:
                        remaining = MAX_DIFF_BYTES - current_diff_bytes
                        if remaining > 0:
                            diff = diff_content[:remaining] + "\n... (diff truncated)"
                        else:
                            diff = f"(diff truncated — {diff_bytes // 1024}KB)"

            # Truncate tool input for display
            input_str = json.dumps(tool_input) if tool_input else ""
            if len(input_str) > 500:
                input_str = input_str[:500] + "..."

            return {
                "timestamp": timestamp,
                "type": "tool_use",
                "content": f"{tool_name}: {input_str}",
                "file_path": str(file_path) if file_path else None,
                "diff": diff,
                "cost_delta": None,
            }

        elif event_type == "tool_result" or event_type == "result":
            content = obj.get("content", "")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                content = "\n".join(parts)
            elif not isinstance(content, str):
                content = str(content)

            return {
                "timestamp": timestamp,
                "type": "tool_result",
                "content": content[:3000],
                "file_path": None,
                "diff": None,
                "cost_delta": None,
            }

        elif event_type in ("thinking", "content_block_thinking"):
            thinking_text = obj.get("thinking", "") or obj.get("text", "")
            return {
                "timestamp": timestamp,
                "type": "thinking",
                "content": thinking_text[:2000],
                "file_path": None,
                "diff": None,
                "cost_delta": None,
            }

        elif event_type == "error":
            return {
                "timestamp": timestamp,
                "type": "error",
                "content": obj.get("error", {}).get("message", str(obj)),
                "file_path": None,
                "diff": None,
                "cost_delta": None,
            }

        elif event_type in ("message_start", "message_stop", "message_delta",
                            "content_block_stop", "ping"):
            # Meta events — extract cost info from message_delta
            if event_type == "message_delta":
                usage = obj.get("usage", {})
                cost = None
                out_tokens = usage.get("output_tokens", 0)
                if out_tokens:
                    # Rough estimate
                    cost = out_tokens * 0.000015
                if cost:
                    return {
                        "timestamp": timestamp,
                        "type": "text",
                        "content": f"(tokens used: {out_tokens})",
                        "file_path": None,
                        "diff": None,
                        "cost_delta": cost,
                    }
            return None

        else:
            # Unknown event type — store with raw data, never drop
            return {
                "timestamp": timestamp,
                "type": "unknown",
                "content": json.dumps(obj)[:2000],
                "file_path": None,
                "diff": None,
                "cost_delta": None,
            }

        return None

    def generate_replay(self, agent_id: str) -> dict:
        """Read agent output, parse into events, generate HTML, create DB record."""
        _ensure_replays_dir()

        with get_db() as conn:
            # Get agent info
            agent_row = conn.execute(
                select(agents.c.id, agents.c.name, agents.c.started_at,
                       agents.c.stopped_at, agents.c.model)
                .where(agents.c.id == agent_id)
            ).fetchone()
            if not agent_row:
                raise ValueError(f"Agent {agent_id} not found")
            agent_data = dict(agent_row._mapping)

            # Get all output chunks
            output_rows = conn.execute(
                select(agent_output.c.chunk, agent_output.c.timestamp)
                .where(agent_output.c.agent_id == agent_id)
                .order_by(agent_output.c.id.asc())
            ).fetchall()

        if not output_rows:
            raise ValueError(f"No output found for agent {agent_id}")

        # Combine output into raw text
        raw_output = "\n".join(row._mapping["chunk"] for row in output_rows)

        # Parse events
        events = self.parse_stream_json(raw_output)

        # Collapse consecutive "read file" events if diff is oversized
        events = self._collapse_read_events(events)

        # Calculate stats
        duration = self._calc_duration(agent_data)
        total_cost = sum(e.get("cost_delta") or 0 for e in events)
        files_changed = len(set(
            e["file_path"] for e in events
            if e.get("file_path") and e["type"] == "tool_use"
            and any(tool in e["content"] for tool in ("Edit:", "Write:", "MultiEdit:"))
        ))

        # Generate HTML
        replay_id = str(uuid.uuid4())
        share_token = uuid.uuid4().hex[:12]
        title = f"Replay: {agent_data['name']}"
        created_at = _now_iso()

        html_content = self._render_html(
            title=title,
            agent_name=agent_data["name"],
            model=agent_data.get("model", "unknown"),
            date=agent_data.get("started_at", created_at),
            duration=duration,
            cost=total_cost,
            files_changed=files_changed,
            events=events,
            share_token=share_token,
        )

        html_path = REPLAYS_DIR / f"{replay_id}.html"
        html_path.write_text(html_content, encoding="utf-8")

        # Save DB record
        record = {
            "id": replay_id,
            "agent_id": agent_id,
            "title": title,
            "duration": duration,
            "event_count": len(events),
            "cost": total_cost,
            "files_changed": files_changed,
            "share_token": share_token,
            "html_path": str(html_path),
            "created_at": created_at,
        }

        with get_db() as conn:
            conn.execute(insert(agent_replays).values(**record))

        log.info("replay_generated", replay_id=replay_id, agent_id=agent_id,
                 event_count=len(events), files_changed=files_changed)
        return record

    def list_replays(self, agent_id: str | None = None) -> list[dict]:
        """List replays, optionally filtered by agent_id."""
        with get_db() as conn:
            q = select(agent_replays).order_by(agent_replays.c.created_at.desc())
            if agent_id:
                q = q.where(agent_replays.c.agent_id == agent_id)
            rows = conn.execute(q).fetchall()
            return [dict(r._mapping) for r in rows]

    def get_replay(self, replay_id: str) -> dict | None:
        """Get a single replay record."""
        with get_db() as conn:
            row = conn.execute(
                select(agent_replays).where(agent_replays.c.id == replay_id)
            ).fetchone()
            if not row:
                return None
            return dict(row._mapping)

    def delete_replay(self, replay_id: str) -> bool:
        """Delete replay record and HTML file."""
        with get_db() as conn:
            row = conn.execute(
                select(agent_replays.c.html_path).where(agent_replays.c.id == replay_id)
            ).fetchone()
            if not row:
                return False

            html_path = row._mapping["html_path"]
            if html_path:
                p = Path(html_path)
                if p.exists():
                    p.unlink()

            conn.execute(delete(agent_replays).where(agent_replays.c.id == replay_id))

        log.info("replay_deleted", replay_id=replay_id)
        return True

    def get_shared_replay(self, share_token: str) -> Path | None:
        """Look up by share_token, return HTML file path."""
        with get_db() as conn:
            row = conn.execute(
                select(agent_replays.c.html_path)
                .where(agent_replays.c.share_token == share_token)
            ).fetchone()
            if not row:
                return None
            html_path = row._mapping["html_path"]
            if not html_path:
                return None
            p = Path(html_path)
            if not p.exists():
                return None
            return p

    def _calc_duration(self, agent_data: dict) -> float | None:
        """Calculate duration in seconds from started_at/stopped_at."""
        started = agent_data.get("started_at")
        stopped = agent_data.get("stopped_at")
        if not started or not stopped:
            return None
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            s = datetime.strptime(started, fmt)
            e = datetime.strptime(stopped, fmt)
            return (e - s).total_seconds()
        except (ValueError, TypeError):
            return None

    def _collapse_read_events(self, events: list[dict]) -> list[dict]:
        """Collapse consecutive 'Read' tool_use events if diff budget is exceeded."""
        result: list[dict] = []
        read_streak: list[dict] = []

        for event in events:
            is_read = (
                event["type"] == "tool_use"
                and event["content"].startswith("Read:")
            )
            if is_read:
                read_streak.append(event)
            else:
                if len(read_streak) > 3:
                    # Collapse
                    files = [e.get("file_path", "?") for e in read_streak]
                    result.append({
                        "timestamp": read_streak[0]["timestamp"],
                        "type": "tool_use",
                        "content": f"Read: read {len(read_streak)} files ({', '.join(f.split('/')[-1] for f in files[:5])}{'...' if len(files) > 5 else ''})",
                        "file_path": None,
                        "diff": None,
                        "cost_delta": None,
                    })
                else:
                    result.extend(read_streak)
                read_streak = []
                result.append(event)

        # Flush remaining
        if len(read_streak) > 3:
            files = [e.get("file_path", "?") for e in read_streak]
            result.append({
                "timestamp": read_streak[0]["timestamp"],
                "type": "tool_use",
                "content": f"Read: read {len(read_streak)} files ({', '.join(f.split('/')[-1] for f in files[:5])}{'...' if len(files) > 5 else ''})",
                "file_path": None,
                "diff": None,
                "cost_delta": None,
            })
        else:
            result.extend(read_streak)

        return result

    def _render_html(self, *, title: str, agent_name: str, model: str,
                     date: str, duration: float | None, cost: float,
                     files_changed: int, events: list[dict],
                     share_token: str) -> str:
        """Render the self-contained HTML replay file."""
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template("replay.html")
        return template.render(
            title=title,
            agent_name=agent_name,
            model=model,
            date=date,
            duration=duration,
            duration_display=self._format_duration(duration),
            cost=cost,
            cost_display=f"${cost:.4f}" if cost else "$0.00",
            files_changed=files_changed,
            events_json=json.dumps(events),
            event_count=len(events),
            share_token=share_token,
        )

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        if not seconds:
            return "—"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m {s}s"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"


replay_service = ReplayService()
