import base64
from datetime import datetime, timezone
from typing import Tuple

def iso_utc(dt: datetime) -> str:
    """ Convert datetime to ISO 8601 UTC string with 'Z' suffix. """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def encode_cursor(ts: datetime, photo_id: str) -> str:
    """ Encode a cursor from timestamp and photo ID. """
    payload = f"{iso_utc(ts)}|{photo_id}"
    return base64.urlsafe_b64encode(payload.encode()).decode()

def decode_cursor(cur: str) -> Tuple[datetime, str]:
    """ Decode a cursor into timestamp and photo ID. """
    raw = base64.urlsafe_b64decode(cur.encode()).decode()
    ts_s, pid = raw.split("|", 1)
    return datetime.fromisoformat(ts_s.replace("Z", "+00:00")), pid
