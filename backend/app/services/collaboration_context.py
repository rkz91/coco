"""
Build collaboration context for agents being spawned as part of a team workflow.

Queries project_context, handoffs, and workflows tables to construct a
structured prompt section that orients the agent on shared project state,
pending handoffs, and workflow progress.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone

from app.db.connections import get_platform_db
from app.config import HUB_DB_PATH, BRAIN_JSON_PATH, CONFIG_JSON_PATH

log = logging.getLogger(__name__)

# Maps agent roles to the section name used when auto-capturing output.
ROLE_SECTION_MAP: dict[str, str] = {
    "product-manager": "brief",
    "project-manager": "plan",
    "developer": "implementation",
    "user-researcher": "research",
}


def _relative_time(iso_str: str | None) -> str:
    """Return a human-friendly relative time like '2h ago'."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return "just now"
        if total_seconds < 3600:
            return f"{total_seconds // 60}m ago"
        if total_seconds < 86400:
            return f"{total_seconds // 3600}h ago"
        return f"{total_seconds // 86400}d ago"
    except Exception:
        return ""


def build_collaboration_prompt(node_id: str, agent_role: str) -> str:
    """Build collaboration context for an agent being spawned.

    Returns a structured prompt section describing team members, shared
    project documents, pending handoffs, and workflow progress.

    Returns an empty string if no collaboration context exists (no
    project_context entries, no handoffs) so solo agents are not confused.
    """
    try:
        with get_platform_db() as db:
            # 1. Project context sections for this node
            context_rows = _query_project_context(db, node_id)

            # 2. Pending handoff targeted at this role
            handoff = _query_pending_handoff(db, node_id, agent_role)

            # 3. Active workflow on this node
            workflow = _query_active_workflow(db, node_id)

            # 4. Team members (agents on this node)
            team = _query_team(db, node_id)

    except Exception as e:
        log.debug("collaboration_context_failed: %s", e)
        return ""

    # If there's no meaningful collaboration data, return empty
    if not context_rows and not handoff:
        return ""

    sections: list[str] = ["== TEAM COLLABORATION CONTEXT =="]

    # Team members
    if team:
        sections.append("")
        sections.append("Your team members:")
        for member in team:
            role_label = member["role"].replace("-", " ").title() if member["role"] else "Custom"
            sections.append(f"- {role_label}: {member['name']}")

    # Shared project document
    if context_rows:
        sections.append("")
        sections.append("Shared Project Document:")
        for row in context_rows:
            author = row["author_role"] or "unknown"
            time_ago = _relative_time(row["created_at"])
            label = row["section"] or "note"
            time_str = f" -- {time_ago}" if time_ago else ""
            sections.append(f"[{label.title()} by {author.replace('-', ' ').title()}{time_str}]")
            # Truncate content to keep prompt under ~3000 tokens
            content = (row["content"] or "")[:800]
            if len(row["content"] or "") > 800:
                content += "\n... (truncated)"
            sections.append(content)
            sections.append("")

    # Current handoff
    if handoff:
        sections.append("Current Handoff to You:")
        sections.append(f"Title: {handoff['title']}")
        sections.append(f"From: {(handoff['from_role'] or 'unknown').replace('-', ' ').title()}")
        if handoff.get("description"):
            sections.append(f"Description: {handoff['description']}")
        sections.append("")

    # Workflow progress
    if workflow:
        try:
            steps = json.loads(workflow["steps"]) if workflow["steps"] else []
            total = len(steps)
            current = (workflow["current_step"] or 0)
            template = workflow.get("template_name") or "Custom"
            objective = workflow.get("objective") or ""
            sections.append(f"Workflow: {template} -- Step {current + 1}/{total}")
            if objective:
                sections.append(f"Objective: {objective}")
            sections.append("")
        except (json.JSONDecodeError, TypeError):
            pass

    # Instructions
    sections.append("INSTRUCTIONS:")
    sections.append("- Read the project context above before starting")
    sections.append("- Your output will be saved and shared with the team")
    sections.append("- Focus on your role's responsibilities")
    sections.append("- Be specific and actionable -- the next team member needs to act on your output")

    return "\n".join(sections)


