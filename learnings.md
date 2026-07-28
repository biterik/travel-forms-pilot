# Travel Forms Pilot — institutional travel memory

This file grows with every trip that gets worked through. Entries are short and concrete.

---

## Style & behavior

- **Don't repeat standard MPI rules.** Erik knows them. Don't list them every time: book only after approval, declare bonus programmes, 70-€ inland hotel rule, 3-month expense-report deadline, ARV per diems for abroad. Mention only when the concrete trip triggers an exception.
- **Co-lecturers / other speakers are irrelevant to the application.** Don't list them in the briefing — they go neither into the form nor into the justification.
- **In the briefing only mention what is new or decision-relevant for this trip.** No textbook recap of the mechanics — what's different here, what does Erik have to decide, where are the gaps.
- **Always deliver the application as a compact file** — only the pages that actually get submitted to the Reisestelle (application + A1 if applicable). No index, no EU country list, no English helper version, no hints/explanations.
- **Default date on the application:** today. Erik signs directly.
- **Trip-purpose wording: always very short.** Erik wants a compact line, not a written-out sentence. Example format: "DPG, symposium organization defect phases" or "FAU Erlangen, AMMP lecture". No conference subtitle, no funding programme, no location (that lives in the field Reiseland/Ort).

## Mandatory artifacts per trip

- **`trip.md` is mandatory** in every trip folder. Template: `travel-forms-pilot/templates/trip.md.tmpl`. It is the single source of truth across all phases and contains in its YAML header: `status`, key dates, trip number / cost center, and the `bonusprogramme:` block.
- **After every expense report, actively ask about bonus points** (BahnBonus and/or Miles & More): number of points/miles per trip, with the rule of thumb "1 point per € Flexpreis Business" for BahnBonus. Record the answer in `trip.md` AND add a row to `personal/bonus_points.md` (see the search path above). Bonus points are reported in batches — set the flag `gemeldet_an_reisestelle:` to `true` only once the batch report has been sent to `travel@mpi-susmat.de`.

## Travel Forms Pilot mode per trip

- First phase (briefing) always with:
  1. Key trip data (location, date, purpose)
  2. EU country? → A1 needed or not
  3. Personal data from `identity.yaml`
  4. Three to four open questions via `AskUserQuestion`: trip duration, cost bearer, mode of transport, private portion if any
- Personal data comes from `identity.yaml`. If something is missing there, fall back to the most recent signed application (`*_signedEB.pdf`) in the latest trip folder via `pdftotext -layout` — the fields Name/Vorname/Abteilung/Kostenstelle/Personalnummer are all on the front page.

## Conventions that have worked

- **Trip folder name:** `yyyymmdd_LOCATION_EVENT/` with the trip start date.
- **Subfolder structure (English):** `1_Invitation/`, `2_Application/`, `3_Booking/`, `receipts/`, `5_Expense_Report/`, `6_Followup/`
- **File naming in `2_Application/`:** `<yyyymmdd-tripstart>_<shortname>_Dienstreiseantrag.docx` (example: `20260906_Cargese-MecaNano_Dienstreiseantrag.docx`). After signature in parallel as `…_signedEB.pdf`.

## Inland application (no A1)

- For domestic German trips **no A1** is needed → the application becomes **1 page**.
  - Truncation recipe: drop the index page (everything up to and including break 0), drop the cost-trigger disclaimer paragraph (incl. break 1), drop the A1 page and the EU country list — only `<w:sectPr>` stays. Trim trailing paragraphs.
  - Result: 0 page breaks in the DOCX, 1 page in the PDF.

## Calendar entry — MANDATORY after every application

**After every completed Dienstreiseantrag, always ask about the calendar — no exceptions, even if the user didn't mention it.** This must be the very next thing after presenting the PDF. Use `AskUserQuestion` with "Yes, add it" / "No, skip". Do NOT skip it even after corrections/regenerations — ask once, after the final PDF is delivered.

If yes: dry-run `create_event` on `cm_absence` via the `calmcp` MCP server, show the returned write contract, then confirm with **both** `confirm=true` and `confirm_foreign=true`. Full behaviour in `prompts/60_calendar.md`.

## Session startup — how the agent finds the skill (revised July 2026)

There are two mechanisms, and which one applies depends on where the session runs:

- **`CLAUDE.md` at the workspace root** — read automatically by Claude Code (CLI) and by Cowork tasks running *on your computer*. It chains STATUS.md → SKILL.md → 00_pilot.md → learnings.md → identity.yaml. A template ships as `CLAUDE.md.example`; copy it to the root of the folder you connect. The real `CLAUDE.md` lives outside the repo and is git-ignored.
- **`SKILL.md` installed as a skill** — the mechanism that works everywhere, including **Cowork tasks running in the cloud**, where your folders are reached over the device bridge and `CLAUDE.md` is *not* auto-loaded. This is now the primary path; `CLAUDE.md` is the belt-and-braces backup.

Verified July 2026: in a cloud Cowork session with `TRAVEL-FORMS` connected, `CLAUDE.md` at the folder root was **not** loaded — the file had to be read explicitly. Do not rely on it in that mode.

