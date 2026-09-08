"""Pydantic schemas for learning resources."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResourceBase(BaseModel):
    """Shared fields for creating and returning a learning resource."""

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    source: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ResourceCreate(ResourceBase):
    """Payload used to create a learning resource."""


class ResourceResponse(ResourceBase):
    """Serialized learning resource returned from persistence."""

    model_config = ConfigDict(from_attributes=True)

    id: int