TOKEN_BUDGET_CHARS = 8000  # ~2000 tokens


def build_coco_context(node_id: str) -> str:
    """Build CoCo brain context for an agent working on a specific node.

    Reads brain.json people and rules, filters to those relevant to the node's
    project, and formats as a context block for the agent's system prompt.
    """
    # 1. Read brain.json
    try:
        brain = json.loads(BRAIN_JSON_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.debug("brain_json_read_failed: %s", e)
        return ""

    people: dict = brain.get("people", {})
    rules: list = brain.get("attention_rules", [])
    if not people and not rules:
        return ""

    # 2. Look up project_id from the node's tree_nodes row
    project_id: str | None = None
    try:
        with get_platform_db() as db:
            row = db.execute(
                "SELECT project_id FROM tree_nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if row:
                project_id = row["project_id"]
    except Exception:
        pass

    # 3. Filter people associated with this project
    filtered_people: list[tuple[str, dict]] = []
    for key, person in people.items():
        person_projects = person.get("projects", [])
        if project_id and project_id in person_projects:
            filtered_people.append((key, person))
        elif not project_id:
            # No project context — include high-priority people
            if person.get("priority") == "high":
                filtered_people.append((key, person))

    # 4. Filter attention rules matching this project
    filtered_rules: list[dict] = []
    for rule in rules:
        target = rule.get("target_project")
        if project_id and target == project_id:
            filtered_rules.append(rule)
        elif not project_id:
            # Include person-level rules (no target_project)
            if not target:
                filtered_rules.append(rule)

    if not filtered_people and not filtered_rules:
        return ""

    # 5. Format output
    parts: list[str] = ["## Team Context (from CoCo Brain)"]

    if filtered_people:
        parts.append("")
        parts.append("### Key People")
        for key, person in filtered_people:
            name = person.get("full_name", key)
            role = person.get("role", "unknown")
            projects = ", ".join(person.get("projects", []))
            topics = ", ".join(person.get("patterns", {}).get("typical_topics", []))
            line = f"- {name} ({role})"
            if topics:
                line += f" -- topics: {topics}"
            parts.append(line)
            if projects:
                parts.append(f"  Projects: {projects}")

    if filtered_rules:
        parts.append("")
        parts.append("### Attention Rules")
        for rule in filtered_rules:
            reason = rule.get("reason", "")
            action = rule.get("action", "unknown")
            parts.append(f"- {reason} (action: {action})")

    result = "\n".join(parts)

    # 6. Respect token budget
    if len(result) > TOKEN_BUDGET_CHARS:
        result = result[:TOKEN_BUDGET_CHARS] + "\n... (truncated)"

    return result


def build_yolo_constraints(project_id: str | None = None) -> str:
    """Build YOLO mode constraints for an agent.

    If YOLO mode is active, returns permission guidelines for autonomous actions.
    If not active, returns empty string.
    """
    try:
        config = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.debug("config_json_read_failed: %s", e)
        return ""

    if config.get("autonomy_mode") != "yolo":
        return ""

    profile = config.get("yolo_profile", "triage")
    profiles_map = config.get("yolo", {}).get("profiles", {})
    profile_info = profiles_map.get(profile, {})
    profile_description = profile_info.get("description", profile)

    # Build safe/escalate lists based on profile
    if profile == "triage":
        safe = "read, search, classify, gather information"
        escalate = "create, update, delete, modify any data"
    elif profile == "pm":
        safe = "read, search, classify, create todos, approve drafts, update brain"
        escalate = "delete, modify agents, create Jira tickets, external comms"
    elif profile == "full":
        safe = "read, search, classify, create, update, approve drafts, update brain, update Confluence"
        escalate = "create Jira tickets, external comms, git push, destructive operations"
    else:
        safe = "read, search"
        escalate = "all write operations"

    parts = [
        f"## Autonomy Mode: YOLO ({profile})",
        "",
        "You have elevated permissions for this session. Guidelines:",
        f"- **Safe actions** (do without asking): {safe}",
        f"- **Escalate** (ask before doing): {escalate}",
        "- **Never** (always blocked): delete production data, push to main without review, modify auth/credentials",
        "",
        f"Profile: {profile_description}",
    ]

    return "\n".join(parts)


def extract_action_items_from_text(text: str) -> list[str]:
    """Extract action items from agent output text using simple heuristics.

    Matches lines starting with TODO:, ACTION:, or - [ ].
    Returns a list of action item descriptions.
    """
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        # Match "TODO: ...", "ACTION: ...", "- [ ] ..."
        for pattern in [
            r"^TODO:\s*(.+)",
            r"^ACTION:\s*(.+)",
            r"^-\s*\[\s*\]\s*(.+)",
        ]:
            m = re.match(pattern, stripped, re.IGNORECASE)
            if m:
                desc = m.group(1).strip()
                if desc and len(desc) > 3:
                    items.append(desc[:200])
                break
    return items


def _create_todos_from_agent_output(
    output_text: str, agent_id: str, node_id: str
) -> int:
    """Scan agent output for action items and create todos in hub.db.

    Returns the number of todos created.
    """
    items = extract_action_items_from_text(output_text)
    if not items:
        return 0

    created = 0
    try:
        conn = sqlite3.connect(str(HUB_DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        # Resolve project_id from node_id via project_content or just use None
        project_id = None
        try:
            row = conn.execute(
                "SELECT project_id FROM project_content WHERE content_id = ? LIMIT 1",
                (node_id,),
            ).fetchone()
            if row:
                project_id = row["project_id"]
        except Exception:
            pass

        for desc in items:
            todo_id = str(uuid.uuid4())
            source_key = f"agent:{agent_id}:{todo_id[:8]}"
            try:
                conn.execute(
                    """INSERT INTO todos (id, title, project_id, priority, owner, status, source_type, source_content_id, created_at)
                       VALUES (?, ?, ?, 'medium', 'rijul', 'open', 'decide', ?, datetime('now'))""",
                    (todo_id, desc, project_id, source_key),
                )
                created += 1
            except Exception as e:
                log.debug("agent_todo_insert_failed: %s", e)

        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("agent_todo_creation_failed: %s", e)

    if created:
        log.info("agent_todos_created", extra={
            "agent_id": agent_id, "node_id": node_id, "count": created
        })
    return created


def auto_capture_output(agent_id: str, agent_role: str, node_id: str | None) -> None:
    """Capture agent's final output as a project_context entry and advance workflow.

    Called after an agent completes. Reads the last 50 output lines, saves
    them to project_context, advances any active workflow, and creates todos
    from action items found in the output.
    """
    if not node_id:
        return

    try:
        with get_platform_db() as db:
            # Read last 50 output lines
            output_rows = db.execute(
                "SELECT chunk FROM agent_output "
                "WHERE agent_id = ? ORDER BY id DESC LIMIT 50",
                (agent_id,),
            ).fetchall()

            if not output_rows:
                return

            # Reverse to chronological order and join
            output_text = "\n".join(r["chunk"] for r in reversed(output_rows))

            # Determine section name
            section_name = ROLE_SECTION_MAP.get(agent_role, "output")

            # Save to project_context
            try:
                db.execute(
                    "INSERT INTO project_context (id, node_id, section, content, author_agent_id, author_role) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), node_id, section_name, output_text, agent_id, agent_role),
                )
                db.commit()
                log.info("auto_captured_output", extra={
                    "agent_id": agent_id, "node_id": node_id, "section": section_name
                })
            except Exception as e:
                log.debug("project_context_insert_failed: %s", e)

            # Create todos from action items in agent output
            try:
                _create_todos_from_agent_output(output_text, agent_id, node_id)
            except Exception as e:
                log.warning("agent_todo_extraction_failed: %s", e)

            # Advance workflow if applicable
            _advance_workflow(db, agent_id, agent_role, node_id)

    except Exception as e:
        log.warning("auto_capture_output_failed: %s", e)


# ---------------------------------------------------------------------------
# Internal query helpers
# ---------------------------------------------------------------------------


def _query_project_context(db, node_id: str) -> list:
    """Fetch project_context sections for a node, ordered by creation time."""
    try:
        rows = db.execute(
            "SELECT section, content, author_role, created_at "
            "FROM project_context "
            "WHERE node_id = ? "
            "ORDER BY created_at ASC",
            (node_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # Table may not exist yet
        return []


def _query_pending_handoff(db, node_id: str, agent_role: str) -> dict | None:
    """Fetch the pending handoff targeted at this role."""
    try:
        row = db.execute(
            "SELECT title, from_role, to_role, description, status "
            "FROM handoffs "
            "WHERE node_id = ? AND to_role = ? AND status = 'pending' "
            "ORDER BY created_at DESC LIMIT 1",
            (node_id, agent_role),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _query_active_workflow(db, node_id: str) -> dict | None:
    """Fetch the active workflow on this node."""
    try:
        row = db.execute(
            "SELECT id, template_name, objective, steps, current_step, status "
            "FROM workflows "
            "WHERE node_id = ? AND status = 'active' "
            "LIMIT 1",
            (node_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _query_team(db, node_id: str) -> list:
    """Fetch team members (agents) assigned to this node."""
    try:
        rows = db.execute(
            "SELECT name, role, status FROM agents "
            "WHERE node_id = ? "
            "ORDER BY created_at ASC",
            (node_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _advance_workflow(db, agent_id: str, agent_role: str, node_id: str) -> None:
    """Check if this agent's completion should advance the workflow."""
    try:
        workflow = db.execute(
            "SELECT * FROM workflows WHERE node_id = ? AND status = 'active' LIMIT 1",
            (node_id,),
        ).fetchone()
    except Exception:
        return

    if not workflow:
        return

    try:
        steps = json.loads(workflow["steps"]) if workflow["steps"] else []
        current = workflow["current_step"] or 0
        current_step = steps[current] if current < len(steps) else None

        if not current_step or current_step.get("role") != agent_role:
            return

        # This agent completed its workflow step -- complete the current handoff
        db.execute(
            "UPDATE handoffs SET status = 'completed', completed_at = datetime('now') "
            "WHERE node_id = ? AND to_role = ? AND status = 'in_progress'",
            (node_id, agent_role),
        )

        # Advance workflow
        next_step = current + 1
        if next_step < len(steps):
            # Create next handoff
            next_role = steps[next_step]["role"]
            action_label = steps[next_step].get("action", "continue").replace("_", " ").title()
            db.execute(
                "INSERT INTO handoffs (id, node_id, workflow_id, from_agent_id, from_role, to_role, title, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
                (
                    str(uuid.uuid4()),
                    node_id,
                    workflow["id"],
                    agent_id,
                    agent_role,
                    next_role,
                    f"{action_label} -- from {agent_role.replace('-', ' ').title()}",
                ),
            )
            db.execute(
                "UPDATE workflows SET current_step = ?, updated_at = datetime('now') WHERE id = ?",
                (next_step, workflow["id"]),
            )
        else:
            # Workflow complete
            db.execute(
                "UPDATE workflows SET status = 'completed', updated_at = datetime('now') WHERE id = ?",
                (workflow["id"],),
            )

        db.commit()
        log.info("workflow_advanced", extra={
            "workflow_id": workflow["id"], "from_step": current, "next_step": next_step if next_step < len(steps) else "complete"
        })
    except (json.JSONDecodeError, IndexError, KeyError, TypeError) as e:
        log.debug("advance_workflow_failed: %s", e)
    except Exception as e:
        log.warning("advance_workflow_error: %s", e)
