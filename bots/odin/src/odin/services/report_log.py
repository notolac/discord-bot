"""Append-only moderation log stored as JSON Lines under ``reports/``.

One file per guild: ``reports/moderation-<guild_id>.jsonl``. Records are small, flat dicts so
they can be grepped or loaded with any tool. This is the interim persistence; a database
replaces it later (see ``tareas/persistence.md``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Action = Literal["warn", "timeout", "purge", "report"]


@dataclass(slots=True)
class ModerationRecord:
    """One moderation event."""

    action: Action
    guild_id: str
    moderator_id: str
    target_id: str | None = None
    reason: str = ""
    channel_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def to_json(self) -> str:
        """Serialize as a single JSON line."""
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> ModerationRecord:
        """Parse one JSON line (unknown keys are ignored)."""
        raw = json.loads(line)
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


class ReportLog:
    """Filesystem-backed moderation log."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, guild_id: str) -> Path:
        """Log file for a guild."""
        safe = "".join(ch for ch in guild_id if ch.isdigit()) or "unknown"
        return self.directory / f"moderation-{safe}.jsonl"

    def append(self, record: ModerationRecord) -> Path:
        """Append ``record`` and return the file written."""
        path = self.path_for(record.guild_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(record.to_json() + "\n")
        return path

    def for_target(
        self, guild_id: str, target_id: str, *, limit: int = 10
    ) -> list[ModerationRecord]:
        """Most recent ``limit`` records about ``target_id`` in ``guild_id`` (newest first)."""
        path = self.path_for(guild_id)
        if not path.is_file():
            return []
        matches: list[ModerationRecord] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = ModerationRecord.from_json(line)
                except json.JSONDecodeError, TypeError:
                    continue
                if record.target_id == target_id:
                    matches.append(record)
        return list(reversed(matches))[:limit]
