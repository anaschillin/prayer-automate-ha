"""Config flow for Prayer Timetable."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import voluptuous as vol

from .const import CONF_DATE_FORMAT, CONF_MONTH, CONF_PDF_PATH, CONF_YEAR, DOMAIN
from .extract import extract_prayer_rows, month_number

DEFAULT_NAME = "Prayer Timetable"


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate that the PDF can be parsed."""
    pdf_path = Path(data[CONF_PDF_PATH]).expanduser()
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    await hass.async_add_executor_job(
        extract_prayer_rows,
        pdf_path,
        data.get(CONF_YEAR),
        data.get(CONF_MONTH),
        data.get(CONF_DATE_FORMAT),
        False,
    )


class PrayerTimetableConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Prayer Timetable."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = dict(user_input)
            data[CONF_PDF_PATH] = str(Path(data[CONF_PDF_PATH]).expanduser())

            if year := data.get(CONF_YEAR):
                try:
                    data[CONF_YEAR] = int(year)
                except (TypeError, ValueError):
                    errors[CONF_YEAR] = "invalid_year"

            if month := data.get(CONF_MONTH):
                try:
                    data[CONF_MONTH] = month_number(str(month))
                except ValueError:
                    errors[CONF_MONTH] = "invalid_month"

            if not errors:
                try:
                    await _validate_input(self.hass, data)
                except FileNotFoundError:
                    errors[CONF_PDF_PATH] = "file_not_found"
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_parse"
                else:
                    await self.async_set_unique_id(data[CONF_PDF_PATH])
                    self._abort_if_unique_id_configured()
                    name = data.pop(CONF_NAME, DEFAULT_NAME)
                    data = {key: value for key, value in data.items() if value not in (None, "")}
                    return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

def _user_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Return the config flow schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_PDF_PATH, default=user_input.get(CONF_PDF_PATH, "")): str,
            # Config-flow schemas are serialized for the frontend.  Keep these
            # inputs as strings and normalize them in async_step_user because
            # voluptuous Any/Coerce validators cannot be serialized.
            vol.Optional(CONF_YEAR, default=user_input.get(CONF_YEAR, "")): str,
            vol.Optional(CONF_MONTH, default=user_input.get(CONF_MONTH, "")): str,
            vol.Optional(CONF_DATE_FORMAT, default=user_input.get(CONF_DATE_FORMAT, "")): str,
        }
    )
