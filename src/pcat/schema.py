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

GUARD_NAME_KINDS = ("must_catch", "must_call", "must_not_call", "must_not_import", "must_raise")
GUARD_VALUE_KINDS = ("min_value", "max_value")
GUARD_ANY_KINDS = ("must_catch", "must_call", "must_raise")
# A dotted name (`requests.Timeout`, `eval`) or a method on any value (`.raise_for_status`).
GUARD_NAME_PATTERN = r"^\.?[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"


class Guard(BaseModel):
    """A reviewed property the linter checks on code derived from the pattern (v4).

    names: exceptions (must_catch, must_raise), calls (must_call, must_not_call)
    or modules (must_not_import). target/value: for min_value/max_value, a
    module constant or a parameter (its default) of `function`, by its name in
    the pattern. target/values (v4.1 must_include): a collection constant or
    default that must still contain every value. `function` defaults to the
    entry point. match (v5.1): "any" makes a must_catch/must_call/must_raise guard
    hold when one of its names is present (house exceptions for sibling flows).
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["must_catch", "must_call", "must_not_call", "min_value", "max_value",
                  "must_not_import", "must_raise", "must_include"]
    names: list[str] = Field(default_factory=list)
    target: Optional[str] = None
    value: Optional[Union[StrictInt, float]] = None
    values: list[Union[StrictInt, float, str]] = Field(default_factory=list)
    function: Optional[str] = None
    reason: Optional[str] = Field(default=None, min_length=1)
    # v5.1: for must_catch/must_call/must_raise, "any" = one of `names` is enough (default: each)
    match: Literal["all", "any"] = "all"

    @model_validator(mode="after")
    def _shape(self) -> "Guard":
        if self.kind in GUARD_NAME_KINDS:
            if not self.names:
                raise ValueError(f"{self.kind} guard needs names")
            if self.target is not None or self.value is not None or self.values:
                raise ValueError(f"{self.kind} guard takes names, not target/value")
            for name in self.names:
                if not re.fullmatch(GUARD_NAME_PATTERN, name):
                    raise ValueError(f"{name!r} is not a dotted name or .method")
                if self.kind == "must_not_import" and name.startswith("."):
                    raise ValueError(f"{name!r}: modules cannot start with '.'")
            if len(set(self.names)) != len(self.names):
                raise ValueError("guard names must be unique")
            if self.match == "any" and self.kind not in GUARD_ANY_KINDS:
                raise ValueError(f"match: any applies to {', '.join(GUARD_ANY_KINDS)} only")
            if self.match == "any" and len(self.names) < 2:
                raise ValueError("match: any needs at least two names")
            return self
        if self.match != "all":
            raise ValueError(f"match applies to {', '.join(GUARD_ANY_KINDS)} only")
        if self.kind == "must_include":
            if self.names or self.value is not None:
                raise ValueError("must_include guard takes target and values, not names/value")
            if not self.target or not self.target.isidentifier() or not self.values:
                raise ValueError("must_include guard needs target (a name) and values")
            if len(set(map(repr, self.values))) != len(self.values):
                raise ValueError("must_include values must be unique")
        else:
            if self.names or self.values:
                raise ValueError(f"{self.kind} guard takes target and value, not names")
            if not self.target or not self.target.isidentifier() or self.value is None:
                raise ValueError(f"{self.kind} guard needs target (a name) and value")
        return self


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
    # v5.1: distribution -> import name where they differ (overrides requirements.KNOWN_IMPORT_NAMES)
    import_names: dict[str, str] = Field(default_factory=dict)
    # v3 search/serving metadata. Optional; never part of the fingerprint.
    exports: list[str] = Field(default_factory=list)  # public functions besides entry_point
    keywords: list[str] = Field(default_factory=list)  # 5-15 search terms when given
    use_when: Optional[str] = Field(default=None, min_length=1)  # situations the pattern is for
    usage: Optional[str] = Field(default=None, min_length=1)  # short calling example for agents
    # v4 linter guards: reviewed properties checked on derived code. Never part of the fingerprint.
    guards: list[Guard] = Field(default_factory=list)

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

    @field_validator("import_names")
    @classmethod
    def _import_names_are_modules(cls, value: dict[str, str]) -> dict[str, str]:
        for dist, module in value.items():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", dist):
                raise ValueError(f"{dist!r} is not a distribution name")
            if not all(part.isidentifier() for part in module.split(".")):
                raise ValueError(f"{module!r} is not a module name")
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
        for guard in self.guards:
            if guard.function is not None and guard.function not in (self.entry_point, *self.exports):
                raise ValueError(
                    f"guard function {guard.function!r} must be the entry_point or an export"
                )
        return self

    @property
    def key(self) -> str:
        """Unique key of this pattern version, e.g. "search.foo@v1"."""
        return f"{self.id}@v{self.version}"

    @property
    def pattern_id(self) -> str:
        """The id without its category segment (folder name stem)."""
        return self.id.split(".", 1)[1]
