"""Response envelope shared by every tool: data plus where it came from and how fresh it is."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Envelope:
    data: Any
    source: str
    as_of: str
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Envelope requires a non-empty source")
        if not self.as_of:
            raise ValueError("Envelope requires an as_of date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "source": self.source,
            "as_of": self.as_of,
            "warnings": list(self.warnings),
        }
