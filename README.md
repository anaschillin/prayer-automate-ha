# Prayer Timetable for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Hassfest](https://github.com/haffi96/prayer-automate-ha/actions/workflows/hassfest.yml/badge.svg)](https://github.com/haffi96/prayer-automate-ha/actions/workflows/hassfest.yml)
[![HACS validation](https://github.com/haffi96/prayer-automate-ha/actions/workflows/hacs.yml/badge.svg)](https://github.com/haffi96/prayer-automate-ha/actions/workflows/hacs.yml)
[![Latest release](https://img.shields.io/github/v/release/haffi96/prayer-automate-ha)](https://github.com/haffi96/prayer-automate-ha/releases)

Prayer Timetable is a custom Home Assistant integration that extracts daily Fajr, Dhuhr, Asr, Maghrib, and Isha times from a PDF timetable. It creates timestamp sensors for each prayer, identifies the next prayer, and can export parsed rows as CSV.

> [!NOTE]
> This is a community custom integration. It is not an official Home Assistant integration.

## Installation

### HACS (recommended)

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=anaschillin&repository=prayer-automate-ha&category=integration)

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu, select **Custom repositories**, and add `https://github.com/anaschillin/prayer-automate-ha` as an **Integration**.
3. Search for **Prayer Timetable** and select **Download**.
4. Restart Home Assistant.

### Manual installation

1. Download this repository.
2. Copy `custom_components/prayer_timetable` to your Home Assistant configuration directory under `custom_components/prayer_timetable`.
3. Restart Home Assistant.

## Setup

1. Open **Settings → Devices & services → Add integration**.
2. Search for **Prayer Timetable**.
3. Choose one PDF source:
   - **Upload PDF** uploads a timetable from your browser and stores it at `/config/prayer_timetable/`.
   - **PDF path** is for a timetable already accessible inside the Home Assistant runtime, for example `/config/prayer_timetable/oxford.pdf`.
4. Optionally set **Year** and **Month** when rows contain only a day number, for example `2026` and `March`.
5. Optionally set **Date format** for unusual date strings, using Python `strptime` syntax such as `%d %B %Y`.

Paths from the machine where you run a browser or development shell are not automatically available in Home Assistant containers. Use **Upload PDF** or a path mounted into Home Assistant, normally under `/config`.

## Entities

The integration creates these sensors:

- Fajr, Dhuhr, Asr, Maghrib, and Isha — timestamp sensors
- Next prayer — the name of the next prayer today
- Next prayer time — timestamp sensor for the next prayer today
- Rows parsed — diagnostic count of parsed timetable rows

## Export parsed rows

Use the `prayer_timetable.export_csv` action to write the currently configured timetable to a CSV file.

```yaml
action: prayer_timetable.export_csv
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
  output_path: /config/prayer_timetable/prayer-times.csv
```

`entry_id` is the integration configuration entry ID. `output_path` must be writable by Home Assistant.

The exported CSV contains:

```csv
date,fajr,dhuhr,asr,maghrib,isha
```

## Troubleshooting

### The PDF file could not be found

Use **Upload PDF**, or provide a path visible inside the Home Assistant runtime. `/home/...` paths on a host are usually not valid in a Home Assistant container; use `/config/...` or configure a volume mount.

### Could not parse prayer rows

PDF timetables differ substantially. The parser first tries tables, then text lines. It works best when each row includes a date or day number followed by five prayer times. Supply Year and Month when the timetable contains only day numbers.

### Integration does not appear after installation

Restart Home Assistant, then refresh the browser. HACS installs integrations under `custom_components`, but Home Assistant must restart to load them.

### Enable debug logging

Add the following to `configuration.yaml`, restart Home Assistant, then inspect the logs:

```yaml
logger:
  logs:
    custom_components.prayer_timetable: debug
```

## Standalone CLI

This repository also includes a command-line extractor for local use:

```bash
uv run prayer-extract timetable.pdf prayer-times.csv --year 2026 --month March
```

## Support and contributing

Report problems and request features in the [issue tracker](https://github.com/haffi96/prayer-automate-ha/issues). Do not attach timetable PDFs containing personal or copyrighted material unless you have permission to share them.

This project is released under the [MIT License](LICENSE).


## Layout-aware monthly timetables (v0.2.0)

Nuneaton Muslim Society's 13-column monthly PDF format is automatically detected.
Each dated row provides **Beginning Times** (`fajr`, `dhuhr`, `asr`, `maghrib`, `isha`)
and **Jamaat Times** (`fajr_jamaat`, `dhuhr_jamaat`, `asr_jamaat`, `maghrib_jamaat`, `isha_jamaat`).
Quotation marks in Jamaat columns repeat the previous day's value. The original generic
PDF parser is retained for other layouts; those PDFs do not provide Jamaat values.

The integration adds five Jamaat timestamp sensors, `next_jamaat` and `next_jamaat_time`.
Existing beginning-time sensor unique IDs are unchanged. Both next-event calculations
include the following day and update every minute. Parsed rows are cached until the PDF changes.

CSV export includes the original columns plus five Jamaat columns (blank when unavailable).
The Nuneaton layout parser prefers `pdftotext -layout` when installed and otherwise uses
`pdfplumber`'s layout extraction. Verify the CSV after uploading a new PDF.
