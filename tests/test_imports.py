def test_import_processor_app():
    from link_health import handler
    from link_health.application import LinkHealthApplication

    assert LinkHealthApplication
    assert handler


def test_schemas_build():
    from link_health.app_config import LinkHealthConfig
    from link_health.app_notifications import LinkHealthNotifications
    from link_health.app_ui import LinkHealthUI

    assert isinstance(LinkHealthConfig.to_schema(), dict)
    assert isinstance(LinkHealthUI(None, None, None).to_schema(), dict)
    assert len(LinkHealthNotifications().to_schema()) == 4
