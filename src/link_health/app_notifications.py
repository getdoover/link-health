from pathlib import Path

from pydoover import notifications
from pydoover.notifications import NotificationPolicy, NotificationSeverity


class LinkHealthNotifications(notifications.Notifications):
    offline = notifications.Notification(
        "The remote node has stopped reporting.",
        display_name="Node offline",
        description=(
            "The node has not reported for longer than the configured offline "
            "time. A node that has never reported does not send this."
        ),
        severity=NotificationSeverity.Warn,
        policy=NotificationPolicy.default,
    )
    battery_low = notifications.Notification(
        "The remote node's battery is low.",
        display_name="Battery low",
        description="The node's battery voltage dropped below the Battery Low limit.",
        severity=NotificationSeverity.Warn,
        policy=NotificationPolicy.default,
    )
    battery_high = notifications.Notification(
        "The remote node's battery voltage is high.",
        display_name="Battery high",
        description=(
            "The node's battery voltage rose above the Battery High limit, which "
            "can point to a charging fault."
        ),
        severity=NotificationSeverity.Warn,
        policy=NotificationPolicy.opt_in,
    )
    poor_link = notifications.Notification(
        "The remote node's link quality is poor.",
        display_name="Poor link",
        description="The node's link success rate dropped below the Poor limit.",
        severity=NotificationSeverity.Warn,
        policy=NotificationPolicy.opt_in,
    )


def export():
    LinkHealthNotifications.export(
        Path(__file__).parents[2] / "doover_config.json",
        "link_health",
    )
