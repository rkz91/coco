"""Pydantic models for agent replay endpoints."""

from typing import Optional
from pydantic import BaseModel


class GenerateReplayBody(BaseModel):
    agent_id: str


class ReplayResponse(BaseModel):
    id: str
    agent_id: str
    title: str
    duration: Optional[float] = None
    event_count: Optional[int] = None
    cost: Optional[float] = None
    files_changed: Optional[int] = None
    share_token: Optional[str] = None
    html_path: Optional[str] = None
    replay_schema_version: str = "1"
    created_at: str


class ReplayListResponse(BaseModel):
    items: list[ReplayResponse]
    count: int
