from pathlib import Path

from pydoover import ui

from .app_tags import LinkHealthTags
from .health import parse_message_path


class LinkHealthUI(ui.UI):
    # Shown while the node is late or offline, or its battery or link is out of
    # limits. Visibility and text are bound to tags (the schema is published once).
    warning = ui.WarningIndicator(
        LinkHealthTags.warning_message,
        name="link_warning",
        hidden=LinkHealthTags.warning_hidden,
        can_cancel=False,
        position=1,
    )

    status = ui.TextVariable(
        "Status",
        name="status",
        value=LinkHealthTags.status_label,
        colour=LinkHealthTags.status_colour,
        graphable=False,
        position=10,
    )

    last_heard = ui.Timestamp(
        "Last Heard",
        name="last_heard",
        value=LinkHealthTags.last_heard_ts,
        position=20,
    )

    battery = ui.NumericVariable(
        "Battery",
        name="battery",
        units="V",
        value=LinkHealthTags.battery_v,
        colour=LinkHealthTags.battery_colour,
        precision=2,
        position=30,
    )

    link_success = ui.NumericVariable(
        "Link Success",
        name="link_success",
        units="%",
        value=LinkHealthTags.link_success_pct,
        precision=0,
        form=ui.Widget.radial,
        position=40,
    )

    link_success_24h = ui.NumericVariable(
        "Link Success (24 h avg)",
        name="link_success_24h",
        units="%",
        value=LinkHealthTags.link_success_24h_pct,
        precision=1,
        position=50,
    )

    retries = ui.NumericVariable(
        "Retries",
        name="retries",
        value=LinkHealthTags.retries,
        precision=0,
        position=60,
    )

    rssi = ui.NumericVariable(
        "Signal (RSSI)",
        name="rssi",
        units="dBm",
        value=LinkHealthTags.rssi,
        precision=0,
        position=70,
    )

    snr = ui.NumericVariable(
        "Signal-to-Noise",
        name="snr",
        units="dB",
        value=LinkHealthTags.snr,
        precision=1,
        position=80,
    )

    route = ui.TextVariable(
        "Route",
        name="route",
        value=LinkHealthTags.route,
        graphable=False,
        position=90,
    )

    async def setup(self):
        cfg = self.config

        low = _num(cfg.battery_low_v.value)
        high = _num(cfg.battery_high_v.value)
        if low is not None and high is not None and high > low:
            top = high + max(2.0, (high - low) * 0.25)
            bottom = max(0.0, low - max(2.0, (high - low) * 0.5))
            self.battery.ranges = [
                ui.Range("Low", bottom, low, ui.Colour.red),
                ui.Range("Normal", low, high, ui.Colour.green),
                ui.Range("High", high, top, ui.Colour.orange),
            ]

        warn = _num(cfg.link_warn_pct.value)
        poor = _num(cfg.link_poor_pct.value)
        if warn is not None and poor is not None and 0 <= poor <= warn <= 100:
            self.link_success.ranges = [
                ui.Range("Poor", 0, poor, ui.Colour.red),
                ui.Range("Fair", poor, warn, ui.Colour.orange),
                ui.Range("Good", warn, 100, ui.Colour.green),
            ]

        # Hide what the node is not configured to report.
        counters = _configured(cfg.success_count_path.value) and _configured(
            cfg.attempt_count_path.value
        )
        link = _configured(cfg.link_success_path.value) or counters
        self.battery.hidden = not _configured(cfg.battery_voltage_path.value)
        self.link_success.hidden = not link
        self.link_success_24h.hidden = not link
        self.retries.hidden = not _configured(cfg.retries_path.value)
        self.rssi.hidden = not _configured(cfg.rssi_path.value)
        self.snr.hidden = not _configured(cfg.snr_path.value)
        self.route.hidden = not _configured(cfg.route_path.value)


def _num(value):
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _configured(value) -> bool:
    try:
        return parse_message_path(value) is not None
    except (TypeError, ValueError):
        return False


def export():
    LinkHealthUI(None, None, None).export(
        Path(__file__).parents[2] / "doover_config.json",
        "link_health",
    )
