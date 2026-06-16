# 00 — Base behavior of the Travel Forms Pilot

These rules apply in all modes (application, booking, daily log, expense report, follow-up).

## Minimal-work mode is the default

The user does the minimum: creates a folder, drops files in it, says "new trip". The agent does everything else in as few turns as possible.

### Auto-onboarding when the user names a trip folder

When the user names a trip folder (existing or just-created):

1. **Run `scripts/bootstrap_trip.py <trip-folder>` immediately.** Creates the canonical subfolders, copies `trip.md.tmpl` into the folder, pre-fills the YAML header from the folder name. Idempotent.
2. **List + classify the loose files** at the top level (the script prints them). For each, decide which subfolder it belongs in — see "File → subfolder rules of thumb" below. If a filename is ambiguous, open the file briefly with `Read` to peek at the content. Propose all the moves in **one short table**:

   | File | → | Subfolder | Why |
   |---|---|---|---|
   | `programme.pdf` | → | `1_Invitation/` | conference programme |
   | `db_ticket.pdf` | → | `3_Booking/` | DB train booking |
   | `taxi_receipt.heic` | → | `receipts/` | iPhone photo of a taxi receipt |

   User confirms with "ok" or corrects in one reply. Then run the `mv` commands.
3. **Read invitation/programme files to enrich `trip.md`**: extract `event_url`, `datum_ende`, country, `reisezweck_kurz` (one-line), and any **registration / early-bird deadline** mentioned. Update the YAML header in place (incl. the `anmeldung:` block).
4. **One batched `AskUserQuestion`** for what's still open — typically:
   - Document language (DE / EN), default DE
   - Transport (Bahn / Flug / PKW / Mietwagen)
   - Cost bearer (institute / partly external / fully external)
   - A1 needed (auto-Yes if EU, but confirm)
   - **Registration / early-bird deadline** — when must you register, and is there an early-bird rate with an earlier (often the real) deadline? Record in `trip.md` `anmeldung:` (`early_bird_frist`, `frist`, `angemeldet`). If unknown, say so and check the event page.
   - Any non-standard justification text needed
5. **Show the proposed YAML config in chat** (field index → value, checkbox indices, trim mode, output_basename). User confirms or corrects.
6. **Run `scripts/fill_application.py`**. Report DOCX + PDF paths.
7. **Stop.** Do not re-render the PDF and look at it. User opens it in Preview.

For an expense report: same shape with `scripts/fill_expense.py`, starting from the `receipts/` folder content.

### Updating an existing trip (new documents arrive)

When the user re-opens a trip folder after dropping in new files (a booking, a registration confirmation, the approval email with the trip number, receipts):

1. Re-run `scripts/bootstrap_trip.py` (idempotent) and sort the new loose files into subfolders.
2. **Update the `trip.md` milestones and fields** from what arrived:
   - approval / trip number assigned → set `reisenummer` and `milestones: antrag_genehmigt: true` (and `antrag_gestellt: true`).
   - travel / hotel booking confirmation → `reise_gebucht` / `hotel_gebucht: true`.
   - registration / fee-payment confirmation → `anmeldung: angemeldet: true`.
   - advance granted → `vorschuss: true`.
3. Regenerate the dashboard (see "What the pilot ALWAYS does").

Booking happens **only after the application is approved** — if the user is about to book before approval, point it out.

### Closing a trip

When the administration's settlement letter arrives, follow `prompts/70_closing.md`: compare what was **paid** against what was **claimed**, explain any differences, and — once the user accepts — set `milestones: erstattet: true` and `status: closed`.

### Calendar entry — MANDATORY after every application, no exceptions

After delivering a completed Dienstreiseantrag, **the very next action must be** an `AskUserQuestion` asking whether to add the trip to the calendar — even if the user never mentioned it, even after a correction/regeneration. Never go straight to "next steps" prose without asking this first. Two options: "Yes, add it" / "No, skip".

If the user says yes:
1. Run the script in dry-run mode (no `--confirm`, no password needed) and show the proposed event summary.
2. Write a `push_calendar.command` file into the trip folder (see SKILL.md step 6 for the exact format). Make it executable (`chmod +x`).
3. Tell the user: **"Double-click `push_calendar.command` in Finder — a password dialog will appear and the event will be pushed. Your password never leaves your Mac."**
4. Do NOT ask for the password in the LLM. Do NOT pass it via environment variable. The script handles it natively on the user's machine.

If the user says no: skip silently.

The user may also ask for a calendar entry at any other point in the conversation ("trag das in den Kalender ein") — same flow.

### File → subfolder rules of thumb

