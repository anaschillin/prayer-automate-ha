"""Constants for the Prayer Timetable integration."""

DOMAIN = "prayer_timetable"

CONF_PDF_PATH = "pdf_path"
CONF_DATE_FORMAT = "date_format"
# Home Assistant does not provide generic month/year configuration constants.
# Keep these integration-specific values here so the config flow works across
# Home Assistant releases.
CONF_MONTH = "month"
CONF_YEAR = "year"

PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
