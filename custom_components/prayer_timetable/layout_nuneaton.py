"""Layout-aware extractor for Nuneaton Muslim Society monthly Salah timetable PDFs.

Requires poppler's `pdftotext` command. Extracts both Beginning/End Times and Jamaat Times.
Usage: python nuneaton_layout_parser.py timetable.pdf --year 2026 --output prayers.csv
"""
from __future__ import annotations
import argparse
import calendar
import csv
from datetime import date
from pathlib import Path
import re
import subprocess
import shutil
import pdfplumber

MONTHS = {name: number for number, name in enumerate(calendar.month_name) if name}
MONTH_HEADING = re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+(20\d{2})\b', re.I)
DAY_ROW = re.compile(r'^\s*(\d{1,2})\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+(.*)$', re.I)
TIME = re.compile(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)')
FIELDS = ('date', 'fajr', 'dhuhr', 'asr', 'maghrib', 'isha',
          'fajr_jamaat', 'dhuhr_jamaat', 'asr_jamaat', 'maghrib_jamaat', 'isha_jamaat')
JAMAAT_NAMES = ('fajr_jamaat', 'dhuhr_jamaat', 'asr_jamaat', 'maghrib_jamaat', 'isha_jamaat')
DITTO = {'"', '“', '”', '‘', '’', }


def normalize(raw: str, prayer: str) -> str:
    """Convert PDF 12-hour notation to local 24-hour wall-clock time."""
    h, m = map(int, raw.split(':'))
    if not 1 <= h <= 12 or not 0 <= m <= 59:
        raise ValueError(f'Invalid time: {raw}')
    # Dawn always occurs before noon; all other beginning times occur after noon.
    if prayer in ('fajr', 'fajr_jamaat'):
        h = h % 12
    elif prayer in ('dhuhr', 'dhuhr_jamaat'):
        # Istewa/Dhuhr may be 11:xx before winter noon, 12:xx or 1:xx in BST.
        h = h if h in (11, 12) else h + 12
    else:
        h = 12 if h == 12 else h + 12
    return f'{h:02d}:{m:02d}'


def parse_pdf(pdf: Path, expected_year: int | None = None) -> list[dict[str, str]]:
    if shutil.which('pdftotext'):
        result = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, text=True)
        pages = result.stdout.split('\f')
    else:
        with pdfplumber.open(pdf) as document:
            pages = [page.extract_text(layout=True, x_tolerance=2, y_tolerance=3) or '' for page in document.pages]
    records: dict[str, dict[str, str]] = {}
    for page in pages:
        heading = MONTH_HEADING.search(page)
        if not heading:
            continue
        month_name, year_str = heading.groups()
        month, year = MONTHS[month_name.capitalize()], int(year_str)
        if expected_year is not None and year != expected_year:
            continue
        previous_jamaat: dict[str, str] = {}
        for line in page.splitlines():
            match = DAY_ROW.match(line)
            if not match:
                continue
            day_str, weekday, _hijri, rest = match.groups()
            day = int(day_str)
            try:
                current = date(year, month, day)
            except ValueError as exc:
                raise ValueError(f'Invalid calendar date in {month_name}: {line}') from exc
            if current.strftime('%a').lower() != weekday.lower():
                raise ValueError(f'Weekday mismatch on {current}: {line}')
            # Fixed-width PDF layout: 8 beginning columns followed by 5 Jamaat
            # columns. Quotation marks mean "same as the preceding day's value"
            # in the *same Jamaat column*, not the preceding prayer.
            cells = rest.split()
            if len(cells) != 13:
                raise ValueError(f'Expected 13 time/ditto cells on {current}, got {len(cells)}: {line}')
            if not all(TIME.fullmatch(cell) for cell in cells[:8]):
                raise ValueError(f'Invalid beginning time on {current}: {line}')
            selected = {'fajr': cells[1], 'dhuhr': cells[4], 'asr': cells[5],
                        'maghrib': cells[6], 'isha': cells[7]}
            row = {'date': current.isoformat(),
                   **{k: normalize(v, k) for k, v in selected.items()}}
            for name, raw in zip(JAMAAT_NAMES, cells[8:]):
                if raw in DITTO:
                    if name not in previous_jamaat:
                        raise ValueError(f'Ditto without preceding {name} on {current}')
                    value = previous_jamaat[name]
                elif TIME.fullmatch(raw):
                    value = normalize(raw, name)
                else:
                    raise ValueError(f'Unexpected Jamaat value {raw!r} on {current}')
                row[name] = value
                previous_jamaat[name] = value
            if row['date'] in records:
                raise ValueError(f'Duplicate date: {row["date"]}')
            records[row['date']] = row
    if not records:
        raise ValueError('No monthly timetable rows found')
    years = {int(key[:4]) for key in records}
    for year in years:
        expected = {date(year, m, d).isoformat() for m in range(1, 13)
                    for d in range(1, calendar.monthrange(year, m)[1] + 1)}
        missing = sorted(expected - records.keys())
        if missing:
            raise ValueError(f'Missing {len(missing)} dates for {year}, first: {missing[:8]}')
    return [records[key] for key in sorted(records)]


