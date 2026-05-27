#!/usr/bin/env python3
"""Scaffold a trip folder so the user has to do as little setup as possible.

The user creates a folder named like `20260901_Cargese_MecaNano-school/` and
drops invitations / programmes / bookings / receipts into it. This script then:

  1. Creates the canonical subfolders (1_Invitation/, 2_Application/, …) if missing.
  2. Copies `templates/trip.md.tmpl` into the folder as `trip.md` if missing.
  3. Pre-fills the YAML header of trip.md with what can be inferred from the
     folder name: start date (yyyymmdd → ISO), location, event name.

The script is idempotent: running it twice does nothing the second time.
File-sorting (deciding which dropped file goes into which subfolder) is left
to the LLM agent — that needs judgement and the agent is good at it.

Usage:
    python bootstrap_trip.py <trip-folder> [--template <path>]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SUBFOLDERS = [
    "1_Invitation",
    "2_Application",
    "3_Booking",
    "receipts",
    "5_Expense_Report",
    "6_Followup",
]

DEFAULT_TEMPLATE = (Path(__file__).resolve().parent.parent
                    / "templates" / "trip.md.tmpl")


def parse_folder_name(name: str):
    """Extract (iso_date, location, event_guess) from a trip-folder name.

    Returns (date_iso or None, location or None, event or None).

    Recognized shapes:
      20260901_Cargese_MecaNano-school
      20260522-FAU-Erlangen
      2026-09-01_Cargese_MecaNano-school
    """
    # 1. Compact 8-digit date with _ or - separator
    m = re.match(r"^(\d{4})(\d{2})(\d{2})[_\-](.+)$", name)
    if not m:
        # 2. Hyphenated ISO date prefix
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[_\-](.+)$", name)
    if not m:
        return None, None, None

    year, mon, day, rest = m.groups()
    iso = f"{year}-{mon}-{day}"

    # Split `rest` on _ or - to get (location, event). First token is location
    # (typically a city), remainder joined back as event.
    parts = re.split(r"[_\-]", rest, maxsplit=1)
    if len(parts) == 1:
        return iso, parts[0] or None, None
    location, event = parts[0] or None, parts[1].replace("-", " ").replace("_", " ").strip() or None
    return iso, location, event


def prefill_trip_md(content: str, *, iso_date=None, location=None, event=None) -> str:
    """Replace placeholder values in the trip.md YAML header with what we know."""
    if iso_date:
        content = re.sub(r"^datum_start: YYYY-MM-DD.*$",
                         f"datum_start: {iso_date}",
                         content, count=1, flags=re.MULTILINE)
    if location:
        # location may be e.g. "Cargese" — the trip.md template comment suggests
        # "Cargèse, Frankreich" so we don't try to second-guess the country here.
        content = re.sub(r'^ziel: ""(\s+#.*)?$',
                         f'ziel: "{location}"\\1',
                         content, count=1, flags=re.MULTILINE)
    if event:
        content = re.sub(r'^event: ""(\s+#.*)?$',
                         f'event: "{event}"\\1',
                         content, count=1, flags=re.MULTILINE)
    return content


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trip_folder", help="Path to the trip folder.")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                    help="Path to trip.md.tmpl (default: bundled template).")
    args = ap.parse_args()

    trip = Path(args.trip_folder).resolve()
    if not trip.exists():
        sys.exit(f"Trip folder does not exist: {trip}")
    if not trip.is_dir():
        sys.exit(f"Not a directory: {trip}")

    created_subfolders = []
    for sf in SUBFOLDERS:
        path = trip / sf
        if not path.exists():
            path.mkdir(parents=True)
            created_subfolders.append(sf)

    trip_md = trip / "trip.md"
    trip_md_action = None
    if not trip_md.exists():
        tmpl = Path(args.template)
        if not tmpl.exists():
            sys.exit(f"trip.md template not found: {tmpl}")
        content = tmpl.read_text(encoding="utf-8")
        iso_date, location, event = parse_folder_name(trip.name)
        content = prefill_trip_md(content,
                                  iso_date=iso_date,
                                  location=location,
                                  event=event)
        trip_md.write_text(content, encoding="utf-8")
        prefilled = [k for k, v in dict(date=iso_date, location=location,
                                        event=event).items() if v]
        trip_md_action = (f"created (pre-filled: {', '.join(prefilled)})"
                          if prefilled else "created")

    # Brief summary
    print(f"Trip folder: {trip}")
    if created_subfolders:
        print(f"Created subfolders: {', '.join(created_subfolders)}")
    else:
        print("Subfolders: already present.")
    if trip_md_action:
        print(f"trip.md: {trip_md_action}")
    else:
        print("trip.md: already present, left alone.")

    # List any loose files at the top level so the LLM agent knows what's there
    # to sort into the subfolders.
    loose = sorted(
        p for p in trip.iterdir()
        if p.is_file() and p.name not in ("trip.md", ".DS_Store")
    )
    if loose:
        print(f"\nLoose files at top level ({len(loose)}) — to be sorted into subfolders:")
        for p in loose:
            print(f"  {p.name}")


if __name__ == "__main__":
    main()
