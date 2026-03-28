"""Pydantic models for the content-to-action pipeline."""

from pydantic import BaseModel


class ProcessContentBody(BaseModel):
    content_id: str
    mode: str = "regex"  # "regex" or "llm"


class ProcessBatchBody(BaseModel):
    limit: int = 20
    mode: str = "regex"


class StagedActionOut(BaseModel):
    id: str
    content_id: str
    action_type: str
    title: str
    description: str | None = None
    assignee: str | None = None
    due_date: str | None = None
    priority: str = "medium"
    source_quote: str | None = None
    confidence: float = 0.0
    extraction_mode: str = "regex"
    status: str = "staged"
    result_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    content_title: str | None = None  # joined from hub_content
