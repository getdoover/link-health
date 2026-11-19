from pathlib import Path

from pydoover import config
from pydoover.config import ApplicationDefaultOpen, ApplicationPosition
from pydoover.processor import ManySubscriptionConfig, ScheduleConfig


class CounterType:
    CUMULATIVE = "Cumulative"
    PER_REPORT = "Per report"


_PATH_HELP = (
    "Use '$channel.path.to.value', for example '$io_state.battery_v'. "
    "Leave empty if the node does not report it."
)


class LinkHealthConfig(config.Schema):
    # -- inputs (message paths) -------------------------------------------------
    battery_voltage_path = config.String(
        "Battery Voltage Path",
        description="Message path of the node's battery or supply voltage (V). "
        + _PATH_HELP,
        default="$io_state.battery_v",
        position=0,
    )
    link_success_path = config.String(
        "Link Success Path",
        description="Message path of the node's link success rate (0-100 %). "
        + _PATH_HELP,
        default="$io_state.link_success_pct",
        position=1,
    )
    success_count_path = config.String(
        "Success Count Path",
        description=(
            "Optional message path of a count of successful transmissions. Used "
            "with Attempt Count Path to work out the success rate and its 24 h "
            "average when the node reports counters instead of a percentage. "
            + _PATH_HELP
        ),
        default="",
        position=2,
    )
    attempt_count_path = config.String(
        "Attempt Count Path",
        description="Optional message path of a count of attempted transmissions. "
        + _PATH_HELP,
        default="",
        position=3,
    )
    counter_type = config.Enum(
        "Counter Type",
        choices=[CounterType.CUMULATIVE, CounterType.PER_REPORT],
        default=CounterType.CUMULATIVE,
        description=(
            "Whether the success / attempt counters are running totals (a drop "
            "is read as a reset) or counts for each report on their own."
        ),
        position=4,
    )
    retries_path = config.String(
        "Retries Path",
        description="Message path of the node's retry count. " + _PATH_HELP,
        default="$io_state.retries",
        position=5,
    )
    rssi_path = config.String(
        "Signal Strength (RSSI) Path",
        name="rssi_path",
        description="Message path of the received signal strength (dBm). " + _PATH_HELP,
        default="$io_state.rssi",
        position=6,
    )
    snr_path = config.String(
        "Signal-to-Noise (SNR) Path",
        name="snr_path",
        description="Optional message path of the signal-to-noise ratio (dB). "
        + _PATH_HELP,
        default="",
        position=7,
    )
    route_path = config.String(
        "Route Path",
        description=(
            "Message path of a text (or list of hops) describing the route the "
            "node's reports take, for example 'Node 4 → Repeater → Gateway'. "
            + _PATH_HELP
        ),
        default="$io_state.route",
        position=8,
    )
    last_heard_path = config.String(
        "Last Heard Path",
        description=(
            "Message path of the time the node was last heard (epoch seconds, "
            "epoch milliseconds or an ISO 8601 time). When a report does not "
            "carry it, the time the message arrived is used. " + _PATH_HELP
        ),
        default="$io_state.last_heard",
        position=9,
    )

    # -- reporting thresholds ---------------------------------------------------
    expected_interval_min = config.Number(
        "Expected Report Interval (min)",
        name="expected_interval_min",
        description="How often the node is expected to report, in minutes.",
        default=15.0,
        minimum=0.1,
        position=10,
    )
    late_after_intervals = config.Number(
        "Late After (intervals)",
        name="late_after_intervals",
        description=(
            "The node reads Late once its last report is older than this many "
            "expected intervals."
        ),
        default=2.0,
        minimum=1,
        position=11,
    )
    offline_after_intervals = config.Number(
        "Offline After (intervals)",
        name="offline_after_intervals",
        description=(
            "The node reads Offline once its last report is older than this many "
            "expected intervals."
        ),
        default=4.0,
        minimum=1,
        position=12,
    )

    # -- power thresholds -------------------------------------------------------
    battery_low_v = config.Number(
        "Battery Low (V)",
        name="battery_low_v",
        description="Battery voltage below this reads Low.",
        default=9.5,
        position=13,
    )
    battery_high_v = config.Number(
        "Battery High (V)",
        name="battery_high_v",
        description=(
            "Battery voltage above this reads High. A 12 V system charging "
            "normally sits around 13-14 V."
        ),
        default=14.5,
        position=14,
    )

    # -- link thresholds --------------------------------------------------------
    link_warn_pct = config.Number(
        "Link Success Warning (%)",
        name="link_warn_pct",
        description="Link success below this reads Fair.",
        default=80.0,
        minimum=0,
        maximum=100,
        position=15,
    )
    link_poor_pct = config.Number(
        "Link Success Poor (%)",
        name="link_poor_pct",
        description="Link success below this reads Poor.",
        default=50.0,
        minimum=0,
        maximum=100,
        position=16,
    )

    subscription = ManySubscriptionConfig(
        default=["io_state"],
        advanced=True,
        position=17,
    )
    schedule = ScheduleConfig(
        description=(
            "How often to re-check the node's status when no report arrives, so "
            "Late and Offline are detected on time."
        ),
        default="rate(5 minutes)",
        advanced=True,
        position=18,
    )

    position = ApplicationPosition(default=900, position=19)
    default_open = ApplicationDefaultOpen(default=False, position=20)


def export():
    LinkHealthConfig.export(
        Path(__file__).parents[2] / "doover_config.json",
        "link_health",
    )
