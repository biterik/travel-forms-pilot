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
- **After every expense report, actively ask about bonus points** (BahnBonus and/or Miles & More): number of points/miles per trip, with the rule of thumb "1 point per € Flexpreis Business" for BahnBonus. Record the answer in `trip.md` AND add a row to `TRAVEL-WORKFLOW-DEVEL/bonus_points.md`. Bonus points are reported in batches — set the flag `gemeldet_an_reisestelle:` to `true` only once the batch report has been sent to `travel@mpi-susmat.de`.

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

## Session startup — CLAUDE.md is mandatory

- **The pilot only works correctly when `CLAUDE.md` exists at the workspace root** (`TRAVEL-WORKFLOW-DEVEL/CLAUDE.md`). Without it, Claude starts blind: ignores SKILL.md, the scripts, and this file, and will try to do everything by hand (editing XML directly, reinventing the workflow, etc.).
- `CLAUDE.md` tells Claude to read STATUS.md → SKILL.md → 00_pilot.md → learnings.md → identity.yaml before answering. Once in place, no startup preamble is needed — just say what you need.
- If a session goes wrong from the start (wrong approach, ignoring scripts), the first thing to check is whether CLAUDE.md is present and the correct folder is connected in Cowork.

## Trip-specific lessons

### DFG-Jahresversammlung Bonn (June 2026)
- **Cost bearer: institute (W0405001)** — unlike DFG committee/working-group trips (e.g., DFG Fachforum MatWerk, DFG Darmstadt Jan 2026) which are fully externally funded by DFG, the annual assembly is attended as a DFG member institution representative and charged to the institute. Do not assume "DFG event = externally funded."
- The trip ticket was for **Festliche Veranstaltungen** (evening events only: Communicator-Preis Mo 29.6., Festveranstaltung Di 30.6.) — travel was Di 30.6. only, returning Mi 01.07. at midnight.
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

- **Trip folders live in `TRAVEL-FORMS/`, not inside `TRAVEL-WORKFLOW-DEVEL/`.** The repo is in `TRAVEL-WORKFLOW-DEVEL/travel-forms-pilot/`; trip folders are siblings of `TRAVEL-WORKFLOW-DEVEL/` inside `TRAVEL-FORMS/`.
- Always check whether the named folder already exists before running `bootstrap_trip.py`. If it doesn't exist yet, ask the user where to create it — never assume it belongs in the workspace root.

## Kerio Connect calendar authentication

- **App passwords do not work for AD-imported accounts** (known KADE bug). Both old and freshly-generated app passwords return 401 for CalDAV PROPFIND, even though credentials are sent correctly.
- **Workaround:** leave `app_password` blank in `identity.yaml`; `add_to_calendar.py` now prompts via `getpass` at runtime. The user enters their regular MPIE password — never stored anywhere.
- The fix (updating KADE on the AD server) requires MPIE IT. Until then, runtime prompt is the correct flow.

## Open questions / next improvements

- Centralize `identity.yaml` — currently lives in `TRAVEL-WORKFLOW-DEVEL/`, should later move to `~/.travel-forms-pilot/identity.yaml` per the concept.
- `trip.md` minimal template — first version exists; refine after second real trip.
- Dashboard artifact: worth building from the second real trip onwards.
- Backlog mode: not yet built; worth doing once Cargèse is reimbursed and we've practiced the "lenient style" once for real.
