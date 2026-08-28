"""Scrapes the UW Waterloo Schedule of Classes and reports seat availability
for a given section.

The public endpoint returns an HTML page containing one outer table per
course, each wrapping an inner table whose rows describe individual sections
(components) such as "LEC 001" or "TST 081". We locate the inner table by its
column headers so the parser keeps working even if column order shifts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://classes.uwaterloo.ca/cgi-bin/cgiwrap/infocour/salook.pl"

# Headers of the inner section table, used to find it and to locate columns.
_REQUIRED_HEADERS = {"comp sec", "enrl cap", "enrl tot"}


@dataclass
class Section:
    """A single course component (section)."""

    component: str  # e.g. "LEC", "TST", "LAB"
    number: str  # e.g. "081", "001"
    enrol_cap: int
    enrol_total: int
    raw_comp_sec: str  # e.g. "LEC 081"

    @property
    def seats_open(self) -> int:
        return max(self.enrol_cap - self.enrol_total, 0)

    @property
    def has_seat(self) -> bool:
        return self.enrol_total < self.enrol_cap


class ScrapeError(RuntimeError):
    """Raised when the page cannot be fetched or parsed as expected."""


def build_url(subject: str, course_number: str, level: str, session: str) -> str:
    params = {
        "level": level,
        "sess": session,
        "subject": subject.upper(),
        "cournum": course_number,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{BASE_URL}?{query}"


def fetch_html(
    subject: str, course_number: str, level: str, session: str, timeout: int = 30
) -> str:
    url = build_url(subject, course_number, level, session)
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:  # network / HTTP error
        raise ScrapeError(f"Failed to fetch {url}: {exc}") from exc
    return response.text


def _find_section_table(soup: BeautifulSoup):
    """Return the inner <table> whose header row contains the required headers."""
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row is None:
            continue
        headers = {
            th.get_text(strip=True).lower() for th in header_row.find_all("th")
        }
        if _REQUIRED_HEADERS.issubset(headers):
            return table
    return None


def _header_index_map(header_row) -> dict[str, int]:
    return {
        th.get_text(strip=True).lower(): i
        for i, th in enumerate(header_row.find_all("th"))
    }


def _to_int(text: str) -> int | None:
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else None


def parse_sections(html: str) -> list[Section]:
    """Parse every section (component) row from the schedule HTML."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_section_table(soup)
    if table is None:
        raise ScrapeError(
            "Could not find the section table. The course/term may be invalid, "
            "or the page layout changed."
        )

    rows = table.find_all("tr")
    header_row = rows[0]
    idx = _header_index_map(header_row)
    comp_i = idx["comp sec"]
    cap_i = idx["enrl cap"]
    tot_i = idx["enrl tot"]

    sections: list[Section] = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) <= max(comp_i, cap_i, tot_i):
            continue  # skip note/reserve rows that don't have full columns

        comp_sec = cells[comp_i].get_text(strip=True)
        cap = _to_int(cells[cap_i].get_text())
        tot = _to_int(cells[tot_i].get_text())
        if not comp_sec or cap is None or tot is None:
            continue

        parts = comp_sec.split()
        component = parts[0] if parts else comp_sec
        number = parts[1] if len(parts) > 1 else ""
        sections.append(
            Section(
                component=component,
                number=number,
                enrol_cap=cap,
                enrol_total=tot,
                raw_comp_sec=comp_sec,
            )
        )
    return sections


def _section_matches(section: Section, target: str) -> bool:
    """Match a target like "81" against a section number like "081".

    Compares numerically when both sides are numbers, else falls back to a
    substring match against the raw "Comp Sec" text.
    """
    target = target.strip()
    if section.number.isdigit() and target.isdigit():
        return int(section.number) == int(target)
    return target.lower() in section.raw_comp_sec.lower()


def find_sections(sections: list[Section], target: str) -> list[Section]:
    """Return all sections matching the target section number."""
    return [s for s in sections if _section_matches(s, target)]


def check_availability(
    subject: str,
    course_number: str,
    section: str,
    level: str,
    session: str,
) -> list[Section]:
    """Fetch the page and return the matching section(s).

    Raises ScrapeError if the page can't be parsed or the section isn't found.
    """
    html = fetch_html(subject, course_number, level, session)
    all_sections = parse_sections(html)
    matches = find_sections(all_sections, section)
    if not matches:
        available = ", ".join(s.raw_comp_sec for s in all_sections) or "(none)"
        raise ScrapeError(
            f"Section '{section}' not found for {subject.upper()} {course_number}. "
            f"Available sections: {available}"
        )
    return matches
