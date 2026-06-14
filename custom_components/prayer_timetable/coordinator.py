"""Data coordinator for Prayer Timetable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONTH, CONF_YEAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_DATE_FORMAT, CONF_PDF_PATH, DOMAIN, PRAYERS
from .extract import PrayerRow, extract_prayer_rows, output_time

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrayerTimetableData:
    """Current prayer timetable data."""

    today: date
    today_row: PrayerRow | None
    prayer_datetimes: dict[str, datetime]
    next_prayer: str | None
    next_prayer_time: datetime | None
    row_count: int


class PrayerTimetableCoordinator(DataUpdateCoordinator[PrayerTimetableData]):
    """Fetch prayer timetable data from the configured PDF."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.config_entry = entry

    async def _async_update_data(self) -> PrayerTimetableData:
        """Load and parse the PDF timetable."""
        pdf_path = Path(self.config_entry.data[CONF_PDF_PATH])
        year = self.config_entry.data.get(CONF_YEAR)
        month = self.config_entry.data.get(CONF_MONTH)
        date_format = self.config_entry.data.get(CONF_DATE_FORMAT)

        try:
            rows = await self.hass.async_add_executor_job(
                extract_prayer_rows,
                pdf_path,
                year,
                month,
                date_format,
                False,
            )
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Failed to parse prayer timetable PDF: {err}") from err

        today = dt_util.now().date()
        rows_by_day = {row.day: row for row in rows if isinstance(row.day, date)}
        today_row = rows_by_day.get(today)
        prayer_datetimes = _row_datetimes(today_row) if today_row else {}
        now = dt_util.now()
        upcoming = [(prayer, value) for prayer, value in prayer_datetimes.items() if value >= now]
        next_prayer, next_prayer_time = min(upcoming, key=lambda item: item[1]) if upcoming else (None, None)

        return PrayerTimetableData(
            today=today,
            today_row=today_row,
            prayer_datetimes=prayer_datetimes,
            next_prayer=next_prayer,
            next_prayer_time=next_prayer_time,
            row_count=len(rows),
        )


def _row_datetimes(row: PrayerRow) -> dict[str, datetime]:
    """Convert a prayer row into timezone-aware datetimes for today."""
    if not isinstance(row.day, date):
        return {}

    timezone = dt_util.DEFAULT_TIME_ZONE
    values: dict[str, datetime] = {}
    for prayer in PRAYERS:
        hour_text, minute_text = output_time(getattr(row, prayer), prayer).split(":", maxsplit=1)
        values[prayer] = datetime.combine(
            row.day,
            time(int(hour_text), int(minute_text)),
            tzinfo=timezone,
        )
    return values
