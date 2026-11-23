"""HTTP schemas for creative-project endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScreenplayProjectCreate(BaseModel):
    title: str = Field(default="", max_length=80)
    idea: str = Field(min_length=1, max_length=4000)
    targetMinutes: int = Field(default=3, ge=1, le=120)
    episodeCount: int = Field(default=1, ge=1, le=200)
    sessionId: str | None = None


class NovelProjectCreate(BaseModel):
    title: str = Field(default="", max_length=80)
    idea: str = Field(min_length=1, max_length=4000)
    targetWords: int = Field(default=3000, ge=500, le=300000)
    chapterCount: int = Field(default=1, ge=1, le=200)
    sessionId: str | None = None
