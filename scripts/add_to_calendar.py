#!/usr/bin/env python3
"""Push a trip into the user's Kerio Connect calendar via CalDAV.

Reads the YAML header of a trip's `trip.md`, builds an iCalendar VEVENT and
uploads it to the user's Kerio Connect calendar over CalDAV.

By default the event is an **all-day block** spanning the travel period
(`datum_start` … `datum_ende` from trip.md). You can instead give explicit
start/end times and/or dates with `--start` / `--end` to create a **timed**
event (e.g. the actual conference hours).

The script is confirmation-first: by default it only prints what it WOULD
create (dry-run). Nothing is sent until you pass `--confirm`.

The event UID is derived from the trip folder name, so running again UPDATES
the same event instead of creating a duplicate.

Usage:
    # All-day over the whole trip (default), preview then push:
    python add_to_calendar.py <trip-folder>
    python add_to_calendar.py <trip-folder> --confirm

    # Timed event — give times (applied to the trip's start/end dates):
    python add_to_calendar.py <trip-folder> --start 09:00 --end 17:00 --confirm

    # Timed event with explicit dates + times:
    python add_to_calendar.py <trip-folder> \
        --start "2026-09-01 14:00" --end "2026-09-01 18:30" --confirm

    # All-day but with overridden dates (date-only, no time):
    python add_to_calendar.py <trip-folder> --start 2026-09-02 --end 2026-09-04

--start / --end accept any of:
    YYYY-MM-DD              a date            (date-only on both sides -> all-day)
    YYYY-MM-DD HH:MM        a date + time     (-> timed event)
    HH:MM                   a time only       (combined with the trip's start/end date -> timed)

Reminder:
    --reminder <spec>   override the reminder. Forms: 0 (off), 30m, 2h, 1d.
                        Default comes from identity.yaml / config `alarm_days_before`.

Calendar credentials and server come from identity.yaml `kalender:` (personal,
local, git-ignored), falling back to config/mpi-susmat.yaml `kalender:` defaults.
"""
from __future__ import annotations

import argparse
import datetime as dt
import platform
import subprocess
import sys
from pathlib import Path


