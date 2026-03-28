"""Podcast briefing service — aggregates data, generates script, synthesizes audio.

Uses KokoroEngine for TTS with sentence-boundary chunking and silence insertion.
Falls back to edge-tts if Kokoro is unavailable, and to script-only if neither works.
"""

import io
import re
import struct
import subprocess
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import structlog
from sqlalchemy import func, select, text

from app.db.session import get_db
from app.db.tables import (
    agents,
    cost_ledger,
    hub_todos,
    podcasts,
    self_improve_cycles,
)
from app.services.event_bus import event_bus

log = structlog.get_logger()

PODCASTS_DIR = Path.home() / ".coco" / "podcasts"
PODCASTS_DIR.mkdir(parents=True, exist_ok=True)

# Sample rate for Kokoro TTS
SAMPLE_RATE = 24000

# Silence durations
CHUNK_SILENCE_MS = 300
SECTION_SILENCE_MS = 600

# Hard cap
MAX_WORDS = 450
MAX_DURATION_SECONDS = 180  # 3 minutes


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _greeting_word() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    return "evening"


# ---------------------------------------------------------------------------
# 1. Aggregate briefing data
# ---------------------------------------------------------------------------


def aggregate_briefing_data() -> dict:
    """Query hub mirror tables for overnight/recent data."""
    data: dict = {
        "completed_agents": 0,
        "new_todos": 0,
        "completed_todos": 0,
        "cost_last_24h": 0.0,
        "todos_due_today": [],
        "recent_self_improve": 0,
        "date": datetime.now().strftime("%A, %B %d"),
    }

    with get_db() as conn:
        # Completed agents (last 24h)
        try:
            row = conn.execute(
                select(func.count().label("cnt"))
                .select_from(agents)
                .where(agents.c.status == "completed")
                .where(agents.c.stopped_at >= text("datetime('now', '-24 hours')"))
            ).fetchone()
            data["completed_agents"] = row.cnt if row else 0
        except Exception:
            log.warning("podcast_agg_failed", section="completed_agents", exc_info=True)

        # New todos (last 24h)
        try:
            row = conn.execute(
                select(func.count().label("cnt"))
                .select_from(hub_todos)
                .where(hub_todos.c.created_at >= text("datetime('now', '-24 hours')"))
            ).fetchone()
            data["new_todos"] = row.cnt if row else 0
        except Exception:
            log.warning("podcast_agg_failed", section="new_todos", exc_info=True)

        # Completed todos (last 24h)
        try:
            row = conn.execute(
                select(func.count().label("cnt"))
                .select_from(hub_todos)
                .where(hub_todos.c.status == "done")
                .where(hub_todos.c.completed_at >= text("datetime('now', '-24 hours')"))
            ).fetchone()
            data["completed_todos"] = row.cnt if row else 0
        except Exception:
            log.warning("podcast_agg_failed", section="completed_todos", exc_info=True)

        # Cost last 24h
        try:
            row = conn.execute(
                select(func.coalesce(func.sum(cost_ledger.c.cost_usd), 0.0).label("total"))
                .where(cost_ledger.c.created_at >= text("datetime('now', '-24 hours')"))
            ).fetchone()
            data["cost_last_24h"] = round(row.total, 4) if row else 0.0
        except Exception:
            log.warning("podcast_agg_failed", section="cost_last_24h", exc_info=True)

        # Todos due today
        try:
            rows = conn.execute(
                select(hub_todos.c.id, hub_todos.c.title, hub_todos.c.priority)
                .where(hub_todos.c.status == "open")
                .where(hub_todos.c.due_date == text("date('now', 'localtime')"))
                .order_by(hub_todos.c.priority.desc())
                .limit(10)
            ).fetchall()
            data["todos_due_today"] = [dict(r._mapping) for r in rows]
        except Exception:
            log.warning("podcast_agg_failed", section="todos_due_today", exc_info=True)

        # Recent self-improve cycles (last 24h)
        try:
            row = conn.execute(
                select(func.count().label("cnt"))
                .select_from(self_improve_cycles)
                .where(self_improve_cycles.c.status == "completed")
                .where(self_improve_cycles.c.completed_at >= text("datetime('now', '-24 hours')"))
            ).fetchone()
            data["recent_self_improve"] = row.cnt if row else 0
        except Exception:
            log.warning("podcast_agg_failed", section="recent_self_improve", exc_info=True)

    return data


