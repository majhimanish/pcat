"""Pydantic models for `pattern.yaml` (spec section 7)."""

from __future__ import annotations

import keyword
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

ID_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
# A reference is an id, optionally pinned to a version: "search.foo" or "search.foo@v2".
REF_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+(@v[1-9][0-9]*)?$"
FINGERPRINT_PATTERN = r"^[0-9a-f]{64}$"

BehaviorValue = Union[StrictBool, StrictInt, float, str, None]


class PatternMeta(BaseModel):
    """Metadata of one pattern version. Unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    version: StrictInt = Field(ge=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    category: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    variant_of: Optional[str] = Field(default=None, pattern=ID_PATTERN)
    behavior: dict[str, BehaviorValue]
    entry_point: str
    owner: str = Field(min_length=1)
    status: Literal["active", "deprecated"]
    replaced_by: Optional[str] = Field(default=None, pattern=REF_PATTERN)
    keep_annotations: StrictBool = True
    fingerprint: Optional[str] = Field(default=None, pattern=FINGERPRINT_PATTERN)

    @field_validator("entry_point")
    @classmethod
    def _entry_point_is_identifier(cls, value: str) -> str:
        if not value.isidentifier() or keyword.iskeyword(value):
            raise ValueError(f"{value!r} is not a valid Python function name")
        return value

    @model_validator(mode="after")
    def _cross_field_rules(self) -> "PatternMeta":
        if self.id.split(".")[0] != self.category:
            raise ValueError(
                f"category {self.category!r} must equal the first segment of id {self.id!r}"
            )
        if self.status == "deprecated" and not self.replaced_by:
            raise ValueError("deprecated patterns must set replaced_by")
        if self.status == "active" and self.replaced_by:
            raise ValueError("active patterns must not set replaced_by")
        return self

    @property
    def key(self) -> str:
        """Unique key of this pattern version, e.g. "search.foo@v1"."""
        return f"{self.id}@v{self.version}"

    @property
    def pattern_id(self) -> str:
        """The id without its category segment (folder name stem)."""
        return self.id.split(".", 1)[1]