def _ask_password_gui(prompt: str) -> str:
    """Show a native GUI password dialog without echoing input.

    Platform strategy:
      macOS   → osascript  (native Cocoa sheet, hidden input)
      Linux   → zenity → kdialog → tkinter → getpass fallback
      Windows → tkinter   → getpass fallback

    The password is never written to any file or environment variable.
    """
    system = platform.system()

    if system == "Darwin":
        script = (
            f'display dialog "{prompt}" '
            f'default answer "" with hidden answer '
            f'buttons {{"Cancel", "OK"}} default button "OK" '
            f'with title "Travel Forms Pilot"'
        )
        try:
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                sys.exit("Password entry cancelled.")
            for part in r.stdout.strip().split(", "):
                if part.startswith("text returned:"):
                    return part[len("text returned:"):]
            sys.exit("Could not parse osascript response.")
        except FileNotFoundError:
            pass  # osascript missing — fall through

    elif system == "Windows":
        try:
            import tkinter as tk
            from tkinter import simpledialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", True)
            pw = simpledialog.askstring("Travel Forms Pilot", prompt,
                                        show="*", parent=root)
            root.destroy()
            if pw is None:
                sys.exit("Password entry cancelled.")
            return pw
        except Exception:
            pass  # tkinter unavailable — fall through

    else:  # Linux
        for cmd in (
            ["zenity", "--password", "--title=Travel Forms Pilot"],
            ["kdialog", "--password", prompt, "--title", "Travel Forms Pilot"],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    return r.stdout.rstrip("\n")
                sys.exit("Password entry cancelled.")
            except FileNotFoundError:
                continue
        try:
            import tkinter as tk
            from tkinter import simpledialog
            root = tk.Tk()
            root.withdraw()
            pw = simpledialog.askstring("Travel Forms Pilot", prompt,
                                        show="*", parent=root)
            root.destroy()
            if pw is None:
                sys.exit("Password entry cancelled.")
            return pw
        except Exception:
            pass  # fall through to getpass

    # Last resort: terminal prompt (hidden input)
    import getpass
    return getpass.getpass(f"{prompt}: ")

try:
    import yaml
except ImportError:
    sys.stderr.write("Missing dependency: pip install pyyaml --break-system-packages\n")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "mpi-susmat.yaml"
# identity.yaml lives one level ABOVE the repo so it never gets committed.
DEFAULT_IDENTITY = REPO_ROOT.parent / "identity.yaml"
LOCAL_TZ = "Europe/Berlin"


# ----------------------------------------------------------------------------- parsing

def parse_trip_md(path: Path) -> dict:
    """Return the YAML header (front matter) of a trip.md as a dict."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        sys.exit(f"{path} has no YAML front matter (expected to start with '---').")
    parts = text.split("---", 2)
    if len(parts) < 3:
        sys.exit(f"{path}: could not find the closing '---' of the YAML header.")
    return yaml.safe_load(parts[1]) or {}


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_calendar_settings(args, identity: dict, config: dict) -> dict:
    """Merge calendar settings from CLI / identity.yaml / config defaults."""
    id_cal = (identity or {}).get("kalender", {}) or {}
    cfg_cal = (config or {}).get("kalender", {}) or {}

    def pick(key, default=None):
        return cfg_cal.get(key, default)

    settings = {
        "caldav_url": args.caldav_url or id_cal.get("caldav_url"),
        "login": args.login or id_cal.get("login"),
        "app_password": id_cal.get("app_password"),
        "calendar_name": args.calendar_name or id_cal.get("calendar_name") or pick("calendar_name"),
        "alarm_days_before": id_cal.get("alarm_days_before", pick("alarm_days_before", 1)),
    }
    if not settings["caldav_url"]:
        pattern = pick("caldav_url_pattern")
        host = pick("host")
        domain = pick("domain") or id_cal.get("domain")
        login = settings["login"]
        if pattern and host and domain and login:
            settings["caldav_url"] = pattern.format(host=host, domain=domain, login=login)
    return settings


# ----------------------------------------------------------------------------- date/time helpers

def iso_to_date(value, field: str) -> dt.date:
    if isinstance(value, dt.date):
        return value
    if value in (None, "", "YYYY-MM-DD"):
        sys.exit(f"trip.md header field `{field}` is empty — cannot build a calendar event.")
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        sys.exit(f"trip.md field `{field}` = {value!r} is not an ISO date (YYYY-MM-DD).")


def parse_endpoint(value: str):
    """Parse a --start/--end value into ('datetime'|'date'|'time', obj)."""
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return "datetime", dt.datetime.strptime(value, fmt)
        except ValueError:
            pass
    try:
        return "date", dt.date.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return "time", dt.datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    sys.exit(f"Could not parse {value!r}. Use YYYY-MM-DD, 'YYYY-MM-DD HH:MM', or HH:MM.")


def parse_reminder(spec: str):
    """Parse a reminder spec like '0', '30m', '2h', '1d' into a timedelta or None."""
    spec = str(spec).strip().lower()
    if spec in ("0", "", "off", "none"):
        return None
    unit = spec[-1]
    try:
        n = int(spec[:-1]) if unit in "mhd" else int(spec)
    except ValueError:
        sys.exit(f"Could not parse --reminder {spec!r}. Use 0, 30m, 2h, or 1d.")
    if unit == "m":
        return dt.timedelta(minutes=n)
    if unit == "h":
        return dt.timedelta(hours=n)
    # 'd' or a bare number -> days
    return dt.timedelta(days=n)


def resolve_window(header: dict, start_arg, end_arg):
    """Return (start, end, all_day).

    start/end are dt.date (all-day) or tz-aware dt.datetime (timed).
    For all-day, `end` is the LAST day (inclusive); DTEND handling is done later.
    """
    trip_start = iso_to_date(header.get("datum_start"), "datum_start")
    trip_end = iso_to_date(header.get("datum_ende"), "datum_ende")

    if not start_arg and not end_arg:
        if trip_end < trip_start:
            sys.exit(f"datum_ende ({trip_end}) is before datum_start ({trip_start}).")
        return trip_start, trip_end, True

    s_kind, s_val = parse_endpoint(start_arg) if start_arg else ("date", trip_start)
    e_kind, e_val = parse_endpoint(end_arg) if end_arg else ("date", trip_end)

    # Resolve each side to either a date or a (date, time) pair.
    def base_date(kind, val, fallback):
        if kind == "datetime":
            return val.date()
        if kind == "date":
            return val
        return fallback  # time-only -> use the trip date

    s_date = base_date(s_kind, s_val, trip_start)
    e_date = base_date(e_kind, e_val, trip_end)
    s_time = s_val.time() if s_kind == "datetime" else (s_val if s_kind == "time" else None)
    e_time = e_val.time() if e_kind == "datetime" else (e_val if e_kind == "time" else None)

    timed = s_time is not None or e_time is not None
    if not timed:
        if e_date < s_date:
            sys.exit(f"end date ({e_date}) is before start date ({s_date}).")
        return s_date, e_date, True

    # Timed: both sides need a time.
    if s_time is None or e_time is None:
        sys.exit("For a timed event give a time on BOTH --start and --end "
                 "(e.g. --start 09:00 --end 17:00).")
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(LOCAL_TZ)
    except Exception:
        tz = None
    start_dt = dt.datetime.combine(s_date, s_time, tzinfo=tz)
    end_dt = dt.datetime.combine(e_date, e_time, tzinfo=tz)
    if end_dt <= start_dt:
        sys.exit(f"end ({end_dt}) must be after start ({start_dt}).")
    return start_dt, end_dt, False


# ----------------------------------------------------------------------------- event build

def build_event(header: dict, trip_folder: Path, start, end, all_day: bool, reminder):
    """Return (ical_text, summary, display_when, uid)."""
    try:
        from icalendar import Calendar, Event, Alarm
    except ImportError:
        sys.stderr.write(
            "Missing dependency: pip install caldav icalendar --break-system-packages\n")
        sys.exit(2)

    event_name = (header.get("event") or "").strip()
    ziel = (header.get("ziel") or "").strip()

    summary = "Dienstreise"
    if event_name:
        summary += f": {event_name}"
    if ziel:
        summary += f" ({ziel})"

    uid = f"travel-forms-pilot-{trip_folder.name}@mpie.de"

    desc_lines = []
    if header.get("reisenummer"):
        desc_lines.append(f"Reisenummer: {header['reisenummer']}")
    if header.get("status"):
        desc_lines.append(f"Status: {header['status']}")
    if header.get("reisezweck_kurz"):
        desc_lines.append(f"Zweck: {header['reisezweck_kurz']}")
    if header.get("event_url"):
        desc_lines.append(f"Event: {header['event_url']}")
    if header.get("abrechnungsfrist"):
        desc_lines.append(f"Abrechnungsfrist: {header['abrechnungsfrist']}")
    desc_lines.append(f"Ordner: {trip_folder}")
    description = "\n".join(desc_lines)

    cal = Calendar()
    cal.add("prodid", "-//travel-forms-pilot//add_to_calendar//EN")
    cal.add("version", "2.0")

    ev = Event()
    ev.add("uid", uid)
    ev.add("summary", summary)
    if all_day:
        # All-day: DTEND is exclusive -> last day + 1.
        ev.add("dtstart", start)
        ev.add("dtend", end + dt.timedelta(days=1))
        ev.add("transp", "TRANSPARENT")   # don't block free/busy for a multi-day block
        display_when = (f"{start.isoformat()} (all day)" if start == end
                        else f"{start.isoformat()} → {end.isoformat()} (all day, inclusive)")
    else:
        ev.add("dtstart", start)
        ev.add("dtend", end)
        ev.add("transp", "OPAQUE")        # timed entries mark you busy
        if start.date() == end.date():
            display_when = (f"{start.date().isoformat()} "
                            f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}")
        else:
            display_when = (f"{start.strftime('%Y-%m-%d %H:%M')} → "
                            f"{end.strftime('%Y-%m-%d %H:%M')}")

    if ziel:
        ev.add("location", ziel)
    ev.add("description", description)
    ev.add("dtstamp", dt.datetime.now(dt.timezone.utc))

    if reminder is not None:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", summary)
        alarm.add("trigger", -reminder)
        ev.add_component(alarm)

    cal.add_component(ev)
    return cal.to_ical().decode("utf-8"), summary, display_when, uid


# ----------------------------------------------------------------------------- upload

def push_to_caldav(settings: dict, ical_text: str) -> str:
    try:
        import caldav
    except ImportError:
        sys.stderr.write("Missing dependency: pip install caldav --break-system-packages\n")
        sys.exit(2)

    url, login, pw = settings["caldav_url"], settings["login"], settings.get("app_password")
    for k, v in (("caldav_url", url), ("login", login)):
        if not v:
            sys.exit(f"Calendar setting `{k}` is missing — set it in identity.yaml `kalender:`.")
    if not pw or str(pw).startswith("PASTE_"):
        pw = _ask_password_gui(f"Kerio password for {login}:")

    client = caldav.DAVClient(url=url, username=login, password=pw)
    principal = client.principal()
    calendars = principal.calendars()
    wanted = settings.get("calendar_name")
    calendar = None
    if wanted:
        for c in calendars:
            name = getattr(c, "name", None) or (c.get_properties() or {}).get("{DAV:}displayname")
            if name and str(name).strip().lower() == str(wanted).strip().lower():
                calendar = c
                break
        if calendar is None:
            names = ", ".join(str(getattr(c, "name", "?")) for c in calendars)
            sys.exit(f"Calendar named {wanted!r} not found. Available: {names}")
    else:
        if not calendars:
            sys.exit("No calendars found for this principal.")
        calendar = calendars[0]

    calendar.save_event(ical_text)  # UID-based upsert (create or update)
    return getattr(calendar, "name", None) or "default calendar"


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trip_folder", help="Path to the trip folder (containing trip.md).")
    ap.add_argument("--confirm", action="store_true",
                    help="Actually push to the server. Without it the script only previews.")
    ap.add_argument("--start", default=None,
                    help="Override start: date, 'date HH:MM', or HH:MM. A time -> timed event.")
    ap.add_argument("--end", default=None,
                    help="Override end: date, 'date HH:MM', or HH:MM. A time -> timed event.")
    ap.add_argument("--reminder", default=None,
                    help="Reminder override: 0 (off), 30m, 2h, 1d. Default from config.")
    ap.add_argument("--caldav-url", default=None, help="Override the CalDAV URL.")
    ap.add_argument("--login", default=None, help="Override the login name.")
    ap.add_argument("--calendar-name", default=None,
                    help="Target calendar display name (default: principal's first calendar).")
    ap.add_argument("--identity", default=str(DEFAULT_IDENTITY),
                    help="Path to identity.yaml (default: one level above the repo).")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG),
                    help="Path to config/mpi-susmat.yaml.")
    args = ap.parse_args()

    trip = Path(args.trip_folder).resolve()
    trip_md = trip / "trip.md"
    if not trip_md.exists():
        sys.exit(f"No trip.md in {trip}. Run bootstrap_trip.py first.")

    header = parse_trip_md(trip_md)
    identity = load_yaml(Path(args.identity))
    config = load_yaml(Path(args.config))
    settings = resolve_calendar_settings(args, identity, config)

    start, end, all_day = resolve_window(header, args.start, args.end)

    if args.reminder is not None:
        reminder = parse_reminder(args.reminder)
    else:
        days = settings.get("alarm_days_before", 1)
        reminder = dt.timedelta(days=int(days)) if days and int(days) > 0 else None

    ical_text, summary, display_when, uid = build_event(
        header, trip, start, end, all_day, reminder)

    print("Proposed calendar event")
    print("-----------------------")
    print(f"  Summary : {summary}")
    print(f"  When    : {display_when}")
    if header.get("ziel"):
        print(f"  Location: {header['ziel']}")
    if reminder is None:
        print("  Reminder: none")
    else:
        total = int(reminder.total_seconds())
        human = (f"{total // 86400}d" if total % 86400 == 0
                 else f"{total // 3600}h" if total % 3600 == 0
                 else f"{total // 60}m")
        print(f"  Reminder: {human} before start")
    print(f"  UID     : {uid}  (re-runs update this event, no duplicate)")
    print(f"  Calendar: {settings.get('caldav_url') or '(unset — set in identity.yaml)'}")

    if not args.confirm:
        print("\nDRY-RUN — nothing sent. Re-run with --confirm to push to the calendar.")
        return

    cal_name = push_to_caldav(settings, ical_text)
    print(f"\nPushed to Kerio Connect calendar: {cal_name}")


if __name__ == "__main__":
    main()
