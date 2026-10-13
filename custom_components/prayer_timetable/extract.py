"""Prayer timetable PDF extraction helpers."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Sequence

import pdfplumber

PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
PRAYER_ALIASES = {
    "fajr": "fajr",
    "fajar": "fajr",
    "subh": "fajr",
    "dhuhr": "dhuhr",
    "zuhr": "dhuhr",
    "zuhur": "dhuhr",
    "dhur": "dhuhr",
    "asr": "asr",
    "maghrib": "maghrib",
    "magrib": "maghrib",
    "isha": "isha",
    "ishaa": "isha",
    "esha": "isha",
}
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d\b")
DAY_RE = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])\b")
PERIOD_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b",
    re.IGNORECASE,
)
MONTH_TOKEN_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b", re.IGNORECASE)
WEEKDAY_RE = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", re.IGNORECASE)
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DATE_PATTERNS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)


@dataclass(frozen=True)
class PrayerRow:
    """Extracted prayer row."""

    day: date | str
    fajr: str
    dhuhr: str
    asr: str
    maghrib: str
    isha: str
    fajr_jamaat: str | None = None
    dhuhr_jamaat: str | None = None
    asr_jamaat: str | None = None
    maghrib_jamaat: str | None = None
    isha_jamaat: str | None = None
    # Layout-aware rows already contain 24-hour local times.
    normalized: bool = False


def normalise_cell(value: object) -> str:
    """Normalize whitespace in a PDF table cell."""
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalise_time(value: str) -> str:
    """Normalize a PDF time string."""
    return value.replace(".", ":")


def output_time(value: str, prayer: str) -> str:
    """Return a 24-hour HH:MM value for a prayer."""
    hour_text, minute_text = normalise_time(value).split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if prayer in {"dhuhr", "asr", "maghrib", "isha"} and hour < 12:
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def normalise_header(value: str) -> str | None:
    """Normalize a prayer name table header."""
    key = re.sub(r"[^a-z]", "", value.lower())
    return PRAYER_ALIASES.get(key)


def parse_known_date(value: str, date_format: str | None = None) -> date | None:
    """Parse a supported date string."""
    value = value.strip().replace(",", "")
    patterns = (date_format, *DATE_PATTERNS) if date_format else DATE_PATTERNS
    for pattern in patterns:
        if not pattern:
            continue
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def make_day(value: str, year: int | None, month: int | None, date_format: str | None) -> date | str | None:
    """Build a date from a PDF date/day cell."""
    parsed = parse_known_date(value, date_format)
    if parsed:
        return parsed

    match = DAY_RE.search(value)
    if not match:
        return None

    day_number = int(match.group(0))
    if year and month:
        try:
            return date(year, month, day_number)
        except ValueError:
            return None
    return str(day_number).zfill(2)


def month_number(value: str | int | None) -> int | None:
    """Convert a month number/name to an integer."""
    if value in (None, ""):
        return None
    value = str(value)
    if value.isdigit():
        month = int(value)
        if 1 <= month <= 12:
            return month
    for pattern in ("%b", "%B"):
        try:
            return datetime.strptime(value, pattern).month
        except ValueError:
            pass
    raise ValueError(f"Invalid month: {value!r}")


def infer_period(pdf_path: Path) -> tuple[int | None, int | None]:
    """Infer timetable year and month from the PDF text."""
    page_texts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            page_texts.append(text)
            match = PERIOD_RE.search(text)
            if match:
                return int(match.group(2)), month_number(match.group(1))

    text = "\n".join(page_texts)
    month_match = MONTH_TOKEN_RE.search(text)
    month = month_number(month_match.group(1)) if month_match else None
    if not month:
        return None, None

    return infer_year_from_weekdays(text.splitlines(), month), month


def infer_year_from_weekdays(lines: Sequence[str], month: int) -> int | None:
    """Infer year by matching weekday/day pairs."""
    weekday_days: list[tuple[int, int]] = []
    for line in lines:
        weekday_match = WEEKDAY_RE.match(line)
        if not weekday_match:
            continue
        before_first_time = TIME_RE.split(line, maxsplit=1)[0]
        day_matches = DAY_RE.findall(before_first_time)
        if day_matches:
            weekday_days.append((WEEKDAYS[weekday_match.group(1).lower()], int(day_matches[-1])))

    if not weekday_days:
        return None

    scores: Counter[int] = Counter()
    for year in range(2020, 2036):
        for weekday, day in weekday_days:
            try:
                if date(year, month, day).weekday() == weekday:
                    scores[year] += 1
            except ValueError:
                pass
    if not scores:
        return None
    current_year = date.today().year
    year, matches = max(scores.items(), key=lambda item: (item[1], -abs(item[0] - current_year)))
    return year if matches >= 3 else None


def row_from_cells(
    cells: Sequence[str],
    header_map: dict[int, str] | None,
    year: int | None,
    month: int | None,
    date_format: str | None,
) -> PrayerRow | None:
    """Extract a row from table cells."""
    cells = [normalise_cell(cell) for cell in cells]
    if not any(cells):
        return None

    if header_map:
        values: dict[str, str] = {}
        for index, prayer in header_map.items():
            if index < len(cells):
                match = TIME_RE.search(cells[index])
                if match:
                    values[prayer] = normalise_time(match.group(0))
        if all(prayer in values for prayer in PRAYERS):
            day = first_day_from_cells(cells, year, month, date_format, exclude=set(header_map))
            if day is not None:
                return PrayerRow(day, *(values[prayer] for prayer in PRAYERS))

    joined = " ".join(cells)
    times = [normalise_time(match.group(0)) for match in TIME_RE.finditer(joined)]
    if len(times) < 5:
        return None

    first_time_pos = TIME_RE.search(joined)
    date_text = joined[: first_time_pos.start()] if first_time_pos else joined
    day = make_day(date_text, year, month, date_format)
    if day is None:
        day = first_day_from_cells(cells, year, month, date_format, exclude=set())
    if day is None:
        return None

    return PrayerRow(day, *times[:5])


def row_from_weekday_line(
    line: str,
    year: int | None,
    month: int | None,
    date_format: str | None,
    fixed_isha: str | None = None,
) -> PrayerRow | None:
    """Extract a row from weekday-prefixed text lines."""
    if not WEEKDAY_RE.match(line):
        return None

    before_first_time = TIME_RE.split(line, maxsplit=1)[0]
    day_matches = DAY_RE.findall(before_first_time)
    if not day_matches:
        return None

    day = make_day(day_matches[-1], year, month, date_format)
    if day is None:
        return None

    times = [normalise_time(match.group(0)) for match in TIME_RE.finditer(line)]
    isha = fixed_isha
    if len(times) >= 9:
        return PrayerRow(day, times[0], times[3], times[5], times[7], isha or times[7])
    if len(times) == 8:
        return PrayerRow(day, times[0], times[3], times[4], times[6], isha or times[6])
    if len(times) == 7:
        return PrayerRow(day, times[0], times[3], times[4], times[5], isha or times[5])
    if len(times) == 6:
        return PrayerRow(day, times[0], times[2], times[3], times[4], isha or times[4])
    if len(times) >= 5:
        return PrayerRow(day, times[0], times[2], times[3], times[4], isha or times[4])
    return None


def fixed_isha_from_weekday_lines(lines: Sequence[str]) -> str | None:
    """Find a fixed Isha time repeated in weekday lines."""
    candidates: Counter[str] = Counter()
    for line in lines:
        if not WEEKDAY_RE.match(line):
            continue
        times = [normalise_time(match.group(0)) for match in TIME_RE.finditer(line)]
        if len(times) >= 8:
            candidates[times[-1]] += 1
    if not candidates:
        return None
    return candidates.most_common(1)[0][0]


def first_day_from_cells(
    cells: Sequence[str],
    year: int | None,
    month: int | None,
    date_format: str | None,
    exclude: set[int],
) -> date | str | None:
    """Find the first date/day value in table cells."""
    for index, cell in enumerate(cells):
        if index in exclude or TIME_RE.search(cell):
            continue
        day = make_day(cell, year, month, date_format)
        if day is not None:
            return day
    return None


def header_map(cells: Sequence[str]) -> dict[int, str]:
    """Build a map from table column index to prayer."""
    mapping: dict[int, str] = {}
    for index, cell in enumerate(cells):
        prayer = normalise_header(cell)
        if prayer:
            mapping[index] = prayer
    return mapping


def extract_table_rows(
    pdf_path: Path,
    year: int | None,
    month: int | None,
    date_format: str | None,
    debug: bool,
) -> list[PrayerRow]:
    """Extract rows from PDF tables."""
    rows: list[PrayerRow] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_header: dict[int, str] | None = None
            for table in page.extract_tables() or []:
                for raw_cells in table:
                    cells = [normalise_cell(cell) for cell in raw_cells]
                    mapping = header_map(cells)
                    if len(set(mapping.values())) >= 3:
                        page_header = mapping
                        continue
                    row = row_from_cells(cells, page_header, year, month, date_format)
                    if row:
                        rows.append(row)
                    elif debug and any(cells):
                        print(f"Skipped table row on page {page_number}: {cells}", file=sys.stderr)
    return rows


def extract_text_rows(
    pdf_path: Path,
    year: int | None,
    month: int | None,
    date_format: str | None,
    debug: bool,
) -> list[PrayerRow]:
    """Extract rows from PDF text lines."""
    rows: list[PrayerRow] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            lines = text.splitlines()
            fixed_isha = fixed_isha_from_weekday_lines(lines)
            for line in lines:
                row = row_from_weekday_line(line, year, month, date_format, fixed_isha)
                if row is None:
                    row = row_from_cells([line], None, year, month, date_format)
                if row:
                    rows.append(row)
                elif debug and len(TIME_RE.findall(line)) >= 3:
                    print(f"Skipped text line on page {page_number}: {line}", file=sys.stderr)
    return rows


def unique_rows(rows: Iterable[PrayerRow]) -> list[PrayerRow]:
    """Deduplicate and sort extracted rows."""
    seen: set[tuple[object, str, str, str, str, str]] = set()
    unique: list[PrayerRow] = []
    for row in rows:
        key = (row.day, row.fajr, row.dhuhr, row.asr, row.maghrib, row.isha)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return sorted(unique, key=lambda row: row.day.isoformat() if isinstance(row.day, date) else row.day)


def distinct_day_count(rows: Sequence[PrayerRow]) -> int:
    """Count distinct row days."""
    return len({row.day for row in rows})


def extract_prayer_rows(
    pdf_path: Path,
    year: int | None = None,
    month: int | None = None,
    date_format: str | None = None,
    debug: bool = False,
) -> list[PrayerRow]:
    """Extract prayer rows from a PDF using the best available strategy."""
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    # Detect the 13-column monthly timetable before the generic parser.
    # Do not silently fall back if this layout is detected but malformed.
    from .layout_nuneaton import MONTH_HEADING, DAY_ROW, parse_pdf
    with pdfplumber.open(pdf_path) as document:
        layout_detected = any(
            MONTH_HEADING.search(text) and any(DAY_ROW.match(line) for line in text.splitlines())
            for page in document.pages
            if (text := (page.extract_text(layout=True) or ''))
        )
    if layout_detected:
        records = parse_pdf(pdf_path, year)
        return [PrayerRow(
            date.fromisoformat(record['date']),
            *(record[name] for name in PRAYERS),
            *(record[f'{name}_jamaat'] for name in PRAYERS),
            normalized=True,
        ) for record in records]

    if not year or not month:
        inferred_year, inferred_month = infer_period(pdf_path)
        year = year or inferred_year
        month = month or inferred_month

    table_rows = unique_rows(extract_table_rows(pdf_path, year, month, date_format, debug))
    text_rows = unique_rows(extract_text_rows(pdf_path, year, month, date_format, debug))
    rows = text_rows if distinct_day_count(text_rows) > distinct_day_count(table_rows) else table_rows or text_rows
    if not rows:
        raise ValueError("No prayer rows found")
    return rows


def write_csv(rows: Sequence[PrayerRow], output_path: Path) -> None:
    """Write extracted prayer rows to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(("date", *PRAYERS, *(f"{name}_jamaat" for name in PRAYERS)))
        for row in rows:
            day = row.day.isoformat() if isinstance(row.day, date) else row.day
            writer.writerow((day,
                *(getattr(row, prayer) if row.normalized else output_time(getattr(row, prayer), prayer) for prayer in PRAYERS),
                *(getattr(row, f"{prayer}_jamaat") or "" for prayer in PRAYERS)))
