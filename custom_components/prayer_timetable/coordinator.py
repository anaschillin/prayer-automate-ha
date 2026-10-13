"""Data coordinator for Prayer Timetable."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_DATE_FORMAT, CONF_MONTH, CONF_PDF_PATH, CONF_YEAR, DOMAIN, PRAYERS
from .extract import PrayerRow, extract_prayer_rows, output_time

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrayerTimetableData:
    today: date
    today_row: PrayerRow | None
    prayer_datetimes: dict[str, datetime]
    jamaat_datetimes: dict[str, datetime]
    next_prayer: str | None
    next_prayer_time: datetime | None
    next_jamaat: str | None
    next_jamaat_time: datetime | None
    row_count: int


def _row_datetimes(row: PrayerRow | None, jamaat: bool = False) -> dict[str, datetime]:
    """Build timezone-aware local timestamps; omit unavailable Jamaat values."""
    if row is None or not isinstance(row.day, date):
        return {}
    values = {}
    for prayer in PRAYERS:
        value = getattr(row, f"{prayer}_jamaat" if jamaat else prayer)
        if not value:
            continue
        if not jamaat and not row.normalized:
            value = output_time(value, prayer)
        hour, minute = map(int, value.split(':'))
        values[prayer] = datetime.combine(row.day, time(hour, minute), tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return values


def _next_event(rows: dict[date, PrayerRow], now: datetime, jamaat: bool) -> tuple[str | None, datetime | None]:
    """Find next event including the following day's timetable."""
    events = []
    for day in (now.date(), now.date() + timedelta(days=1)):
        for prayer, timestamp in _row_datetimes(rows.get(day), jamaat).items():
            if timestamp > now:
                events.append((prayer, timestamp))
    return min(events, key=lambda event: event[1]) if events else (None, None)


class PrayerTimetableCoordinator(DataUpdateCoordinator[PrayerTimetableData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, logger=_LOGGER, name=DOMAIN, update_interval=timedelta(minutes=1))
        self.config_entry = entry
        self._rows: dict[date, PrayerRow] | None = None
        self._pdf_mtime_ns: int | None = None

    async def _load_rows(self) -> dict[date, PrayerRow]:
        pdf_path = Path(self.config_entry.data[CONF_PDF_PATH])
        mtime = await self.hass.async_add_executor_job(lambda: pdf_path.stat().st_mtime_ns)
        if self._rows is None or mtime != self._pdf_mtime_ns:
            rows = await self.hass.async_add_executor_job(
                extract_prayer_rows, pdf_path,
                self.config_entry.data.get(CONF_YEAR),
                self.config_entry.data.get(CONF_MONTH),
                self.config_entry.data.get(CONF_DATE_FORMAT), False,
            )
            self._rows = {row.day: row for row in rows if isinstance(row.day, date)}
            self._pdf_mtime_ns = mtime
        return self._rows

    async def _async_update_data(self) -> PrayerTimetableData:
        try:
            rows = await self._load_rows()
            now = dt_util.now()
            today = now.date()
            current = rows.get(today)
            next_prayer, next_prayer_time = _next_event(rows, now, False)
            next_jamaat, next_jamaat_time = _next_event(rows, now, True)
            return PrayerTimetableData(
                today, current, _row_datetimes(current), _row_datetimes(current, True),
                next_prayer, next_prayer_time, next_jamaat, next_jamaat_time, len(rows),
            )
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Failed to load prayer timetable: {err}") from err
