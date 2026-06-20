"""Prayer Timetable integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import CONF_DATE_FORMAT, CONF_MONTH, CONF_PDF_PATH, CONF_YEAR, DOMAIN
from .coordinator import PrayerTimetableCoordinator
from .extract import extract_prayer_rows, write_csv

PLATFORMS = (Platform.SENSOR,)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-level services."""

    async def export_csv(call: ServiceCall) -> None:
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError("Unknown Prayer Timetable config entry")

        output_path = Path(call.data["output_path"])
        pdf_path = Path(entry.data[CONF_PDF_PATH])
        year = entry.data.get(CONF_YEAR)
        month = entry.data.get(CONF_MONTH)
        date_format = entry.data.get(CONF_DATE_FORMAT)

        rows = await hass.async_add_executor_job(
            extract_prayer_rows,
            pdf_path,
            year,
            month,
            date_format,
            False,
        )
        await hass.async_add_executor_job(write_csv, rows, output_path)

    hass.services.async_register(
        DOMAIN,
        "export_csv",
        export_csv,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): cv.string,
                vol.Required("output_path"): cv.string,
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Prayer Timetable from a config entry."""
    coordinator = PrayerTimetableCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
