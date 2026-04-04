import base64
from datetime import datetime, timezone
from typing import Optional, Tuple

def iso_utc(dt: datetime) -> str:
    """ Convert datetime to ISO 8601 UTC string with 'Z' suffix. """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

NULL_CURSOR_TIMESTAMP = "null"


def encode_cursor(ts: Optional[datetime], photo_id: str) -> str:
    """ Encode a cursor from timestamp and photo ID. """
    ts_part = NULL_CURSOR_TIMESTAMP if ts is None else iso_utc(ts)
    payload = f"{ts_part}|{photo_id}"
    return base64.urlsafe_b64encode(payload.encode()).decode()

def decode_cursor(cur: str) -> Tuple[Optional[datetime], str]:
    """ Decode a cursor into timestamp and photo ID. """
    raw = base64.urlsafe_b64decode(cur.encode()).decode()
    ts_s, pid = raw.split("|", 1)
    if ts_s == NULL_CURSOR_TIMESTAMP:
        return None, pid
    return datetime.fromisoformat(ts_s.replace("Z", "+00:00")), pid
