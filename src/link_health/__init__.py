from pydoover.processor import run_app

from .application import LinkHealthApplication


def handler(event, context):
    """Lambda handler entry point."""
    return run_app(
        LinkHealthApplication(),
        event,
        context,
    )
