"""Pydantic models for the attention tracking service."""

from pydantic import BaseModel


class ViewEventBody(BaseModel):
    project_slug: str
    source: str = "knowledge"  # "knowledge" | "graph" | "content"
