"""Climate entities for Eplucon zone control panels."""

from __future__ import annotations

import logging

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from dacite import from_dict

from .const import (
    DOMAIN,
    MANUFACTURER,
    ZONE_CONTROLLER_TYPES,
    CONF_USE_MOCK_DATA,
    CONF_PORTAL_USERNAME,
    CONF_PORTAL_PASSWORD,
)
from .eplucon_api.DTO.DeviceDTO import DeviceDTO
from .eplucon_api.portal_client import EpluconPortalClient, PortalAuthError, PortalRequestError
from .zone_entity import EpluconZoneEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add controllable room thermostats when portal credentials are configured."""
    portal_clients = hass.data[DOMAIN].get("portal_clients", {})
    if entry.data.get(CONF_USE_MOCK_DATA) or entry.entry_id not in portal_clients:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in coordinator.data or []:
        if isinstance(device, dict):
            device = from_dict(data_class=DeviceDTO, data=device)
        if device.type not in ZONE_CONTROLLER_TYPES or not device.zones:
            continue
        for zone in device.zones:
            if zone.control_zone_id and zone.parent_id and zone.mode_id:
                entities.append(
                    EpluconZoneClimateEntity(
                        coordinator,
                        device,
                        zone,
                        portal_clients[entry.entry_id],
                    )
                )

    _LOGGER.debug("Adding %d Eplucon zone climate entities", len(entities))
    async_add_entities(entities)


class EpluconZoneClimateEntity(EpluconZoneEntity, ClimateEntity):
    """Set a zone target using the Eplucon portal's session-authenticated route."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.1
    _attr_name = "Thermostat"

    def __init__(self, coordinator, device, zone, portal_client: EpluconPortalClient) -> None:
        super().__init__(coordinator, device, zone, entity_key="climate")
        self._portal_client = portal_client

    @property
    def device_info(self) -> dict:
        """Identify this thermostat as the zone's control panel."""
        return {
            "identifiers": {
                (DOMAIN, f"{self._module_index}_zone_{self._zone_id}")
            },
            "name": self._zone_name,
            "manufacturer": MANUFACTURER,
            "model": "Eplucon th-TOUCH zone",
            "via_device": (DOMAIN, self._module_index),
        }

    @property
    def current_temperature(self) -> float | None:
        """Return the latest measured room temperature."""
        zone = self.zone
        try:
            return float(zone.current_temperature) if zone and zone.current_temperature is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the latest configured room target."""
        zone = self.zone
        try:
            return float(zone.set_temperature) if zone and zone.set_temperature is not None else None
        except (TypeError, ValueError):
            return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the target, then request a fresh value from the read API."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        zone = self.zone
        if temperature is None or zone is None:
            raise HomeAssistantError("Eplucon zone or target temperature is unavailable")
        try:
            await self._portal_client.async_set_zone_temperature(
                self._module_index,
                zone,
                float(temperature),
            )
        except (PortalAuthError, PortalRequestError) as err:
            raise HomeAssistantError(str(err)) from err

        self.async_write_ha_state()
        try:
            await self.coordinator.async_request_refresh()
        except Exception as err:  # The portal accepted the change; refresh can retry later.
            _LOGGER.warning("Setpoint changed, but Eplucon refresh failed: %s", err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """The Eplucon zone endpoint supports heating setpoints only."""
        if hvac_mode != HVACMode.HEAT:
            raise HomeAssistantError("Eplucon zone mode changes are not supported")
