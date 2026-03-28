from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.tables import (
    hub_projects, hub_content, hub_project_content, nodes,
)

router = APIRouter(tags=["Teams"])


def _node_map() -> dict:
    """Return a dict mapping hub_project_id -> node row for all linked nodes."""
    children = nodes.alias("c")
    child_count_sq = (
        select(func.count())
        .select_from(children)
        .where(children.c.parent_id == nodes.c.id)
        .correlate(nodes)
        .scalar_subquery()
        .label("child_count")
    )
    with get_db() as conn:
        rows = conn.execute(
            select(
                nodes.c.id.label("node_id"),
                nodes.c.hub_project_id,
                nodes.c.label,
                nodes.c.parent_id,
                nodes.c.node_type,
                nodes.c.path,
                nodes.c.depth,
                nodes.c.icon,
                nodes.c.color,
                child_count_sq,
            ).where(nodes.c.hub_project_id.isnot(None))
        ).fetchall()
        return {r.hub_project_id: dict(r._mapping) for r in rows}


@router.get("/api/teams")
def list_teams():
    try:
        with get_db() as conn:
            item_count_sq = (
                select(func.count())
                .select_from(hub_content)
                .join(hub_project_content, hub_content.c.id == hub_project_content.c.content_id)
                .where(hub_project_content.c.project_id == hub_projects.c.id)
                .correlate(hub_projects)
                .scalar_subquery()
                .label("item_count")
            )
            rows = conn.execute(
                select(
                    hub_projects.c.id,
                    hub_projects.c.name,
                    hub_projects.c.jira_key,
                    hub_projects.c.confluence_space,
                    hub_projects.c.active,
                    item_count_sq,
                ).order_by(hub_projects.c.name)
            ).fetchall()

        node_map = _node_map()
        teams = []
        for r in rows:
            team = dict(r._mapping)
            team["team_id"] = team.pop("id")
            team["team_name"] = team.pop("name")
            node = node_map.get(team["team_id"])
            team["node_id"] = node["node_id"] if node else None
            team["child_count"] = node["child_count"] if node else 0
            teams.append(team)
        return teams
    except Exception:
        return []


@router.get("/api/teams/{team_id}")
def get_team(team_id: str):
    with get_db() as conn:
        row = conn.execute(
            select(
                hub_projects.c.id,
                hub_projects.c.name,
                hub_projects.c.jira_key,
                hub_projects.c.confluence_space,
                hub_projects.c.active,
            ).where(hub_projects.c.id == team_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Team not found")

        team = dict(row._mapping)
        team["team_id"] = team.pop("id")
        team["team_name"] = team.pop("name")

        counts = conn.execute(
            select(hub_content.c.source, func.count().label("count"))
            .join(hub_project_content, hub_content.c.id == hub_project_content.c.content_id)
            .where(hub_project_content.c.project_id == team_id)
            .group_by(hub_content.c.source)
        ).fetchall()
        team["content_counts"] = {r.source: r.count for r in counts}

        # Enrich with node metadata
        children = nodes.alias("c")
        child_count_sq = (
            select(func.count())
            .select_from(children)
            .where(children.c.parent_id == nodes.c.id)
            .correlate(nodes)
            .scalar_subquery()
            .label("child_count")
        )
        node = conn.execute(
            select(
                nodes.c.id.label("node_id"),
                nodes.c.parent_id,
                nodes.c.label,
                nodes.c.node_type,
                nodes.c.path,
                nodes.c.depth,
                nodes.c.icon,
                nodes.c.color,
                child_count_sq,
            ).where(nodes.c.hub_project_id == team_id)
        ).fetchone()
        if node:
            team["node_id"] = node.node_id
            team["child_count"] = node.child_count
            team["node_path"] = node.path
            team["node_depth"] = node.depth
            team["node_icon"] = node.icon
            team["node_color"] = node.color
        else:
            team["node_id"] = None
            team["child_count"] = 0

    return team
