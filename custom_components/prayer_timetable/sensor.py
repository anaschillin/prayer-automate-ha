"""Sensors for Prayer Timetable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRAYERS
from .coordinator import PrayerTimetableCoordinator


@dataclass(frozen=True, kw_only=True)
class PrayerSensorEntityDescription(SensorEntityDescription):
    """Prayer sensor description."""

    prayer: str | None = None


PRAYER_DESCRIPTIONS = tuple(
    PrayerSensorEntityDescription(
        key=prayer,
        translation_key=prayer,
        device_class=SensorDeviceClass.TIMESTAMP,
        prayer=prayer,
    )
    for prayer in PRAYERS
) + tuple(
    PrayerSensorEntityDescription(
        key=f"{prayer}_jamaat", translation_key=f"{prayer}_jamaat",
        device_class=SensorDeviceClass.TIMESTAMP, prayer=f"{prayer}_jamaat",
    ) for prayer in PRAYERS
)

EXTRA_DESCRIPTIONS = (
    PrayerSensorEntityDescription(key="next_prayer", translation_key="next_prayer"),
    PrayerSensorEntityDescription(
        key="next_prayer_time",
        translation_key="next_prayer_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    PrayerSensorEntityDescription(key="next_jamaat", translation_key="next_jamaat"),
    PrayerSensorEntityDescription(
        key="next_jamaat_time", translation_key="next_jamaat_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    PrayerSensorEntityDescription(
        key="row_count",
        translation_key="row_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Prayer Timetable sensors."""
    coordinator: PrayerTimetableCoordinator = entry.runtime_data
    async_add_entities(
        PrayerTimetableSensor(coordinator, entry, description)
        for description in (*PRAYER_DESCRIPTIONS, *EXTRA_DESCRIPTIONS)
    )


class PrayerTimetableSensor(CoordinatorEntity[PrayerTimetableCoordinator], SensorEntity):
    """Prayer Timetable sensor."""

    entity_description: PrayerSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PrayerTimetableCoordinator,
        entry: ConfigEntry,
        description: PrayerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Prayer Timetable",
        }

    @property
    def native_value(self) -> datetime | str | int | None:
        """Return the sensor value."""
        data = self.coordinator.data
        if data is None:
            return None

        if self.entity_description.prayer:
            prayer = self.entity_description.prayer
            if prayer.endswith("_jamaat"):
                return data.jamaat_datetimes.get(prayer.removesuffix("_jamaat"))
            return data.prayer_datetimes.get(prayer)
        if self.entity_description.key == "next_prayer":
            return data.next_prayer
        if self.entity_description.key == "next_prayer_time":
            return data.next_prayer_time
        if self.entity_description.key == "next_jamaat":
            return data.next_jamaat
        if self.entity_description.key == "next_jamaat_time":
            return data.next_jamaat_time
        if self.entity_description.key == "row_count":
            return data.row_count
        return None
