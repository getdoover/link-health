import logging
import time
from typing import Any

from pydoover.models import DeploymentEvent, MessageCreateEvent, ScheduleEvent
from pydoover.processor import Application

from . import health
from .app_config import CounterType, LinkHealthConfig
from .app_notifications import LinkHealthNotifications
from .app_tags import WARNING_DEFAULT_MESSAGE, LinkHealthTags
from .app_ui import LinkHealthUI

log = logging.getLogger(__name__)

# A reported last-heard time this far ahead of the message is a clock problem
# on the node, not a report from the future: the arrival time is used instead.
FUTURE_TOLERANCE_MS = 5 * 60 * 1000

INPUTS = (
    ("battery", "battery_voltage_path"),
    ("link_pct", "link_success_path"),
    ("success_count", "success_count_path"),
    ("attempt_count", "attempt_count_path"),
    ("retries", "retries_path"),
    ("rssi", "rssi_path"),
    ("snr", "snr_path"),
    ("route", "route_path"),
    ("last_heard", "last_heard_path"),
)


def now_ms() -> int:
    return int(time.time() * 1000)


def format_age(age_ms: float) -> str:
    minutes = max(age_ms, 0) / 60_000
    if minutes < 90:
        return f"{minutes:.0f} min"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} days"


class LinkHealthApplication(Application):
    config: LinkHealthConfig
    tags: LinkHealthTags
    ui: LinkHealthUI
    notifications: LinkHealthNotifications

    config_cls = LinkHealthConfig
    tags_cls = LinkHealthTags
    ui_cls = LinkHealthUI
    notifications_cls = LinkHealthNotifications

    async def setup(self):
        self._inputs: dict[str, tuple[str, list[str]]] = {}
        for key, field in INPUTS:
            element = getattr(self.config, field, None)
            value = None if element is None else element.value
            try:
                parsed = health.parse_message_path(value)
            except (TypeError, ValueError) as e:
                log.warning("Ignoring %s: %s", field, e)
                continue
            if parsed is not None:
                self._inputs[key] = parsed
        if not self._inputs:
            log.warning("No input message paths are configured; nothing to report.")

    # -- events -----------------------------------------------------------------

    async def on_deployment(self, event: DeploymentEvent):
        await self.refresh_status(now_ms())

    async def on_schedule(self, event: ScheduleEvent):
        await self.refresh_status(now_ms())

    async def on_message_create(self, event: MessageCreateEvent):
        data = event.message.data or {}
        values = self._read_inputs(event.channel.name, data)
        if not values:
            return

        now = now_ms()
        arrival = self._arrival_ms(event, now)
        heard = health.to_epoch_ms(values.get("last_heard"))
        if heard is None or heard > arrival + FUTURE_TOLERANCE_MS:
            heard = arrival

        previous = _int_or_none(self.tags.last_heard_ts.get())
        if previous is not None and heard < previous:
            log.info("Ignoring a report from %s, older than the last one.", heard)
            return

        await self.tags.last_heard_ts.set(heard)
        await self._update_power(values)
        await self._update_link(values, heard, now)
        await self._update_signal(values)
        await self.refresh_status(now)

    # -- inputs -----------------------------------------------------------------

    def _read_inputs(self, channel: str, data: Any) -> dict[str, Any]:
        values = {}
        for key, (input_channel, path) in self._inputs.items():
            if input_channel != channel:
                continue
            value = health.extract_path_value(data, path)
            if value is not None:
                values[key] = value
        return values

    @staticmethod
    def _arrival_ms(event, fallback: int) -> int:
        try:
            ts = event.message.timestamp
            return int(ts.timestamp() * 1000)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return fallback

    # -- power ------------------------------------------------------------------

    async def _update_power(self, values: dict[str, Any]):
        if "battery" not in values:
            return
        voltage = health.to_number(values["battery"])
        if voltage is None:
            log.warning("Battery voltage %r is not numeric.", values["battery"])
            return

        low = health.to_number(self.config.battery_low_v.value)
        high = health.to_number(self.config.battery_high_v.value)
        state = health.battery_state(voltage, low, high)
        previous = self.tags.battery_state.get()

        await self.tags.battery_v.set(voltage)
        await self.tags.battery_state.set(state)
        await self.tags.battery_colour.set(health.BATTERY_COLOURS.get(state))

        if state != previous:
            if state == health.BATTERY_LOW:
                await self.notifications.battery_low.send(
                    f"Battery is low at {voltage:.2f} V (limit {low:g} V)."
                )
            elif state == health.BATTERY_HIGH:
                await self.notifications.battery_high.send(
                    f"Battery is high at {voltage:.2f} V (limit {high:g} V)."
                )

    # -- link -------------------------------------------------------------------

    async def _update_link(self, values: dict[str, Any], heard: int, now: int):
        reported = health.to_number(values.get("link_pct"))
        if reported is not None:
            reported = health.clamp_pct(reported)

        samples = self.tags.link_samples.get()
        sampled = False

        success = health.to_number(values.get("success_count"))
        attempts = health.to_number(values.get("attempt_count"))
        counter_pct = None
        if (
            success is not None
            and attempts is not None
            and success >= 0
            and attempts >= 0
        ):
            cumulative = self.config.counter_type.value != CounterType.PER_REPORT
            d_success, d_attempts = health.counter_delta(
                success, attempts, self.tags.last_counters.get(), cumulative
            )
            await self.tags.last_counters.set([success, attempts])
            if d_attempts > 0:
                d_success = min(d_success, d_attempts)
                counter_pct = health.clamp_pct(d_success / d_attempts * 100.0)
                samples = health.add_link_sample(
                    samples, heard, d_success, d_attempts, now
                )
                sampled = True

        pct = reported if reported is not None else counter_pct
        if pct is None:
            return

        if not sampled:
            samples = health.add_link_sample(samples, heard, pct, 100.0, now)

        await self.tags.link_samples.set(samples)
        await self.tags.link_success_pct.set(round(pct, 1))
        average = health.rolling_link_pct(samples, now)
        await self.tags.link_success_24h_pct.set(
            None if average is None else round(average, 1)
        )

        warn = health.to_number(self.config.link_warn_pct.value)
        poor = health.to_number(self.config.link_poor_pct.value)
        quality = health.link_quality(pct, warn, poor)
        previous = self.tags.link_quality.get()
        await self.tags.link_quality.set(quality)
        if quality == health.LINK_POOR and previous != health.LINK_POOR:
            await self.notifications.poor_link.send(
                f"Link success is {pct:.0f} % (poor below {poor:g} %)."
            )

    # -- signal and route -------------------------------------------------------

    async def _update_signal(self, values: dict[str, Any]):
        for key, tag in (
            ("retries", self.tags.retries),
            ("rssi", self.tags.rssi),
            ("snr", self.tags.snr),
        ):
            if key in values:
                number = health.to_number(values[key])
                if number is not None:
                    await tag.set(number)
        if "route" in values:
            route = health.to_route(values["route"])
            if route is not None:
                await self.tags.route.set(route)

    # -- status -----------------------------------------------------------------

    async def refresh_status(self, now: int):
        last = _int_or_none(self.tags.last_heard_ts.get())
        status = health.compute_status(
            last,
            now,
            health.to_number(self.config.expected_interval_min.value) or 0,
            health.to_number(self.config.late_after_intervals.value) or 2,
            health.to_number(self.config.offline_after_intervals.value) or 4,
        )
        previous = self.tags.status.get()

        await self.tags.status.set(status)
        await self.tags.status_label.set(health.STATUS_LABELS[status])
        await self.tags.status_colour.set(health.STATUS_COLOURS[status])

        if status == health.STATUS_OFFLINE and previous in (
            health.STATUS_ONLINE,
            health.STATUS_LATE,
        ):
            await self.notifications.offline.send(
                f"No report for {format_age(now - last)}."
            )

        await self._update_warning(status, last, now)

    async def _update_warning(self, status: str, last: int | None, now: int):
        issues = []
        if status == health.STATUS_OFFLINE:
            issues.append(f"Offline: no report for {format_age(now - last)}")
        elif status == health.STATUS_LATE:
            issues.append(f"Late: no report for {format_age(now - last)}")

        battery = self.tags.battery_state.get()
        if battery == health.BATTERY_LOW:
            issues.append("Battery low")
        elif battery == health.BATTERY_HIGH:
            issues.append("Battery high")

        if self.tags.link_quality.get() == health.LINK_POOR:
            issues.append("Poor link")

        await self.tags.warning_hidden.set(not issues)
        await self.tags.warning_message.set(
            " · ".join(issues) if issues else WARNING_DEFAULT_MESSAGE
        )


def _int_or_none(value) -> int | None:
    number = health.to_number(value)
    return None if number is None else int(number)
