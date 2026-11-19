from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from link_health import application as app_module
from link_health.app_config import CounterType
from link_health.application import LinkHealthApplication

MIN = 60_000
NOW = 1_795_050_000_000


class Value:
    def __init__(self, value):
        self.value = value


class FakeConfig:
    def __init__(self, **overrides):
        values = dict(
            battery_voltage_path="$io_state.battery_v",
            link_success_path="$io_state.link_success_pct",
            success_count_path="",
            attempt_count_path="",
            counter_type=CounterType.CUMULATIVE,
            retries_path="$io_state.retries",
            rssi_path="$io_state.rssi",
            snr_path="",
            route_path="$io_state.route",
            last_heard_path="$io_state.last_heard",
            expected_interval_min=15.0,
            late_after_intervals=2.0,
            offline_after_intervals=4.0,
            battery_low_v=9.5,
            battery_high_v=14.5,
            link_warn_pct=80.0,
            link_poor_pct=50.0,
        )
        values.update(overrides)
        for key, value in values.items():
            setattr(self, key, Value(value))


class FakeTag:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    async def set(self, value, log=False):
        self.value = value


class FakeTags:
    def __init__(self):
        for name in [
            "last_heard_ts",
            "battery_v",
            "battery_state",
            "battery_colour",
            "link_success_pct",
            "link_success_24h_pct",
            "link_quality",
            "retries",
            "rssi",
            "snr",
            "route",
            "link_samples",
            "last_counters",
            "warning_message",
        ]:
            setattr(self, name, FakeTag())
        self.status = FakeTag("unknown")
        self.status_label = FakeTag("No data yet")
        self.status_colour = FakeTag("grey")
        self.warning_hidden = FakeTag(True)


class FakeNotification:
    def __init__(self, sent, name):
        self.sent = sent
        self.name = name

    async def send(self, message=None, **kwargs):
        self.sent.append((self.name, message))


class FakeNotifications:
    def __init__(self):
        self.sent = []
        for name in ("offline", "battery_low", "battery_high", "poor_link"):
            setattr(self, name, FakeNotification(self.sent, name))


def make_app(**config):
    app = object.__new__(LinkHealthApplication)
    app.config = FakeConfig(**config)
    app.tags = FakeTags()
    app.notifications = FakeNotifications()
    return app


def message(data, channel="io_state", at_ms=NOW):
    ts = datetime.fromtimestamp(at_ms / 1000, tz=UTC)
    return SimpleNamespace(
        channel=SimpleNamespace(name=channel),
        message=SimpleNamespace(data=data, timestamp=ts),
    )


