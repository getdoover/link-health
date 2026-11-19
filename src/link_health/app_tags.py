from pydoover.tags import Tag, Tags

from .health import STATUS_COLOURS, STATUS_LABELS, STATUS_UNKNOWN

WARNING_DEFAULT_MESSAGE = "Remote node needs attention"


class LinkHealthTags(Tags):
    # online / late / offline / unknown (never heard)
    status = Tag("string", default=STATUS_UNKNOWN)
    status_label = Tag("string", default=STATUS_LABELS[STATUS_UNKNOWN])
    status_colour = Tag("string", default=STATUS_COLOURS[STATUS_UNKNOWN])
    # epoch milliseconds of the node's last report
    last_heard_ts = Tag("number", default=None)

    battery_v = Tag("number", default=None, live=True)
    # normal / low / high; None until a voltage arrives
    battery_state = Tag("string", default=None)
    battery_colour = Tag("string", default=None)

    link_success_pct = Tag("number", default=None, live=True)
    link_success_24h_pct = Tag("number", default=None)
    # good / fair / poor; None until a link reading arrives
    link_quality = Tag("string", default=None)

    retries = Tag("number", default=None)
    rssi = Tag("number", default=None, live=True)
    snr = Tag("number", default=None)
    route = Tag("string", default=None)

    # Internal state carried between invocations (each is a fresh instance).
    link_samples = Tag("array", default=None)
    last_counters = Tag("array", default=None)

    # Drive the warning indicator; the UI schema is published once, so its
    # visibility and text are bound to tags.
    warning_hidden = Tag("boolean", default=True)
    warning_message = Tag("string", default=WARNING_DEFAULT_MESSAGE)
