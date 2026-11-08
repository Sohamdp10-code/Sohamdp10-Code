#!/usr/bin/env python3
"""Build a self-hosted SVG from GitHub's public contribution calendar."""

from __future__ import annotations

from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import os
import re
import sys


USERNAME = os.environ.get("GITHUB_USERNAME", "Sohamdp10-code")
OUTPUT = Path("activity-graph.svg")
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39ff14"]


class ContributionParser(HTMLParser):
    """Extract GitHub's public calendar cells without third-party packages."""

    def __init__(self) -> None:
        super().__init__()
        self.days: dict[date, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "td":
            return

        attributes = dict(attrs)
        raw_date = attributes.get("data-date")
        raw_level = attributes.get("data-level")
        if not raw_date or raw_level is None:
            return

        try:
            parsed_date = date.fromisoformat(raw_date)
            level = int(raw_level)
        except (TypeError, ValueError):
            return

        if 0 <= level <= 4:
            self.days[parsed_date] = level


def fetch_calendar(username: str) -> tuple[str, dict[date, int]]:
    url = f"https://github.com/users/{username}/contributions"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; GitHub-Profile-Graph/1.0)",
            "Accept": "text/html",
        },
    )

    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub returned HTTP {response.status}")
        html = response.read().decode("utf-8", errors="replace")

    parser = ContributionParser()
    parser.feed(html)

    if len(parser.days) < 300:
        raise RuntimeError(
            "GitHub returned fewer than 300 contribution-day cells; "
            "the page may have changed or returned an incomplete response."
        )

    return html, parser.days


def build_svg(html: str, days: dict[date, int]) -> str:
    latest = max(days)
    # Align the 53-week grid to Sunday through Saturday.
    grid_end = latest + timedelta(days=(5 - latest.weekday()) % 7)
    grid_start = grid_end - timedelta(days=370)

    width = 780
    height = 190
    left = 54
    top = 58
    cell = 10
    step = 13

    total_match = re.search(
        r"([\d,]+)\s+contributions?\s+in the last year", html, re.IGNORECASE
    )
    total_text = (
        f"{total_match.group(1)} contributions in the last year"
        if total_match
        else "GitHub public contribution calendar"
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="title description">',
        '<title id="title">Soham GitHub contribution activity</title>',
        '<desc id="description">A 53-week contribution heatmap generated from the public GitHub profile.</desc>',
        '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
        '<text x="18" y="25" fill="#39ff14" font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="13" font-weight="700">SOHAM // CONTRIBUTION ACTIVITY</text>',
        f'<text x="18" y="43" fill="#8b949e" font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="10">{total_text} · refreshed {date.today().isoformat()}</text>',
    ]

    # Month labels, placed at the first visible week of each month.
    seen_month_weeks: set[int] = set()
    current = grid_start
    while current <= grid_end:
        if current.day == 1:
            week = (current - grid_start).days // 7
            if week not in seen_month_weeks:
                parts.append(
                    f'<text x="{left + week * step}" y="55" fill="#8b949e" '
                    f'font-family="ui-monospace, SFMono-Regular, Consolas, monospace" '
                    f'font-size="9">{current.strftime("%b")}</text>'
                )
                seen_month_weeks.add(week)
        current += timedelta(days=1)

    # Weekday labels: Monday, Wednesday, Friday.
    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = top + row * step + 8
        parts.append(
            f'<text x="18" y="{y}" fill="#8b949e" font-family="ui-monospace, '
            f'SFMono-Regular, Consolas, monospace" font-size="9">{label}</text>'
        )

    for offset in range(371):
        day = grid_start + timedelta(days=offset)
        week = offset // 7
        weekday = offset % 7  # Sunday = first row
        level = days.get(day, 0)
        x = left + week * step
        y = top + weekday * step
        color = PALETTE[level]
        tooltip = f"{day.isoformat()}: contribution level {level}"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{color}" stroke="#30363d" stroke-width="0.35">'
            f'<title>{tooltip}</title></rect>'
        )

    # Legend.
    legend_y = 166
    parts.append(
        '<text x="596" y="175" fill="#8b949e" font-family="ui-monospace, '
        'SFMono-Regular, Consolas, monospace" font-size="9">Less</text>'
    )
    for index, color in enumerate(PALETTE):
        x = 624 + index * 14
        parts.append(
            f'<rect x="{x}" y="{legend_y}" width="10" height="10" rx="2" '
            f'fill="{color}" stroke="#30363d" stroke-width="0.35"/>'
        )
    parts.append(
        '<text x="704" y="175" fill="#8b949e" font-family="ui-monospace, '
        'SFMono-Regular, Consolas, monospace" font-size="9">More</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    try:
        html, days = fetch_calendar(USERNAME)
        svg = build_svg(html, days)
        OUTPUT.write_text(svg, encoding="utf-8")
        print(f"Generated {OUTPUT} with {len(days)} contribution days for {USERNAME}.")
        return 0
    except Exception as error:  # Fail the workflow; never replace a good graph with junk.
        print(f"Could not generate the contribution graph: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