@pytest.fixture
def clock(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(app_module, "now_ms", lambda: state["now"])
    return state


@pytest.mark.asyncio
async def test_no_data_is_unknown_and_silent(clock):
    app = make_app()
    await app.setup()
    await app.on_deployment(None)
    clock["now"] += 24 * 60 * MIN
    await app.on_schedule(None)

    assert app.tags.status.value == "unknown"
    assert app.tags.status_label.value == "No data yet"
    assert app.tags.warning_hidden.value is True
    assert app.notifications.sent == []


@pytest.mark.asyncio
async def test_message_without_configured_values_is_ignored(clock):
    app = make_app()
    await app.setup()
    await app.on_message_create(message({"something_else": 1}))
    await app.on_message_create(message({"battery_v": 12.5}, channel="other"))
    assert app.tags.last_heard_ts.value is None
    assert app.tags.status.value == "unknown"


@pytest.mark.asyncio
async def test_report_updates_tags(clock):
    app = make_app()
    await app.setup()
    await app.on_message_create(
        message(
            {
                "battery_v": "13.8",
                "link_success_pct": 92,
                "retries": 3,
                "rssi": -97,
                "route": ["Node 7", "Repeater", "Gateway"],
            }
        )
    )
    t = app.tags
    assert t.status.value == "online"
    assert t.last_heard_ts.value == NOW
    assert t.battery_v.value == 13.8
    assert t.battery_state.value == "normal"
    assert t.link_success_pct.value == 92
    assert t.link_success_24h_pct.value == 92
    assert t.link_quality.value == "good"
    assert t.retries.value == 3
    assert t.rssi.value == -97
    assert t.route.value == "Node 7 → Repeater → Gateway"
    assert t.warning_hidden.value is True
    assert app.notifications.sent == []


@pytest.mark.asyncio
async def test_last_heard_from_payload(clock):
    app = make_app()
    await app.setup()
    heard_s = (NOW - 40 * MIN) // 1000
    await app.on_message_create(message({"battery_v": 12.4, "last_heard": heard_s}))
    assert app.tags.last_heard_ts.value == heard_s * 1000
    assert app.tags.status.value == "late"
    assert app.tags.warning_hidden.value is False


@pytest.mark.asyncio
async def test_goes_late_then_offline_once(clock):
    app = make_app()
    await app.setup()
    await app.on_message_create(message({"battery_v": 12.4}))

    clock["now"] = NOW + 45 * MIN
    await app.on_schedule(None)
    assert app.tags.status.value == "late"
    assert app.notifications.sent == []

    clock["now"] = NOW + 65 * MIN
    await app.on_schedule(None)
    assert app.tags.status.value == "offline"
    assert [n for n, _ in app.notifications.sent] == ["offline"]

    clock["now"] = NOW + 120 * MIN
    await app.on_schedule(None)
    assert [n for n, _ in app.notifications.sent] == ["offline"]

    # back online
    await app.on_message_create(message({"battery_v": 12.4}, at_ms=clock["now"]))
    assert app.tags.status.value == "online"


@pytest.mark.asyncio
async def test_battery_notifications_on_transition(clock):
    app = make_app()
    await app.setup()
    await app.on_message_create(message({"battery_v": 13.9}))
    await app.on_message_create(message({"battery_v": 9.1}, at_ms=NOW + MIN))
    await app.on_message_create(message({"battery_v": 9.0}, at_ms=NOW + 2 * MIN))
    await app.on_message_create(message({"battery_v": 15.0}, at_ms=NOW + 3 * MIN))
    assert [n for n, _ in app.notifications.sent] == ["battery_low", "battery_high"]
    assert app.tags.battery_state.value == "high"


@pytest.mark.asyncio
async def test_poor_link_notification(clock):
    app = make_app()
    await app.setup()
    await app.on_message_create(message({"link_success_pct": 90}))
    await app.on_message_create(message({"link_success_pct": 40}, at_ms=NOW + MIN))
    await app.on_message_create(message({"link_success_pct": 30}, at_ms=NOW + 2 * MIN))
    assert [n for n, _ in app.notifications.sent] == ["poor_link"]
    assert app.tags.link_success_24h_pct.value == pytest.approx(53.3, abs=0.1)
    assert "Poor link" in app.tags.warning_message.value


@pytest.mark.asyncio
async def test_cumulative_counters(clock):
    app = make_app(
        link_success_path="",
        success_count_path="$io_state.ok",
        attempt_count_path="$io_state.tries",
    )
    await app.setup()
    await app.on_message_create(message({"ok": 90, "tries": 100}))
    assert app.tags.link_success_pct.value == 90
    await app.on_message_create(message({"ok": 95, "tries": 110}, at_ms=NOW + MIN))
    assert app.tags.link_success_pct.value == 50
    # 95 of 110 over the window
    assert app.tags.link_success_24h_pct.value == pytest.approx(86.4, abs=0.1)


@pytest.mark.asyncio
async def test_older_report_does_not_regress(clock):
    app = make_app()
    await app.setup()
    await app.on_message_create(message({"battery_v": 12.5}))
    await app.on_message_create(
        message({"battery_v": 8.0, "last_heard": (NOW - 10 * MIN) // 1000})
    )
    assert app.tags.battery_v.value == 12.5
    assert app.notifications.sent == []


@pytest.mark.asyncio
async def test_no_paths_configured_does_not_raise(clock):
    app = make_app(
        battery_voltage_path="",
        link_success_path="",
        retries_path="",
        rssi_path="",
        route_path="",
        last_heard_path="bad path",
    )
    await app.setup()
    await app.on_message_create(message({"battery_v": 12}))
    await app.on_schedule(None)
    assert app.tags.status.value == "unknown"
