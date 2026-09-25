"""Sensor platform for kamstrup_21."""

import json
from pathlib import Path
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KamstrupUpdateCoordinator
from .const import DOMAIN

_DEVICE_CLASSES = {
    "water": SensorDeviceClass.WATER,
    "volume_flow_rate": SensorDeviceClass.VOLUME_FLOW_RATE,
    "duration": SensorDeviceClass.DURATION,
}
_STATE_CLASSES = {
    "total": SensorStateClass.TOTAL,
    "measurement": SensorStateClass.MEASUREMENT,
}


def _load_descriptions() -> list[SensorEntityDescription]:
    """Load sensor descriptions from the integration configuration file."""
    with Path(__file__).with_name("sensors.json").open(encoding="utf-8") as file:
        configurations: list[dict[str, Any]] = json.load(file)

    return [
        SensorEntityDescription(
            key=configuration["key"],
            name=configuration["name"],
            icon=configuration.get("icon"),
            device_class=_DEVICE_CLASSES.get(configuration.get("device_class")),
            state_class=_STATE_CLASSES.get(configuration.get("state_class")),
            native_unit_of_measurement=configuration.get(
                "native_unit_of_measurement"
            ),
            entity_registry_enabled_default=configuration.get(
                "entity_registry_enabled_default", True
            ),
        )
        for configuration in configurations
    ]


DESCRIPTIONS = _load_descriptions()


def _format_special_value(
    key: str, value: str | float, unit: str | None
) -> str | float | None:
    """Format KMP date/time values and integer-like information fields."""
    if unit == "°C" and float(value) in {-127, 127, 128}:
        return None
    if unit == "yy:mm:dd":
        formatted = f"{int(value):06d}"
        if key in {"1003", "138", "140"}:
            return f"20{formatted[:2]}-{formatted[2:4]}-{formatted[4:]}"
        return f"{formatted[:2]}:{formatted[2:4]}:{formatted[4:]}"
    if unit == "yyyy:mm:dd":
        formatted = f"{int(value):08d}"
        return f"{formatted[:4]}-{formatted[4:6]}-{formatted[6:]}"
    if unit == "mm:dd":
        formatted = f"{int(value):04d}"
        return f"{formatted[:2]}-{formatted[2:]}"
    if unit == "hh:mm:ss":
        formatted = f"{int(value):06d}"
        return f"{formatted[:2]}:{formatted[2:4]}:{formatted[4:]}"
    if unit == "Bitfield":
        return str(int(value))
    if key in {"99", "1001", "113", "1005"} and float(value).is_integer():
        return str(int(value))
    return value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kamstrup sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[KamstrupSensor] = []

    # Add all meter sensors described above.
    for description in DESCRIPTIONS:
        entities.append(
            KamstrupMeterSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                description=description,
            )
        )

    async_add_entities(entities)


class KamstrupSensor(CoordinatorEntity[KamstrupUpdateCoordinator], SensorEntity):
    """Defines a Kamstrup sensor."""

    def __init__(
        self,
        coordinator: KamstrupUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Kamstrup sensor."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info


class KamstrupMeterSensor(KamstrupSensor):
    """Defines a Kamstrup meter sensor."""

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.coordinator.register_command(self.int_key)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self.coordinator.unregister_command(self.int_key)

    @property
    def int_key(self) -> int:
        """Get the key as an int"""
        return int(self.entity_description.key)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data:
            value_data = self.coordinator.data.get(self.int_key)
            if value_data:
                value = value_data.get("value", None)
                unit = value_data.get("unit", None)
                if value is not None:
                    return _format_special_value(
                        self.entity_description.key, value, unit
                    )

        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.coordinator.data:
            value_data = self.coordinator.data.get(self.int_key)
            if value_data:
                device_unit = value_data.get("unit", None)
                if device_unit not in {
                    "yy:mm:dd",
                    "yyyy:mm:dd",
                    "mm:dd",
                    "hh:mm:ss",
                    "ASCII",
                    "Bitfield",
                } and device_unit:
                    return device_unit
        
        # Fall back to the unit defined in the entity description
        return self.entity_description.native_unit_of_measurement
