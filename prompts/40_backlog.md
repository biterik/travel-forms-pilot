# 40 — Backlog import (old trips)

Brings an **already-completed** trip folder into the pilot's convention so it
shows up in records / the dashboard. Lenient by design: recover what's easily
recoverable, don't chase perfection, never destroy anything.

## Trigger

The user points at an old trip folder and asks to "import", "back-fill",
"read in", or "catch up" old Dienstreisen — e.g. "import 20230425_Madrid_MecaNano",
"read in my old trips". Scope of this version: **single-trip folders only**
(one trip per folder). Year-aggregator folders that hold many trips
(e.g. `2025_FAU`, `2024_DFG`) and the loose `Bitzek_DR####_*.pdf` settlement
PDFs at the `TRAVEL-FORMS` top level are **not** handled yet — flag them and skip.

## Behavior — ALWAYS preview the gleaned facts before writing anything

**Preview is the default. Never write/move on an old folder without first
showing the user the gleaned facts and what's missing, and getting an OK.**

1. **Preview** (the default — changes nothing):

   ```bash
   python scripts/backlog_trip.py <trip-folder>
   ```

   It prints three blocks: **Gleaned facts** (status + why, trip number, event,
   destination, dates, Abrechnungsfrist, cost center, purpose — each tagged with
   where it came from: `[application]`, `[folder name]`, `[default]` — plus the
   **milestones** it could verify), a **Missing / needs checking** block (every
   field it couldn't determine or only guessed), and the **changes it would
   make** (subfolders, trip.md, file moves, files left at the top level).

2. **Present that to the user per folder** and sanity-check, especially:
   - **status** — `closed` only when there's settlement (DR-Abrechnung) proof on
     file; every old import that isn't clearly closed defaults to `open-unsure`.
     The `milestones:` block carries the detail (antrag, genehmigt, gebucht,
     event, abrechnung, erstattet). A `_Vorlage`/template expense file is **not**
     proof of filing, so `abrechnung_eingereicht` stays blank in that case.
   - **destination / event** — old folders are sometimes named
     `EVENT_LOCATION` instead of `LOCATION_EVENT`, so `ziel` and `event` can be
     swapped or rough. A `[folder name]` tag on either means "verify".
   - **dates** — a `[folder name]` tag means no application dates were read; the
     end date was assumed equal to the start. Verify multi-day trips.
   - **anything in the Missing block**, and the files it would leave behind.

3. **Only after the user confirms**, apply:

   ```bash
   python scripts/backlog_trip.py <trip-folder> --confirm
   ```

   If the preview got a field wrong or left it blank, correct it on the same
   command instead of hand-editing afterwards:

   ```bash
   python scripts/backlog_trip.py <trip-folder> --confirm \
       --status completed --event "3rd SupERBO Symposium on Superalloys"
   ```

   `--status` overrides the inferred status; `--event` sets the event name
   (handy when the folder uses a `yyyymm` name that can't be parsed). Then move
   any leftover ambiguous files by hand and patch anything else directly.

When importing several folders, **preview them all first and present a short
per-folder summary of facts + gaps**, then apply `--confirm` to the ones the
user approves. Don't write any folder before its facts have been shown.

## Notes

- **Non-destructive:** a file is only moved if no same-named file is already in
  the target subfolder; `trip.md` is never overwritten unless you pass
  `--force-trip-md`. Re-runs are safe and idempotent (detection scans
  subfolders too, so status stays correct after files are sorted).
- **No form regeneration.** Backlog never rebuilds the application or expense
  report — the trip is done. It only records and tidies.
- `trip.md` is marked `backlog_imported: true` with the import date.
- Bonus points are left blank — ask the user only if they want to back-fill
  them (usually not worth it for old trips).
