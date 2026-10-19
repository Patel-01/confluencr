from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionActivity:
    method: str
    path: str
    status_code: int
    created_at: datetime


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    total_api_calls: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    recent_activity: list[SessionActivity]