If a session goes wrong from the start (wrong approach, ignoring the scripts, hand-editing XML), check in this order: is the skill installed; is `CLAUDE.md` present at the *connected* folder root; is the right folder connected at all.

## Personal files live outside the repo (revised July 2026)

- `identity.yaml` and `bonus_points.md` are personal and never committed. Canonical location: **`TRAVEL-FORMS/personal/`** — a sibling of the trip folders, so it survives moving, re-cloning or deleting the repo.
- The scripts resolve them via `$TFP_IDENTITY` → `$TFP_PERSONAL_DIR` → `<trips-root>/personal/` → one level above the repo (the pre-2026 location, still honoured) → `~/.travel-forms-pilot/`. Never hard-code the path again.
- The repo ships `identity.example.yaml` and `bonus_points.example.md` with no personal data. Keep it that way: the examples are what an outside user forks.
- If `identity.yaml` can't be found, **ask** — do not reconstruct a personnel number or cost centre from an old PDF without saying that's what you did.

## Trip-specific lessons

### DFG-Jahresversammlung Bonn (June 2026)
- **Cost bearer: the institute (default cost centre from `identity.yaml`)** — unlike DFG committee/working-group trips (e.g., DFG Fachforum MatWerk, DFG Darmstadt Jan 2026) which are fully externally funded by DFG, the annual assembly is attended as a DFG member institution representative and charged to the institute. Do not assume "DFG event = externally funded."
- The trip ticket was for **Festliche Veranstaltungen** (evening events only: Communicator-Preis Mo 29.6., Festveranstaltung Di 30.6.) — travel was Di 30.6. only, same-day return (event ends ~23:00, no hotel). Di 30.06.2026 = departure AND return date.
- Hotel + Tagegeld checked (MPI pays both); no external cost bearer.
- Bahn; BahnBonus applies.

### MecaNano Summer School / Cargèse (September 2026)
- IESC address: **Menasina, 20130 Cargèse, France**.
- Cargèse is ~50 km from Ajaccio; standard route: fly to Ajaccio, transfer organized by the host — checking only the airplane box is enough.
- MecaNano is COST Action **CA21121** — belongs in the trip purpose.
- At IESC schools the host typically covers accommodation and meals → mark "partly externally borne" on the application; **at the expense-report stage** then reduce per diems for meals received.
- When invited as a lecturer, no conference fee → leave the "seminar fee" checkbox empty.

## Date sanity-checking

- **Always show the weekday with every date** — e.g. "Mo, 29.6.2026". Users often give a weekday abbreviation ("Die") with the date; compute the real weekday and flag mismatches before filling any form.
- **"Return at 00:00" = next calendar day.** Call this out so it's clear the end date is different from the start date.
- Real example (DFG Bonn 2026): user said "Die 29.6.", but 29.6.2026 is a Monday (Mo). The festive event was on Dienstag 30.6. — the wrong date got into the application and needed correction.

## Trip folder location

- **Trip folders live in `TRAVEL-FORMS/`, never inside the repo.** Layout: `TRAVEL-FORMS/` holds `travel-forms-pilot/` (the repo), `personal/` (identity + bonus points), and the trip folders as siblings of both.
- Always check whether the named folder already exists before running `bootstrap_trip.py`. If it doesn't exist yet, ask the user where to create it — never assume it belongs in the workspace root.

## Calendar (revised July 2026 — now via the calmcp MCP server)

- **Two calendars, two purposes.** `cm_absence` (Kerio, shared, owned by `cm-office`, role `writable`) gets **one all-day block** over the travel period and nothing else — the department reads it. `ic_travel` (iCloud "travel", role `owner`) gets **one event per travel leg and per hotel stay**, built from the booking confirmations. Never put booking detail on the shared calendar.
- **Two gates, not one.** `calmcp` writes are dry-run until `confirm=true`. A calendar whose role isn't `owner` needs `confirm_foreign=true` **as well** — so every absence-block write needs both. Show the user the returned before/after contract first, and say out loud that `cm_absence` is shared.
- **Keep the UID scheme.** `travel-forms-pilot-<trip-folder>@mpie.de` for the absence block — unchanged from the `add_to_calendar.py` era, so re-runs update the old events instead of duplicating them. Itinerary UIDs: `tfp-<trip-folder>-out|-ret|-leg<N>|-hotel@travel`.
- **Rebooking = edit, not a second event.** `move_event` for new times, `update_event` for everything else, same UID.
- **Credentials are gone from the pilot entirely.** The MCP server pulls them from the OS keyring. No `app_password` in `identity.yaml`, no `getpass`, no `push_calendar.command`. Never ask the user for a calendar password in any mode.
- **The old KADE problem no longer bites.** Kerio app passwords don't work for AD-imported accounts (known bug, fix needs MPIE IT) — that was the whole reason for the runtime password prompt. With the MCP server the regular password sits in the Keychain and the question doesn't arise. Still relevant only on the `add_to_calendar.py` fallback path.
- `add_to_calendar.py` is retained as the fallback for sessions without the MCP server (GWDG, bare chat, another vendor). It covers the absence block only.

