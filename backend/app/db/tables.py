"""SQLAlchemy Core table metadata for all platform + hub mirror tables.

This is the single source of truth for the database schema. Used by:
- engine.py / session.py for connections
- Alembic for migrations
- All routers and services for query construction
"""

from sqlalchemy import (
    Column, DateTime, Float, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, ForeignKey, text,
)

metadata = MetaData()

# ---------------------------------------------------------------------------
# Platform tables (read-write)
# ---------------------------------------------------------------------------

nodes = Table(
    "nodes", metadata,
    Column("id", String, primary_key=True),
    Column("parent_id", String, ForeignKey("nodes.id")),
    Column("hub_project_id", String),
    Column("label", String, nullable=False),
    Column("node_type", String, nullable=False, server_default="group"),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("path", String, nullable=False, server_default=""),
    Column("depth", Integer, nullable=False, server_default="0"),
    Column("icon", String),
    Column("color", String),
    Column("folder_path", String),
    Column("github_repo", String),
    Column("jira_key", String),
    Column("confluence_space", String),
    Column("prefix", String),
    Column("metadata_json", String, server_default="{}"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

agents = Table(
    "agents", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("node_id", String),
    Column("project_id", String),
    Column("model", String, nullable=False, server_default="sonnet"),
    Column("role", String, server_default="custom"),
    Column("status", String, nullable=False, server_default="idle"),
    Column("task_description", Text),
    Column("system_prompt", Text),
    Column("working_directory", String),
    Column("pid", Integer),
    Column("started_at", String),
    Column("stopped_at", String),
    Column("last_heartbeat", String),
    Column("exit_code", Integer),
    Column("config", String, server_default="{}"),
    Column("reports_to", String),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

agent_output = Table(
    "agent_output", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("agent_id", String, ForeignKey("agents.id"), nullable=False),
    Column("stream", String, nullable=False),
    Column("chunk", String, nullable=False),
    Column("timestamp", String, nullable=False, server_default=text("(datetime('now'))")),
)

cost_ledger = Table(
    "cost_ledger", metadata,
    Column("id", String, primary_key=True),
    Column("agent_id", String, ForeignKey("agents.id")),
    Column("node_id", String),
    Column("project_id", String),
    Column("model", String, nullable=False),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("cost_usd", Float, nullable=False, server_default="0.0"),
    Column("source", String, nullable=False, server_default="agent"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

budgets = Table(
    "budgets", metadata,
    Column("project_id", String, primary_key=True),
    Column("node_id", String),
    Column("daily_cap_usd", Float),
    Column("weekly_cap_usd", Float),
    Column("monthly_cap_usd", Float),
    Column("alert_threshold_pct", Float, server_default="0.8"),
)

governance_log = Table(
    "governance_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("action", String, nullable=False),
    Column("item_type", String, nullable=False),
    Column("item_id", String),
    Column("autonomy_mode", String),
    Column("confidence", Float),
    Column("decision_by", String, server_default="user"),
    Column("notes", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

tasks = Table(
    "tasks", metadata,
    Column("id", String, primary_key=True),
    Column("title", String, nullable=False),
    Column("description", Text),
    Column("agent_id", String, ForeignKey("agents.id")),
    Column("node_id", String),
    Column("project_id", String),
    Column("status", String, nullable=False, server_default="open"),
    Column("priority", String, server_default="medium"),
    Column("checked_out_by", String),
    Column("checked_out_at", String),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

task_documents = Table(
    "task_documents", metadata,
    Column("id", String, primary_key=True),
    Column("task_id", String, ForeignKey("tasks.id"), nullable=False),
    Column("key", String, nullable=False),
    Column("body", Text, nullable=False, server_default=""),
    Column("revision", Integer, nullable=False, server_default="1"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
    UniqueConstraint("task_id", "key"),
)

chat_sessions = Table(
    "chat_sessions", metadata,
    Column("id", String, primary_key=True),
    Column("title", String),
    Column("model", String, server_default="sonnet"),
    Column("message_count", Integer, server_default="0"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

chat_messages = Table(
    "chat_messages", metadata,
    Column("id", String, primary_key=True),
    Column("session_id", String, ForeignKey("chat_sessions.id")),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("model", String),
    Column("tokens_used", Integer),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

preferences = Table(
    "preferences", metadata,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
)

comments = Table(
    "comments", metadata,
    Column("id", String, primary_key=True),
    Column("entity_type", String, nullable=False),
    Column("entity_id", String, nullable=False),
    Column("parent_id", String),
    Column("author", String, nullable=False, server_default="user"),
    Column("body", Text, nullable=False),
    Column("mentions", String, server_default="[]"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

project_context = Table(
    "project_context", metadata,
    Column("id", String, primary_key=True),
    Column("node_id", String, nullable=False),
    Column("section", String, nullable=False),
    Column("title", String),
    Column("content", Text, nullable=False),
    Column("author_agent_id", String),
    Column("author_role", String),
    Column("version", Integer, server_default="1"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

handoffs = Table(
    "handoffs", metadata,
    Column("id", String, primary_key=True),
    Column("node_id", String, nullable=False),
    Column("workflow_id", String),
    Column("from_agent_id", String, nullable=False),
    Column("from_role", String),
    Column("to_role", String, nullable=False),
    Column("title", String, nullable=False),
    Column("description", Text),
    Column("status", String, nullable=False, server_default="pending"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("accepted_at", String),
    Column("completed_at", String),
)

workflows = Table(
    "workflows", metadata,
    Column("id", String, primary_key=True),
    Column("node_id", String, nullable=False),
    Column("template_name", String, nullable=False),
    Column("objective", Text),
    Column("steps", Text, nullable=False),
    Column("current_step", Integer, server_default="0"),
    Column("status", String, nullable=False, server_default="active"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

workflow_templates = Table(
    "workflow_templates", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", Text),
    Column("steps", Text, nullable=False),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

templates = Table(
    "templates", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", Text),
    Column("template_json", Text, nullable=False),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

goals = Table(
    "goals", metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String),
    Column("node_id", String),
    Column("parent_id", String, ForeignKey("goals.id")),
    Column("title", String, nullable=False),
    Column("description", Text),
    Column("status", String, nullable=False, server_default="active"),
    Column("progress_pct", Integer, server_default="0"),
    Column("owner", String),
    Column("target_date", String),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

draft_decisions = Table(
    "draft_decisions", metadata,
    Column("id", String, primary_key=True),
    Column("hub_draft_id", String, nullable=False, unique=True),
    Column("status", String, nullable=False),
    Column("decided_by", String, server_default="user"),
    Column("decided_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

content_classifications = Table(
    "content_classifications", metadata,
    Column("id", String, primary_key=True),
    Column("hub_content_id", String, nullable=False, unique=True),
    Column("project_id", String),
    Column("classified_project_id", String),
    Column("suggested_project_id", String),
    Column("action", String, server_default="classify"),
    Column("confidence", Float, server_default="0.0"),
    Column("reasoning", Text),
    Column("auto_classified", Integer, server_default="0"),
    Column("status", String, server_default="pending"),
    Column("classified_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("created_at", String, server_default=text("(datetime('now'))")),
)

project_overrides = Table(
    "project_overrides", metadata,
    Column("id", String, primary_key=True),
    Column("hub_project_id", String, nullable=False, unique=True),
    Column("name", String),
    Column("description", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

id_sequences = Table(
    "id_sequences", metadata,
    Column("node_id", String, ForeignKey("nodes.id"), primary_key=True),
    Column("next_seq", Integer, nullable=False, server_default="1"),
)

entity_identifiers = Table(
    "entity_identifiers", metadata,
    Column("entity_id", String, primary_key=True),
    Column("entity_type", String, nullable=False),
    Column("node_id", String, nullable=False),
    Column("sequence_num", Integer, nullable=False),
    Column("display_id", String, nullable=False),
    UniqueConstraint("node_id", "sequence_num"),
)

todo_dependencies = Table(
    "todo_dependencies", metadata,
    Column("id", String, primary_key=True),
    Column("todo_id", String, nullable=False),
    Column("depends_on", String, nullable=False),
    Column("dep_type", String, nullable=False, server_default="blocked_by"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    UniqueConstraint("todo_id", "depends_on"),
)

todo_overrides = Table(
    "todo_overrides", metadata,
    Column("hub_todo_id", String, primary_key=True),
    Column("title", String),
    Column("status", String),
    Column("priority", String),
    Column("owner", String),
    Column("due_date", String),
    Column("project_id", String),
    Column("node_id", String),
    Column("source_type", String),
    Column("source_content_id", String),
    Column("is_platform_native", Integer, server_default="0"),
    Column("created_at", String, server_default=text("(datetime('now'))")),
    Column("updated_at", String, server_default=text("(datetime('now'))")),
)

analysis_jobs = Table(
    "analysis_jobs", metadata,
    Column("id", String, primary_key=True),
    Column("node_id", String, ForeignKey("nodes.id"), nullable=False),
    Column("folder_path", String, nullable=False),
    Column("analysis_type", String, server_default="full"),
    Column("status", String, server_default="pending"),
    Column("file_count", Integer, server_default="0"),
    Column("agent_ids", String, server_default="[]"),
    Column("results_summary", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("completed_at", String),
)

task_board = Table(
    "task_board", metadata,
    Column("id", String, primary_key=True),
    Column("node_id", String, nullable=False),
    Column("name", String, nullable=False, server_default="Shared Board"),
    Column("agent_ids", String, nullable=False, server_default="[]"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

events = Table(
    "events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_type", String, nullable=False),
    Column("data_json", Text, nullable=False),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

triggers = Table(
    "triggers", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("trigger_type", String, nullable=False),
    Column("enabled", Integer, nullable=False, server_default="1"),
    Column("config", String, nullable=False, server_default="{}"),
    Column("action_type", String, nullable=False),
    Column("action_config", String, nullable=False, server_default="{}"),
    Column("node_id", String),
    Column("last_fired_at", String),
    Column("fire_count", Integer, server_default="0"),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

trigger_log = Table(
    "trigger_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trigger_id", String, ForeignKey("triggers.id"), nullable=False),
    Column("fired_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("status", String, nullable=False),
    Column("result", Text),
    Column("error", Text),
)

self_improve_cycles = Table(
    "self_improve_cycles", metadata,
    Column("id", String, primary_key=True),
    Column("status", String, nullable=False, server_default="idle"),
    Column("budget_usd", Float, nullable=False, server_default="5.0"),
    Column("spent_usd", Float, nullable=False, server_default="0.0"),
    Column("max_improvements", Integer, nullable=False, server_default="5"),
    Column("focus_areas", Text),
    Column("started_at", String),
    Column("completed_at", String),
    Column("error", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

self_improve_improvements = Table(
    "self_improve_improvements", metadata,
    Column("id", String, primary_key=True),
    Column("cycle_id", String, ForeignKey("self_improve_cycles.id"), nullable=False),
    Column("title", String, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("priority", Integer, nullable=False, server_default="0"),
    Column("category", String, nullable=False, server_default="refactor"),
    Column("status", String, nullable=False, server_default="proposed"),
    Column("worktree_path", String),
    Column("branch_name", String),
    Column("diff_summary", Text),
    Column("diff_stat", Text),
    Column("test_results", Text),
    Column("review_notes", Text),
    Column("security_scan", Text),
    Column("pr_description", Text),
    Column("changelog_entry", Text),
    Column("agent_id", String),
    Column("human_comment", Text),
    Column("reject_reason", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

self_improve_agents = Table(
    "self_improve_agents", metadata,
    Column("id", String, primary_key=True),
    Column("cycle_id", String, ForeignKey("self_improve_cycles.id"), nullable=False),
    Column("improvement_id", String, ForeignKey("self_improve_improvements.id")),
    Column("agent_id", String, nullable=False),
    Column("role", String, nullable=False),
    Column("status", String, nullable=False, server_default="pending"),
    Column("started_at", String),
    Column("completed_at", String),
    Column("output_summary", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

inbox_read_state = Table(
    "inbox_read_state", metadata,
    Column("item_key", String, primary_key=True),
    Column("read_state", String, nullable=False, server_default="unread"),
    Column("updated_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

jarvis_sessions = Table(
    "jarvis_sessions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("command", String, nullable=False),
    Column("response_summary", Text),
    Column("cards_json", Text),
    Column("created_at", String, nullable=False, server_default=text("(datetime('now'))")),
)

verification_gates = Table(
    "verification_gates", metadata,
    Column("id", String, primary_key=True),
    Column("gate", String, nullable=False),
    Column("verdict", String, nullable=False),
    Column("checks_json", Text),
    Column("summary", Text),
    Column("node_id", String),
    Column("entity_type", String),
    Column("entity_id", String),
    Column("run_at", String, nullable=False),
    Column("duration_ms", Integer, server_default="0"),
)

agent_roles = Table(
    "agent_roles", metadata,
    Column("slug", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("default_system_prompt", Text),
    Column("default_model", String, server_default="sonnet"),
    Column("sort_order", Integer, server_default="0"),
)

# ---------------------------------------------------------------------------
# Hub mirror tables (populated by hub_sync service from hub.db)
# ---------------------------------------------------------------------------

hub_todos = Table(
    "hub_todos", metadata,
    Column("id", String, primary_key=True),
    Column("title", Text),
    Column("description", Text),
    Column("project_id", String),
    Column("owner", String),
    Column("due_date", String),
    Column("priority", String),
    Column("status", String),
    Column("source_type", String),
    Column("source_content_id", String),
    Column("jira_key", String),
    Column("created_at", String),
    Column("completed_at", String),
    Column("tags", String),
)

hub_content = Table(
    "hub_content", metadata,
    Column("id", String, primary_key=True),
    Column("title", Text),
    Column("body", Text),
    Column("summary", Text),
    Column("source", String),
    Column("source_id", String),
    Column("sender", String),
    Column("triage", String),
    Column("priority", String),
    Column("has_action_item", Integer),
    Column("action_owner", String),
    Column("action_due_date", String),
    Column("ingested_at", String),
    Column("created_at", String),
)

hub_projects = Table(
    "hub_projects", metadata,
    Column("id", String, primary_key=True),
    Column("name", String),
    Column("jira_key", String),
    Column("confluence_space", String),
    Column("active", Integer, server_default="1"),
    Column("created_at", String),
)

hub_sync_state = Table(
    "hub_sync_state", metadata,
    Column("source", String, primary_key=True),
    Column("last_sync", String),
    Column("item_count", Integer),
    Column("status", String),
    Column("message", String),
)

hub_project_content = Table(
    "hub_project_content", metadata,
    Column("project_id", String, nullable=False),
    Column("content_id", String, nullable=False),
    UniqueConstraint("project_id", "content_id"),
)

hub_api_costs = Table(
    "hub_api_costs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("feature", String),
    Column("model", String),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("cost_usd", Float),
    Column("created_at", String),
)

hub_drafts = Table(
    "hub_drafts", metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String),
    Column("template", String),
    Column("section", String),
    Column("content", Text),
    Column("source_content_id", String),
    Column("status", String),
    Column("created_at", String),
)

# ---------------------------------------------------------------------------
# Hub sync watermark (tracks sync progress)
# ---------------------------------------------------------------------------

hub_sync_watermark = Table(
    "hub_sync_watermark", metadata,
    Column("table_name", String, primary_key=True),
    Column("last_synced_at", String),
    Column("last_rowid", Integer),
    Column("row_count", Integer),
)
