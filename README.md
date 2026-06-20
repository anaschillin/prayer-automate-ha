# Prayer Automate

Extract the five daily prayer times from a PDF timetable and write them to CSV.

## Usage

```bash
uv run prayer-extract timetable.pdf prayer-times.csv
```

Output columns:

```csv
date,fajr,dhuhr,asr,maghrib,isha
```

If your timetable uses `Zuhr` instead of `Dhuhr`, the script normalises it to `dhuhr`.

## Notes

PDF timetables vary a lot. This script first tries structured PDF tables, then falls back to text lines. It works best when each row contains a date or day number followed by the five prayer times.

Useful options:

```bash
uv run prayer-extract timetable.pdf prayer-times.csv --year 2026 --month March
uv run prayer-extract timetable.pdf prayer-times.csv --date-format '%d %B %Y'
uv run prayer-extract timetable.pdf prayer-times.csv --debug
```

Use `--year` and `--month` when the PDF rows only contain day numbers.

## Home Assistant Custom Integration

This repository also includes a custom integration in `custom_components/prayer_timetable`.

Install it by copying `custom_components/prayer_timetable` into your Home Assistant `custom_components` directory, then restart Home Assistant.

Add it from **Settings > Devices & services > Add integration > Prayer Timetable** and provide:

- `Upload PDF`: upload a PDF directly from the browser; the integration stores it in `/config/prayer_timetable/`
- `PDF path`: optional alternative for a PDF already available inside Home Assistant (for example `/config/prayer_timetable/oxford.pdf`)
- `Year` and `Month`: optional, but useful when the PDF rows only contain day numbers
- `Date format`: optional Python `strptime` format for unusual date formats

The integration exposes timestamp sensors for `Fajr`, `Dhuhr`, `Asr`, `Maghrib`, and `Isha`, plus `Next prayer`, `Next prayer time`, and a diagnostic `Rows parsed` sensor.

The existing PDF-to-CSV flow is available as the `prayer_timetable.export_csv` service. Pass the integration `entry_id` and an `output_path` on the Home Assistant host.
