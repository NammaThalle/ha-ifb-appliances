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
