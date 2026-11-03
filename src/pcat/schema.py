"""Pydantic models for `pattern.yaml` (spec section 7)."""

from __future__ import annotations

import keyword
import re
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

ID_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
# A reference is an id, optionally pinned to a version: "search.foo" or "search.foo@v2".
REF_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+(@v[1-9][0-9]*)?$"
FINGERPRINT_PATTERN = r"^[0-9a-f]{64}$"
# A pip requirement without markers or URLs: name, optional extras, version specifiers.
REQUIREMENT_PATTERN = (
    r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9._,-]+\])?"
    r"(\s*(==|!=|>=|<=|~=|>|<)\s*[0-9A-Za-z.*+!_-]+(\s*,\s*(==|!=|>=|<=|~=|>|<)\s*[0-9A-Za-z.*+!_-]+)*)?"
)

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
    # Third-party distributions the pattern imports, as pip requirement strings
    # (e.g. "pyjwt>=2.8,<3"). Metadata only: never part of the fingerprint.
    requires: list[str] = Field(default_factory=list)
    # v3 search/serving metadata. Optional; never part of the fingerprint.
    exports: list[str] = Field(default_factory=list)  # public functions besides entry_point
    keywords: list[str] = Field(default_factory=list)  # 5-15 search terms when given
    use_when: Optional[str] = Field(default=None, min_length=1)  # situations the pattern is for
    usage: Optional[str] = Field(default=None, min_length=1)  # short calling example for agents

    @field_validator("entry_point")
    @classmethod
    def _entry_point_is_identifier(cls, value: str) -> str:
        if not value.isidentifier() or keyword.iskeyword(value):
            raise ValueError(f"{value!r} is not a valid Python function name")
        return value

    @field_validator("requires")
    @classmethod
    def _requires_are_requirements(cls, value: list[str]) -> list[str]:
        for item in value:
            if not re.fullmatch(REQUIREMENT_PATTERN, item):
                raise ValueError(f"{item!r} is not a requirement like 'name>=1.0,<2'")
        names = [re.match(r"[A-Za-z0-9._-]+", item).group(0).lower() for item in value]
        if len(names) != len(set(names)):
            raise ValueError("requires lists a distribution more than once")
        return value

    @field_validator("exports")
    @classmethod
    def _exports_are_identifiers(cls, value: list[str]) -> list[str]:
        for name in value:
            if not name.isidentifier() or keyword.iskeyword(name):
                raise ValueError(f"{name!r} is not a valid Python function name")
        if len(value) != len(set(value)):
            raise ValueError("exports lists a function more than once")
        return value

    @field_validator("keywords")
    @classmethod
    def _keywords_count(cls, value: list[str]) -> list[str]:
        if value and not 5 <= len(value) <= 15:
            raise ValueError(f"give 5-15 keywords, got {len(value)}")
        if any(not k.strip() for k in value):
            raise ValueError("keywords must not be empty")
        if len({k.strip().lower() for k in value}) != len(value):
            raise ValueError("keywords must be unique")
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
        if self.entry_point in self.exports:
            raise ValueError("exports must not repeat the entry_point")
        return self

    @property
    def key(self) -> str:
        """Unique key of this pattern version, e.g. "search.foo@v1"."""
        return f"{self.id}@v{self.version}"

    @property
    def pattern_id(self) -> str:
        """The id without its category segment (folder name stem)."""
        return self.id.split(".", 1)[1]