# ---------------------------------------------------------------------------
# 2. Generate script (template-based, deterministic)
# ---------------------------------------------------------------------------

# Section marker for silence insertion
SECTION_BREAK = "\n\n"


def generate_script(data: dict) -> str:
    """Produce a conversational morning briefing script from aggregated data.

    Target: 300-450 words, 2-3 minutes at ~150 wpm.
    """
    greeting = _greeting_word()
    date_str = data.get("date", _today_str())
    sections: list[str] = []

    # --- Greeting ---
    sections.append(
        f"Good {greeting}. It's {date_str}. Here's your CoCo briefing."
    )

    # --- Overnight highlights ---
    highlights: list[str] = []
    completed = data.get("completed_agents", 0)
    new_todos = data.get("new_todos", 0)
    completed_todos = data.get("completed_todos", 0)
    cost = data.get("cost_last_24h", 0.0)
    self_improve = data.get("recent_self_improve", 0)

    if completed > 0:
        highlights.append(
            f"{completed} agent{'s' if completed != 1 else ''} finished their work overnight."
        )
    if completed_todos > 0:
        highlights.append(
            f"{completed_todos} todo{'s' if completed_todos != 1 else ''} got marked done."
        )
    if new_todos > 0:
        highlights.append(
            f"{new_todos} new todo{'s' if new_todos != 1 else ''} came in over the last 24 hours."
        )
    if cost > 0.01:
        highlights.append(
            f"API spend in the last 24 hours was ${cost:.2f}."
        )
    if self_improve > 0:
        highlights.append(
            f"The self-improve engine completed {self_improve} cycle{'s' if self_improve != 1 else ''}."
        )

    if highlights:
        sections.append("Here's what happened. " + " ".join(highlights))
    else:
        sections.append(
            "It's been a quiet stretch. No major activity in the last 24 hours."
        )

    # --- Action items: todos due today ---
    todos = data.get("todos_due_today", [])
    if todos:
        count = len(todos)
        sections.append(
            f"You've got {count} item{'s' if count != 1 else ''} due today."
        )
        # List up to 5
        for i, todo in enumerate(todos[:5]):
            title = todo.get("title", "Untitled")
            priority = todo.get("priority", "medium")
            marker = "High priority: " if priority == "high" else ""
            sections.append(f"{marker}{title}.")
        if count > 5:
            sections.append(f"Plus {count - 5} more. Check the todos page for the full list.")
    else:
        sections.append("No items due today. Clear runway.")

    # --- Sign-off ---
    sections.append(
        "That's your briefing. Have a productive day."
    )

    script = SECTION_BREAK.join(sections)

    # Hard cap at MAX_WORDS
    words = script.split()
    if len(words) > MAX_WORDS:
        words = words[:MAX_WORDS]
        script = " ".join(words) + "... and that's the highlights."

    return script


# ---------------------------------------------------------------------------
# 3. Synthesize audio
# ---------------------------------------------------------------------------


