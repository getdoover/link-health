import pytest

from link_health import health

MIN = 60_000


def test_parse_message_path():
    assert health.parse_message_path("$io_state.battery_v") == (
        "io_state",
        ["battery_v"],
    )
    assert health.parse_message_path("$io_state:node.radio.rssi") == (
        "io_state",
        ["node", "radio", "rssi"],
    )
    assert health.parse_message_path("") is None
    assert health.parse_message_path(None) is None
    with pytest.raises(ValueError):
        health.parse_message_path("io_state.battery_v")
    with pytest.raises(ValueError):
        health.parse_message_path("$io_state")


def test_extract_path_value():
    data = {"node": {"hops": ["a", "b"], "v": 12.6}}
    assert health.extract_path_value(data, ["node", "v"]) == 12.6
    assert health.extract_path_value(data, ["node", "hops", "1"]) == "b"
    assert health.extract_path_value(data, ["node", "missing"]) is None
    assert health.extract_path_value(data, ["node", "v", "x"]) is None


def test_to_epoch_ms():
    assert health.to_epoch_ms(1_795_050_000) == 1_795_050_000_000
    assert health.to_epoch_ms(1_795_050_000_000) == 1_795_050_000_000
    assert health.to_epoch_ms("1795050000") == 1_795_050_000_000
    assert health.to_epoch_ms("2026-11-19T00:00:00Z") == 1_795_046_400_000
    assert health.to_epoch_ms("not a time") is None
    assert health.to_epoch_ms(0) is None
    assert health.to_epoch_ms(True) is None


@pytest.mark.parametrize(
    "age_min,expected",
    [(0, "online"), (30, "online"), (31, "late"), (60, "late"), (61, "offline")],
)
def test_compute_status(age_min, expected):
    now = 10_000 * MIN
    assert health.compute_status(now - age_min * MIN, now, 15, 2, 4) == expected


def test_compute_status_never_heard_is_unknown():
    assert health.compute_status(None, 10_000 * MIN, 15, 2, 4) == "unknown"


def test_battery_state_12v_charging_is_normal():
    assert health.battery_state(13.8, 9.5, 14.5) == "normal"
    assert health.battery_state(9.4, 9.5, 14.5) == "low"
    assert health.battery_state(14.6, 9.5, 14.5) == "high"
    assert health.battery_state(None, 9.5, 14.5) is None


def test_link_quality():
    assert health.link_quality(95, 80, 50) == "good"
    assert health.link_quality(70, 80, 50) == "fair"
    assert health.link_quality(40, 80, 50) == "poor"
    assert health.link_quality(None, 80, 50) is None


def test_counter_delta_cumulative_and_reset():
    assert health.counter_delta(110, 120, [100, 105], True) == (10, 15)
    # counter reset (node reboot): new totals are the delta
    assert health.counter_delta(3, 4, [100, 105], True) == (3, 4)
    assert health.counter_delta(110, 120, None, True) == (110, 120)
    assert health.counter_delta(9, 10, [100, 105], False) == (9, 10)


def test_rolling_average_drops_old_samples():
    now = 100 * 24 * 60 * MIN
    samples = health.add_link_sample(
        None, now - 25 * 60 * MIN, 0, 100, now - 25 * 60 * MIN
    )
    samples = health.add_link_sample(samples, now - 60 * MIN, 80, 100, now)
    samples = health.add_link_sample(samples, now, 100, 100, now)
    # the 25 h old sample was trimmed
    assert len(samples) == 2
    assert health.rolling_link_pct(samples, now) == pytest.approx(90.0)
    assert health.rolling_link_pct([], now) is None


def test_to_route():
    assert (
        health.to_route(["Node 4", "Repeater", "Gateway"])
        == "Node 4 → Repeater → Gateway"
    )
    assert health.to_route(" direct ") == "direct"
    assert health.to_route("") is None
    assert health.to_route(None) is None
