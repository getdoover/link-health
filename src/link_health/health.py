"""Pure link-health logic: message paths, status, battery and link quality.

Kept free of pydoover so the maths can be tested without an application.
"""

import math
from datetime import UTC, datetime
from typing import Any

# status values
STATUS_ONLINE = "online"
STATUS_LATE = "late"
STATUS_OFFLINE = "offline"
STATUS_UNKNOWN = "unknown"

STATUS_LABELS = {
    STATUS_ONLINE: "Online",
    STATUS_LATE: "Late",
    STATUS_OFFLINE: "Offline",
    STATUS_UNKNOWN: "No data yet",
}

STATUS_COLOURS = {
    STATUS_ONLINE: "green",
    STATUS_LATE: "orange",
    STATUS_OFFLINE: "red",
    STATUS_UNKNOWN: "grey",
}

# battery_state values
BATTERY_NORMAL = "normal"
BATTERY_LOW = "low"
BATTERY_HIGH = "high"

BATTERY_COLOURS = {
    BATTERY_NORMAL: "green",
    BATTERY_LOW: "red",
    BATTERY_HIGH: "orange",
}

# link_quality values
LINK_GOOD = "good"
LINK_FAIR = "fair"
LINK_POOR = "poor"

ROLLING_WINDOW_MS = 24 * 60 * 60 * 1000
# Upper bound on stored link samples: a report a minute for a day, plus slack.
MAX_LINK_SAMPLES = 1500


def parse_message_path(value: Any) -> tuple[str, list[str]] | None:
    """Split '$channel.path.to.value' (or '$channel:path.to.value').

    Returns None for an empty or unset path, so an input can be switched off by
    clearing it. Raises ValueError for a path that is set but malformed.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Message path must be a string like '$channel.key'.")

    path = value.strip()
    if not path:
        return None
    if not path.startswith("$"):
        raise ValueError(f"Message path {path!r} must start with '$channel'.")

    body = path[1:]
    if ":" in body:
        channel, raw_path = body.split(":", 1)
    elif "." in body:
        channel, raw_path = body.split(".", 1)
    else:
        raise ValueError(f"Message path {path!r} needs a value path after the channel.")

    channel = channel.strip()
    parts = [part.strip() for part in raw_path.split(".") if part.strip()]
    if not channel or not parts:
        raise ValueError(
            f"Message path {path!r} needs both a channel and a value path."
        )
    return channel, parts


def extract_path_value(data: Any, path: list[str]) -> Any:
    value = data
    for part in path:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if value is None:
            return None
    return value


def to_number(value: Any) -> float | None:
    """A finite float from a number or numeric string, else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def to_route(value: Any) -> str | None:
    """A route/hop description as text. A list reads as hops joined by arrows."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        hops = [
            str(hop).strip() for hop in value if hop is not None and str(hop).strip()
        ]
        return " → ".join(hops) if hops else None
    if isinstance(value, dict):
        return None
    text = str(value).strip()
    return text or None


def to_epoch_ms(value: Any) -> int | None:
    """Epoch milliseconds from epoch seconds, epoch ms, or an ISO 8601 string."""
    if value is None or isinstance(value, bool):
        return None
    number = to_number(value)
    if number is not None:
        if number <= 0:
            return None
        # Anything past 1e11 is too far in the future to be seconds (year 5138),
        # so it is milliseconds.
        return int(number if number > 1e11 else number * 1000)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)
    return None


def compute_status(
    last_heard_ms: int | None,
    now_ms: int,
    interval_min: float,
    late_after: float,
    offline_after: float,
) -> str:
    """Online / late / offline from the age of the last report.

    Late once the report is more than ``late_after`` intervals old, offline once
    it is more than ``offline_after`` intervals old. Never heard is unknown.
    """
    if last_heard_ms is None:
        return STATUS_UNKNOWN
    interval_ms = max(float(interval_min or 0), 0.0) * 60_000
    if interval_ms <= 0:
        return STATUS_ONLINE
    late_after = max(float(late_after or 0), 1.0)
    offline_after = max(float(offline_after or 0), late_after)
    age = now_ms - last_heard_ms
    if age > offline_after * interval_ms:
        return STATUS_OFFLINE
    if age > late_after * interval_ms:
        return STATUS_LATE
    return STATUS_ONLINE


def battery_state(
    voltage: float | None, low: float | None, high: float | None
) -> str | None:
    if voltage is None:
        return None
    if low is not None and voltage < low:
        return BATTERY_LOW
    if high is not None and voltage > high:
        return BATTERY_HIGH
    return BATTERY_NORMAL


def link_quality(
    pct: float | None, warn: float | None, poor: float | None
) -> str | None:
    if pct is None:
        return None
    if poor is not None and pct < poor:
        return LINK_POOR
    if warn is not None and pct < warn:
        return LINK_FAIR
    return LINK_GOOD


def clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


def counter_delta(
    success: float,
    attempts: float,
    previous: list | tuple | None,
    cumulative: bool,
) -> tuple[float, float]:
    """The successes and attempts this report covers.

    Per-report counters are taken as they are. Cumulative counters are
    differenced against the previous report; a counter that went backwards was
    reset (a node reboot), so the new totals are what it counted since.
    """
    if not cumulative or not previous or len(previous) < 2:
        return success, attempts
    prev_success, prev_attempts = previous[0], previous[1]
    if prev_success is None or prev_attempts is None:
        return success, attempts
    if success < prev_success or attempts < prev_attempts:
        return success, attempts
    return success - prev_success, attempts - prev_attempts


def add_link_sample(
    samples: list | None,
    ts_ms: int,
    success: float,
    attempts: float,
    now_ms: int,
) -> list:
    """Append a [ts, success, attempts] sample and trim to the rolling window.

    A percentage reading is stored as (pct, 100), so the window average of
    percentages and the window ratio of counters come out of the same sum.
    """
    kept = [
        s
        for s in (samples or [])
        if isinstance(s, (list, tuple))
        and len(s) >= 3
        and s[0] is not None
        and now_ms - s[0] <= ROLLING_WINDOW_MS
    ]
    kept.append([int(ts_ms), float(success), float(attempts)])
    kept.sort(key=lambda s: s[0])
    return kept[-MAX_LINK_SAMPLES:]


def rolling_link_pct(samples: list | None, now_ms: int) -> float | None:
    success = 0.0
    attempts = 0.0
    for s in samples or []:
        if not isinstance(s, (list, tuple)) or len(s) < 3:
            continue
        if now_ms - s[0] > ROLLING_WINDOW_MS:
            continue
        success += s[1]
        attempts += s[2]
    if attempts <= 0:
        return None
    return clamp_pct(success / attempts * 100.0)