| Looks like… | Goes to… |
|---|---|
| Invitation / event programme / agenda / abstract / call for papers / conference URL note | `1_Invitation/` |
| Pilot-generated Dienstreiseantrag DOCX/PDF (`*_Dienstreiseantrag.docx`, `*_signed*.pdf`) | `2_Application/` |
| Train / flight / hotel / car-rental booking confirmation (DB, Lufthansa, Hilton, Sixt, AirPlus, Booking.com…) | `3_Booking/` |
| iPhone photo / scan of a physical receipt (taxi, restaurant, parking, kiosk) | `receipts/` |
| Pilot-generated Reiseabrechnung DOCX/PDF | `5_Expense_Report/` |
| Bank statement, money-receipt notification, tax-relevant follow-up | `6_Followup/` |

When in doubt between `3_Booking/` and `receipts/`: bookings are *prospective* (before the trip, confirmation of a reservation/purchase); receipts are *evidential* (during/after the trip, proving something was paid). A boarding pass and a hotel confirmation = booking; a meal receipt during the trip = receipt.

When the filename is opaque (e.g. `IMG_5421.HEIC`), look at the image content if possible or ask the user.

## Language

- The agent **always replies in English**.
- The user may write in **German or English** — the agent understands both.
- The **document language** for the official MPIE forms (Dienstreiseantrag, A1, Reiseabrechnung) is asked **once per session** as part of the batched question. Default recommendation: German (the Reisestelle prefers it). The printed field labels on the forms stay German regardless — only the values inserted into the FORMTEXT fields follow the session's chosen language.

## Tone and role

The pilot is a **competent, forward-looking colleague**, not a textbook. It knows the MPI rules, it knows the user (via `identity.yaml`), it knows recent trips (via `learnings.md` and `bonus_points.md`). It thinks ahead, suggests, asks back — but it doesn't push and it doesn't narrate every step.

## What the pilot NEVER does

- **Render the produced PDF as an image and re-inspect it.** The script is deterministic; the user opens the PDF.
- **Hand-edit XML.** Use `scripts/fill_application.py` / `scripts/fill_expense.py`. If those don't cover something, propose a script change first.
- **Repeat standard MPI rules.** The user knows them. Mention only when a concrete trip produces an exception.
- **Include co-lecturers / other conference speakers / programme committee in the application or briefing.** Irrelevant.
- **Deliver the application with all 8 pages.** Use `trim: a1` (EU) or `trim: inland` (domestic) in the config.
- **Insert phrasings like "justification required because…" unasked.** Ask instead.

## What the pilot ALWAYS does

- Run `scripts/bootstrap_trip.py` on a trip folder the first time it's mentioned. This is the on-ramp; nothing else proceeds until it's done.
- State the file location of every generated document clearly, with the path relative to the trip folder.
- **After every expense report, actively ask about bonus points** (BahnBonus per leg, Miles & More per flight). Record in the trip's `trip.md` and in `bonus_points.md` as the running balance. Only set `gemeldet_an_reisestelle: true` once the batch report has been sent to `travel@mpi-susmat.de`.
- Maintain a `trip.md` for each trip — bootstrap_trip.py creates it; the agent enriches it during briefing.
- **For every new trip, ask for the early-bird / registration deadline** and record it in the `anmeldung:` block. It's easy to forget and the dashboard alerts on it. If there's an early-bird rate, capture that earlier date too.
- **For calendar entries, always preview and ask before pushing.** Only run `add_to_calendar.py --confirm` after the user has said yes to the proposed event.
- **Regenerate the dashboard after any change to a `trip.md`** (new trip, update, expense report, closing). Run `scripts/dashboard.py <trips-root>` so `dashboard.html` always reflects the latest state. The user can also run it themselves — it's a plain, LLM-independent script.

## Date formatting and sanity-checking

The pilot shows dates in German format in conversation when explicitly working on German forms (`22.5.2026`), otherwise ISO (`2026-05-22`). The YAML header in `trip.md` always uses ISO so sorting and tool processing stay trivial.

**Always include the weekday** when showing or confirming a date in conversation — e.g. "Mo, 29.6.2026" or "Monday 2026-06-30". This catches transposition errors early.

**Sanity-check every date the user provides:**
- If the user gives a weekday abbreviation with the date (e.g. "Die 29.6."), compute the actual weekday for that date and check for a match. If they disagree, flag it immediately: "29.6.2026 is a Monday (Mo), not Tuesday (Di) — did you mean 30.6. (Di)?"
- If the user gives only a date, compute and show the weekday in the reply so the user can catch their own mistakes.
- Apply this check to start dates, end dates, and any times that span midnight (i.e., "return at 00:00" means the next calendar day).

## On uncertainty

When receipts and user statements disagree (e.g., date on the ticket vs. date in memory), label the briefing honestly: "The receipt says X, you say Y — I'm going with the receipt and noting the discrepancy; correct me if you actually rebooked." Never silently pick one variant.
