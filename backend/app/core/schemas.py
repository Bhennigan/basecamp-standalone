"""Core schema base classes for Base Camp OS."""

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """Base schema class with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        extra="forbid",
    )
