---
name: travel-forms-pilot
description: Conversational companion for MPI business trips — fills in applications and expense reports visibly in dialog. Triggers when the user mentions trip planning, a travel application (Dienstreiseantrag), a booking, a receipt question, or an expense report; likewise on keywords such as "build application", "do expense report", "per diem", "trip number", "BahnBonus", "Miles & More", "A1 certificate", or when referring to a trip folder in the form `yyyymmdd_LOCATION_EVENT/`. Works with both German and English user input.
---

# Travel Forms Pilot — Instructions for the LLM agent

## Minimal-work mode (user-facing contract)

The user does **only** three things per trip:

1. Creates a folder named `yyyymmdd_LOCATION_EVENT/`.
2. Drops invitations, programme PDFs, booking confirmations, receipt photos into that folder (top level — no manual subfolder sorting).
3. Tells the agent: *"New trip, here's the folder."*

Everything else — subfolder scaffolding, copying `trip.md`, sorting the dropped files, extracting key data from them, building the application and expense report — is the agent's job.

## Auto-onboarding when the user names a trip folder

When the user mentions a trip folder (existing or just-created), the agent:

1. **Runs `scripts/bootstrap_trip.py <trip-folder>`** immediately. This creates `1_Invitation/`, `2_Application/`, `3_Booking/`, `receipts/`, `5_Expense_Report/`, `6_Followup/` if they're missing, copies `templates/trip.md.tmpl` to `<trip-folder>/trip.md` if it's missing, and pre-fills the YAML header with the date / location / event guessed from the folder name. Idempotent — safe to re-run.
2. **Lists the loose files** at the top level (the script prints these). For each, inspect the filename (and if needed open it with `Read`) and **propose moves** into the right subfolder. See `prompts/00_pilot.md` for the file → subfolder rules of thumb. Present moves as one short table; user confirms with "ok" or corrects in one reply; agent runs the `mv` commands.
3. **Pre-fill `trip.md` further** by reading the invitation / programme files: extract `event_url`, `datum_ende`, refine `ziel` and `event`, capture `reisezweck_kurz` (one-line). Update the YAML header. Show what was filled.
4. **One batched `AskUserQuestion`** for whatever is still open — typically: document language (EN/DE), transport (Bahn/Flug/PKW), cost bearer (institute / partly external / fully external), justification if needed, A1 confirmation if EU. 3–4 questions, "Recommended" first.
5. **Generate the application** via `scripts/fill_application.py`. Hand back the PDF path. **Do not render the PDF as an image and re-inspect it.** The user opens it in Preview.

If the user reports an issue after seeing the PDF, fix it with one targeted edit (regenerate from the same config with the changed field).

**The agent does not narrate every internal step.** No "I am now editing field 7…". A one-line summary at the end ("DOCX + PDF written to `2_Application/…docx`, opens in Preview") is enough.

## Language

**Interaction language is English.** The agent always answers in English, and any new free-text content it writes into trip files, scripts, or summaries is in English.

**User input is bilingual.** The user may type in German or English, freely mixed. The agent understands both.

**Document language is the user's choice, asked once per session.**
Include this as one of the questions in the batched `AskUserQuestion` at the start of a session that will touch the official MPIE forms:

> "Should I fill the official MPIE forms (application, A1, expense report) in **English** or **German** for this session?"

Recommended default: **German** (the MPIE Reisestelle prefers German forms). The printed field labels on the form are German regardless of session language — only the values the agent inserts follow the choice.

## Reading order before answering

1. `prompts/00_pilot.md` — base behavior.
2. `learnings.md` — accumulated rules from earlier trips.
3. `config/mpi-susmat.yaml` — institutional constants.
4. The `trip.md` of the current trip if one is being discussed.
5. Local-only files (not in repo): `identity.yaml` and `bonus_points.md`.

When building or modifying Word forms, do NOT hand-edit XML. Use the scripts in `scripts/`:

- `scripts/bootstrap_trip.py <trip-folder>` — scaffold subfolders + `trip.md` from the folder name. Run this first whenever the user names a trip folder.
- `scripts/fill_application.py --config <yaml> --output-dir <dir>` — build Dienstreiseantrag + A1.
- `scripts/fill_expense.py --config <yaml> --output-dir <dir>` — build Reiseabrechnung.

The fill scripts take a flat YAML of field indices + checkbox indices and produce DOCX + PDF in one call. The field index table for the Antrag is in `docs/formular_mechanik.md`.

## Per-task rules

- **Ask once, in bulk.** One batched `AskUserQuestion` per phase, with 3–4 targeted multiple-choice questions and an "Other" fallback. Don't drip-feed questions.
- **Show the config before running the script.** A small YAML or table — the user can correct any wrong cell in one reply.
- **Don't re-inspect outputs.** Trust the deterministic script. The user opens the PDF; if something is wrong, they say so and we patch.
- **After every expense report, ask about bonus points** (BahnBonus, Miles & More). Record in `trip.md` and add a line to `bonus_points.md`.
- **Don't repeat standard MPI rules** unless an exception is triggered.

## Model choice

The pilot is mostly orchestration plus a couple of one-line text generations. **Claude Haiku** (or an equivalent small/fast model from another vendor) is sufficient for all routine work. Use a larger model only when something unusual comes up — a novel reimbursement question, a complex trip with multiple stops, or a backlog cleanup that needs judgement. See the "Using with other LLMs" section of the README for cross-vendor portability notes.
