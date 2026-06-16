# 60 — Calendar entry (Kerio Connect via CalDAV)

Adds a trip to Erik's Kerio Connect calendar as an all-day block over the
travel period. **On-demand only, and always with a confirmation step.**

## Trigger

The user explicitly asks for it — e.g. "put this trip in my calendar",
"trag das in den Kalender ein", "add Cargèse to my calendar". The pilot does
**not** do this automatically as part of `10_new_trip` or any other flow.

## Behavior — confirm first, always

This mode is confirmation-first by design (Erik's instruction). Never push
silently.

1. **Read the trip's `trip.md`** YAML header (`event`, `ziel`, `datum_start`,
   `datum_ende`, `reisenummer`, `reisezweck_kurz`, `event_url`, `status`).
2. **Run the preview (dry-run):**

   ```bash
   python scripts/add_to_calendar.py <trip-folder>
   ```

   This sends nothing — it only prints the proposed event (summary, dates,
   location, reminder, target calendar).

   **All-day is the default** (the whole travel period). If Erik gives times,
   build a **timed** event instead with `--start` / `--end`:

   ```bash
   # times applied to the trip's start/end dates:
   python scripts/add_to_calendar.py <trip-folder> --start 09:00 --end 17:00
   # explicit date + time (e.g. a single talk slot):
   python scripts/add_to_calendar.py <trip-folder> --start "2026-09-01 14:00" --end "2026-09-01 18:30"
   ```

   `--start` / `--end` accept `YYYY-MM-DD`, `YYYY-MM-DD HH:MM`, or `HH:MM`.
   A time on either side makes it a timed event — then **both** sides need a
   time. Date-only on both sides stays all-day (just overrides the dates).
   Reminder override: `--reminder 0|30m|2h|1d` (default comes from
   `identity.yaml` `alarm_days_before`, currently 0 = no reminder).
3. **Show the proposed event in chat and ask back.** One short confirmation:
   "I'll add this to your Kerio calendar — *Dienstreise: <event> (<ziel>)*,
   <start> → <end>, all day, reminder 1 day before. OK to push?"
   If anything is off (dates, all-day vs. timed, reminder), the user corrects
   in one reply.
4. **Only after an explicit yes**, push:

   ```bash
   python scripts/add_to_calendar.py <trip-folder> --confirm
   ```
5. **Report** the result (which calendar) in one line. Note in the trip's
   `trip.md` daily log / follow-up that the calendar entry was created.

## Notes

- The event UID is derived from the trip folder name, so re-running **updates**
  the same event instead of creating a duplicate. Safe to re-push after a date
  change.
- All-day block by default (DTEND is exclusive — the script handles the +1 day).
  Timed events are supported via `--start` / `--end` (Europe/Berlin, they mark
  you busy / OPAQUE); use them for actual program or talk times.
- **Target calendar: `CM_Absence`** (owned by `cm-office`, shared to Erik with
  write access). Set via `identity.yaml` `kalender:` `calendar_name: CM_Absence`
  + `shared_owner: cm-office`. The script searches Erik's own calendars first,
  then the owner's home. To confirm it's visible/writable or to grab its exact
  URL, run `python scripts/add_to_calendar.py --list-calendars`; if name-matching
  fails, paste the URL into `calendar_url:`. `--delete --confirm` removes an event.
- Credentials come from `identity.yaml` `kalender:` (local, never in the repo).
  If the `app_password` is still the placeholder, the push fails with a clear
  message — tell Erik to generate a Kerio app password and paste it in.
- Server reachability: the push needs `xmail1.mpie.de` reachable over HTTPS
  (institute network / VPN if accessed from outside).