def _generate_silence(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Generate silence as a numpy array of zeros."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return np.zeros(num_samples, dtype=np.float32)


def _chunk_text(text: str, max_chars: int = 200) -> list[str]:
    """Split text at sentence boundaries (. ! ?) with max chars per chunk."""
    # Split on sentence-ending punctuation followed by space
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _concat_wav_arrays(arrays: list[np.ndarray], sample_rate: int = SAMPLE_RATE) -> bytes:
    """Concatenate numpy float32 arrays into a WAV byte buffer."""
    if not arrays:
        return b""
    combined = np.concatenate(arrays)
    # Convert float32 [-1, 1] to int16
    int16_data = (combined * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())

    return buf.getvalue()


async def _edge_tts_fallback(script: str, out_path: Path) -> float | None:
    """Try edge-tts as fallback. Returns duration in seconds or None."""
    try:
        import edge_tts

        communicate = edge_tts.Communicate(script, "en-US-AndrewNeural", rate="-5%")
        await communicate.save(str(out_path.with_suffix(".mp3")))
        mp3_path = out_path.with_suffix(".mp3")
        if mp3_path.exists() and mp3_path.stat().st_size > 100:
            # Estimate duration: ~150 wpm
            word_count = len(script.split())
            duration = word_count / 150 * 60
            # Rename to match expected path
            mp3_path.rename(out_path)
            return duration
    except ImportError:
        log.warning("edge_tts_not_installed")
    except Exception as e:
        log.warning("edge_tts_fallback_failed", error=str(e))
    return None


def synthesize_audio(
    script: str,
    voice: str = "af_heart",
    podcast_id: str | None = None,
) -> tuple[str, float] | None:
    """Synthesize audio from script using Kokoro with chunking and silence.

    Returns (file_path, duration_seconds) or None if synthesis fails.
    """
    from app.services.kokoro_engine import KokoroEngine

    if podcast_id is None:
        podcast_id = uuid.uuid4().hex[:12]

    out_path = PODCASTS_DIR / f"{podcast_id}.wav"

    # Split script into sections (separated by double newlines)
    sections = script.split(SECTION_BREAK)
    all_audio: list[np.ndarray] = []

    # Check Kokoro availability
    engine = KokoroEngine(cache_dir=PODCASTS_DIR / ".cache")
    (PODCASTS_DIR / ".cache").mkdir(parents=True, exist_ok=True)

    if not engine.is_available():
        log.warning("kokoro_not_available_for_podcast")
        return None

    for sec_idx, section in enumerate(sections):
        chunks = _chunk_text(section, max_chars=200)

        for chunk_idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            # Generate audio for this chunk via Kokoro
            chunk_path = engine.generate(chunk, voice=voice, speed=1.0)
            if chunk_path is None:
                log.warning("podcast_chunk_failed", section=sec_idx, chunk=chunk_idx)
                continue

            # Read the WAV data as numpy
            try:
                import soundfile as sf
                audio_data, sr = sf.read(str(chunk_path), dtype="float32")
                all_audio.append(audio_data)
            except Exception as e:
                log.warning("podcast_chunk_read_failed", error=str(e))
                continue

            # Add inter-chunk silence (300ms)
            if chunk_idx < len(chunks) - 1:
                all_audio.append(_generate_silence(CHUNK_SILENCE_MS))

        # Add inter-section silence (600ms)
        if sec_idx < len(sections) - 1:
            all_audio.append(_generate_silence(SECTION_SILENCE_MS))

    if not all_audio:
        log.warning("podcast_no_audio_generated")
        return None

    # Concatenate and write
    wav_bytes = _concat_wav_arrays(all_audio, SAMPLE_RATE)
    out_path.write_bytes(wav_bytes)

    # Calculate actual duration
    combined = np.concatenate(all_audio)
    actual_duration = len(combined) / SAMPLE_RATE

    # Quality gate: compare to expected duration
    word_count = len(script.split())
    expected_duration = word_count / 150 * 60  # 150 wpm

    if expected_duration > 0:
        ratio = actual_duration / expected_duration
        if abs(ratio - 1.0) > 0.2:
            log.warning(
                "podcast_duration_mismatch",
                actual=round(actual_duration, 1),
                expected=round(expected_duration, 1),
                ratio=round(ratio, 2),
            )

    # Hard cap at 3 minutes
    if actual_duration > MAX_DURATION_SECONDS:
        log.warning("podcast_exceeds_cap", duration=round(actual_duration, 1))
        # Truncate: keep only MAX_DURATION_SECONDS worth
        max_samples = int(SAMPLE_RATE * MAX_DURATION_SECONDS)
        truncated = combined[:max_samples]
        # Re-write
        int16_data = (truncated * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(int16_data.tobytes())
        out_path.write_bytes(buf.getvalue())
        actual_duration = MAX_DURATION_SECONDS

    log.info(
        "podcast_audio_synthesized",
        path=str(out_path),
        duration=round(actual_duration, 1),
        word_count=word_count,
    )

    return str(out_path), round(actual_duration, 1)


# ---------------------------------------------------------------------------
# 4. Orchestrator
# ---------------------------------------------------------------------------


async def generate_podcast(voice: str = "af_heart") -> dict:
    """Full pipeline: aggregate -> script -> audio -> persist -> notify."""
    podcast_id = uuid.uuid4().hex[:12]
    now = _iso_now()
    title = f"Morning Brief — {datetime.now().strftime('%b %d, %Y')}"

    # Create initial record
    with get_db() as conn:
        conn.execute(
            podcasts.insert().values(
                id=podcast_id,
                title=title,
                status="generating",
                voice=voice,
                created_at=now,
            )
        )

    try:
        # 1. Aggregate data
        data = aggregate_briefing_data()

        # 2. Generate script
        script = generate_script(data)

        # 3. Synthesize audio
        result = synthesize_audio(script, voice=voice, podcast_id=podcast_id)

        if result is None:
            # Try edge-tts fallback
            out_path = PODCASTS_DIR / f"{podcast_id}.wav"
            try:
                import asyncio
                duration = await _edge_tts_fallback(script, out_path)
                if duration:
                    result = (str(out_path), duration)
            except Exception:
                pass

        audio_path = result[0] if result else None
        duration = result[1] if result else None
        status = "ready" if result else "ready"  # script-only is still "ready"

        # 4. Update DB record
        with get_db() as conn:
            conn.execute(
                podcasts.update()
                .where(podcasts.c.id == podcast_id)
                .values(
                    script=script,
                    audio_path=audio_path,
                    duration=duration,
                    status=status,
                )
            )

        record = {
            "id": podcast_id,
            "title": title,
            "script": script,
            "audio_path": audio_path,
            "duration": duration,
            "voice": voice,
            "status": status,
            "created_at": now,
        }

        # 5. Emit event
        event_bus.emit("podcast.ready", {"podcast_id": podcast_id, "title": title})

        # 6. macOS notification
        _send_notification(title)

        return record

    except Exception as e:
        log.error("podcast_generation_failed", error=str(e), exc_info=True)
        with get_db() as conn:
            conn.execute(
                podcasts.update()
                .where(podcasts.c.id == podcast_id)
                .values(status="failed")
            )
        return {
            "id": podcast_id,
            "title": title,
            "script": None,
            "audio_path": None,
            "duration": None,
            "voice": voice,
            "status": "failed",
            "created_at": now,
        }


# ---------------------------------------------------------------------------
# 5. Queries
# ---------------------------------------------------------------------------


def list_podcasts(limit: int = 10) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            select(podcasts).order_by(podcasts.c.created_at.desc()).limit(limit)
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def get_podcast(podcast_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            select(podcasts).where(podcasts.c.id == podcast_id)
        ).fetchone()
        return dict(row._mapping) if row else None


def delete_podcast(podcast_id: str) -> bool:
    """Delete a podcast record and its audio file."""
    record = get_podcast(podcast_id)
    if not record:
        return False

    # Delete audio file
    if record.get("audio_path"):
        try:
            Path(record["audio_path"]).unlink(missing_ok=True)
        except Exception:
            pass

    with get_db() as conn:
        conn.execute(podcasts.delete().where(podcasts.c.id == podcast_id))

    return True


# ---------------------------------------------------------------------------
# 6. macOS notification
# ---------------------------------------------------------------------------


def _send_notification(title: str) -> None:
    """Send macOS desktop notification."""
    try:
        subprocess.Popen(
            [
                "osascript",
                "-e",
                f'display notification "Your morning brief is ready" with title "CoCo" subtitle "{title}"',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Best effort