## Backlog import (old trips)

- **Use `scripts/backlog_trip.py <folder>`** for old, completed single-trip folders — never hand-build their `trip.md`. It **previews by default** (gleaned facts, each tagged with its source `[application]`/`[folder name]`/`[default]`, plus a "Missing / needs checking" list) and only writes/sorts on `--confirm`. Always show Erik the facts + gaps for each folder before confirming. Lenient and non-destructive.
- **Status model (revised 16 June 2026):** headline `status` is `open` / `open-unsure` / `closed`, plus a `milestones:` block (`antrag_gestellt`, `antrag_genehmigt`, `reise_gebucht`, `hotel_gebucht`, `vorschuss`, `event_stattgefunden`, `abrechnung_eingereicht`, `erstattet`). `closed` requires settlement (DR-Abrechnung) proof on file; backlog imports default to `open-unsure`. The importer sets milestones conservatively (only `true` on positive evidence from filenames/PDF, blank otherwise). The old linear enum (`planned → … → reimbursed`) is retired; all existing `trip.md`s were migrated.
- **A `_Vorlage`/template expense file is NOT proof of filing.** Don't mark `abrechnung_eingereicht`/`filed` just because a `*Reiseabrechnung*` file exists — if it's the template, leave the milestone blank.
- **Filename gotchas learned here:** the trip number `DR####` is usually preceded by `_`, so a regex `\bDR` fails — use a letter lookbehind `(?<![A-Za-z])DR\d{3,}`. Signed application copies are sometimes flattened scans with no text layer, so extraction must try *all* PDFs until one yields text, not just the signed one.
- **Old folders are sometimes named `EVENT_LOCATION`** (e.g. `20230905_Complas_Barcelona`, Complas = event, Barcelona = city) instead of the `LOCATION_EVENT` convention — so `ziel`/`event` from the folder name can be swapped. Destination from the application PDF is more reliable; always eyeball the dry-run.
- **Scope so far:** single-trip folders only. Year-aggregator folders (`2025_FAU`, `2024_DFG`, …) holding many trips, and the loose `<Surname>_DR####_*.pdf` settlement PDFs at the `TRAVEL-FORMS` top level, are not handled yet.

## Dashboard & registration

- **Dashboard = `scripts/dashboard.py <trips-root>`** — portable (stdlib + PyYAML, no LLM, cross-OS), read-only, writes a self-contained HTML (+ `--text`). Spot something → edit the trip's `trip.md` → re-run. Only trips with a `trip.md` appear, so import old folders first (`backlog_trip.py`).
- **Always capture the registration / early-bird deadline for new trips** in the `anmeldung:` block (`early_bird_frist`, `frist`, `angemeldet`). This was historically forgotten; the dashboard now alerts on it. The early-bird date is often the one that actually matters.
- **Keep the dashboard portable:** no network/CDN/JS libraries, no OS-specific calls — pure stdlib + PyYAML, single self-contained HTML.
- **Regenerate `dashboard.html` after every `trip.md` change** (new trip, update, expense report, closing) so it's always current. The user can also run `dashboard.py` themselves.
- **Closing = check the settlement letter** (`prompts/70_closing.md`): read the admin's settlement letter AND the submitted Reiseabrechnung, compare paid vs. claimed, explain differences in plain language, never invent figures (ask if it's a scan). On acceptance set `erstattet: true` + `status: closed`. This is an LLM reading task (portable), not a deterministic parser.
- **Update flow (B):** when new docs arrive for an active trip, re-run bootstrap (sorts files) and update `trip.md` milestones — approval/trip number → `antrag_genehmigt`+`reisenummer`; booking → `reise_gebucht`/`hotel_gebucht`; sign-up → `angemeldet`. Booking only after approval.

## Done since (closing out old entries)

- ~~Centralize `identity.yaml`~~ — done July 2026: canonical location `TRAVEL-FORMS/personal/`, with a documented search order in the scripts (see "Personal files live outside the repo").
- ~~Dashboard artifact~~ — built (`scripts/dashboard.py`, `prompts/50_dashboard.md`).
- ~~Backlog mode~~ — built (`scripts/backlog_trip.py`, `prompts/40_backlog.md`).
- ~~Calendar without a password prompt~~ — solved by the calmcp MCP server, July 2026.

## Open questions / next improvements

- `trip.md` minimal template — refine once a couple more real trips have gone through the `beitrag:` / `anmeldung:` blocks.
- Backlog scope: year-aggregator folders (`2025_FAU`, `2024_DFG`, …) and the loose `<Surname>_DR####_*.pdf` settlement PDFs at the `TRAVEL-FORMS` top level are still not handled.
- Quickie receipt-photo workflow (drop a photo, get it filed and captured) — not started.
- Reiseabrechnung per-day repeating fields still use raw 0-based indices; alias them in `NAMED_FIELDS` as they come up.
- Itinerary events could seed the Reiseabrechnung departure/arrival times via `find_events` — sketched in `prompts/60_calendar.md`, not yet exercised on a real trip.
