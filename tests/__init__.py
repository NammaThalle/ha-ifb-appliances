"""Common test initialization and Home Assistant mocking environment."""

import sys
from unittest.mock import MagicMock


class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator supporting generic subscription."""

    def __init__(self, hass, logger, name, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}
        self.last_update_success = True

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    async def async_config_entry_first_refresh(self):
        pass

    async def async_request_refresh(self):
        pass

    def async_set_update_interval(self, interval):
        self.update_interval = interval


class MockCoordinatorEntity:
    """Mock CoordinatorEntity supporting generic subscription."""

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    @property
    def available(self):
        return True


# Install mock homeassistant packages into sys.modules if not present
if "homeassistant" not in sys.modules:
    mock_ha = MagicMock()
    mock_ha_core = MagicMock()
    mock_ha_config_entries = MagicMock()
    mock_ha_config_entries.ConfigEntry = MagicMock

    class MockConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)

    mock_ha_config_entries.ConfigFlow = MockConfigFlow

    class MockOptionsFlow:
        def __init__(self, config_entry=None):
            self.config_entry = config_entry
        def async_show_form(self, step_id, data_schema=None, errors=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}}
        def async_create_entry(self, title, data):
            return {"type": "create_entry", "title": title, "data": data}

    mock_ha_config_entries.OptionsFlow = MockOptionsFlow
    mock_ha_helpers = MagicMock()
    mock_ha_aiohttp = MagicMock()

    mock_ha_coordinator = MagicMock()
    mock_ha_coordinator.DataUpdateCoordinator = MockDataUpdateCoordinator
    mock_ha_coordinator.CoordinatorEntity = MockCoordinatorEntity

    mock_sensor = MagicMock()
    mock_sensor.SensorEntity = MockCoordinatorEntity
    mock_sensor.SensorDeviceClass = MagicMock()
    mock_sensor.SensorStateClass = MagicMock()

    mock_binary_sensor = MagicMock()
    mock_binary_sensor.BinarySensorEntity = MockCoordinatorEntity
    mock_binary_sensor.BinarySensorDeviceClass = MagicMock()

    mock_select = MagicMock()
    mock_select.SelectEntity = MockCoordinatorEntity

    mock_button = MagicMock()
    mock_button.ButtonEntity = MockCoordinatorEntity
    mock_button.ButtonDeviceClass = MagicMock()

    def mock_async_redact_data(data, to_redact):
        if isinstance(data, dict):
            return {
                k: "**REDACTED**" if k in to_redact else mock_async_redact_data(v, to_redact)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [mock_async_redact_data(v, to_redact) for v in data]
        return data

    mock_diagnostics = MagicMock()
    mock_diagnostics.async_redact_data = mock_async_redact_data

    sys.modules["homeassistant"] = mock_ha
    sys.modules["homeassistant.core"] = mock_ha_core
    sys.modules["homeassistant.config_entries"] = mock_ha_config_entries
    sys.modules["homeassistant.helpers"] = mock_ha_helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = mock_ha_aiohttp
    sys.modules["homeassistant.helpers.update_coordinator"] = mock_ha_coordinator
    sys.modules["homeassistant.components"] = MagicMock()
    sys.modules["homeassistant.components.sensor"] = mock_sensor
    sys.modules["homeassistant.components.binary_sensor"] = mock_binary_sensor
    sys.modules["homeassistant.components.select"] = mock_select
    sys.modules["homeassistant.components.button"] = mock_button
    sys.modules["homeassistant.components.diagnostics"] = mock_diagnostics

    mock_ha.core = mock_ha_core
    mock_ha.config_entries = mock_ha_config_entries
    mock_ha.helpers = mock_ha_helpers
    mock_ha.components = sys.modules["homeassistant.components"]

if "voluptuous" not in sys.modules:
    mock_vol = MagicMock()
    sys.modules["voluptuous"] = mock_vol
