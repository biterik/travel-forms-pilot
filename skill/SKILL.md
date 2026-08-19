---
name: travel-forms-pilot
description: German academic business-trip paperwork (Dienstreise) for MPI-SusMat — travel applications, expense reports, calendar entries, and the trip dashboard. Use when the user mentions a business trip, a Dienstreiseantrag or travel application, a Reiseabrechnung or expense report, a per diem or Tagegeld, a trip number or Reisenummer, an A1 certificate, the Reisestelle, a booking or hotel confirmation for a work trip, a settlement letter, BahnBonus or Miles & More points, putting a trip in the calendar, or a trip folder named like `yyyymm_LOCATION_EVENT/`. Also use for "new trip", "build the application", "do the expense report", "close the trip", "how do my trips look". Understands German and English input; always replies in English.
---

# Travel Forms Pilot — entry point

This skill is a **locator plus the non-negotiables**. The full behaviour lives in
the `travel-forms-pilot` repo on the user's disk, which is also where the scripts,
form templates and accumulated trip learnings are. Read from there — do not work
from memory of this file alone.

## Step 1 — find the pilot, before doing anything else

Look for the repo in the connected folders, in this order:

1. `<connected folder>/travel-forms-pilot/`
2. `<connected folder>/TRAVEL-WORKFLOW-DEVEL/travel-forms-pilot/`
3. anywhere one level deeper that contains both `SKILL.md` and `scripts/fill_application.py`

Erik's layout (July 2026):

```
~/Desktop/MPIE/TRAVEL-FORMS/            ← the folder to connect
├── CLAUDE.md
├── personal/                           ← identity.yaml, bonus_points.md (never in git)
├── TRAVEL-WORKFLOW-DEVEL/
│   ├── STATUS.md
│   └── travel-forms-pilot/             ← the repo
├── dashboard.html
└── <trip folders>/                     ← yyyymm_LOCATION_EVENT
```

**If you cannot find the repo, say so and stop.** Ask the user to connect the
folder that contains it. Do not improvise the workflow, do not hand-build a form,
do not edit DOCX XML. Working blind is the failure mode this skill exists to
prevent.

## Step 2 — read, in this order

1. `<repo>/SKILL.md` — the full agent specification
2. `<repo>/prompts/00_pilot.md` — base behaviour
3. `<repo>/learnings.md` — accumulated rules from earlier trips
4. `<repo>/config/mpi-susmat.yaml` — institutional constants
5. `personal/identity.yaml` — master data (see the search path below)
6. the current trip's `trip.md`, if one is under discussion

Mode-specific prompts, read when the task calls for them:
`prompts/40_backlog.md` (importing old trips), `prompts/50_dashboard.md`,
`prompts/60_calendar.md`, `prompts/70_closing.md` (settlement letters).

## Step 3 — the non-negotiables

These hold even before you have read anything else.

- **Never hand-edit DOCX XML.** Use `scripts/fill_application.py`,
  `scripts/fill_expense.py`, `scripts/bootstrap_trip.py`,
  `scripts/backlog_trip.py`, `scripts/dashboard.py`. If a script doesn't cover
  something, propose a change to the script rather than working around it.
- **Never invent personal data.** `identity.yaml` is resolved by searching
  `$TFP_IDENTITY` → `$TFP_PERSONAL_DIR` → `<trips-root>/personal/` → one level
  above the repo → `~/.travel-forms-pilot/`. If it isn't found, ask. Never
  reconstruct a personnel number or cost centre from an old PDF without saying
  that is what you did.
- **After every completed Dienstreiseantrag, ask about the calendar.** Mandatory,
  the very next action after handing over the PDF, even if the user never
  mentioned it, even after a regeneration. One `AskUserQuestion`, yes/no.
- **Calendar writes are dry-run first, always.** Via the `calmcp` MCP server.
  The absence block goes on `cm_absence` (all-day, whole trip, *no booking
  detail*) and needs `confirm=true` **and** `confirm_foreign=true` — it is a
  shared departmental calendar. Travel legs and hotel stays go on `ic_travel`
  (`confirm=true`). Show the returned write contract before confirming. Never ask
  the user for a calendar password; there isn't one to give.
- **Always show the weekday with every date** ("Mo, 29.6.2026"), and check any
  weekday the user supplies against the real one before it reaches a form.
- **Ask in batches, once per phase** — three or four questions together, with an
  "Other" fallback. Never drip-feed.
- **Don't re-inspect generated PDFs.** The scripts are deterministic; the user
  opens the file and reports problems.
- **Trip folders live beside the repo, never inside it.** If a named trip folder
  doesn't exist, ask where to create it.
- **Regenerate the dashboard after any `trip.md` change**:
  `python3 scripts/dashboard.py <trips-root>`.

## Step 4 — answer

Interaction language is English; the user may write German or English. Ask once
per session whether the official MPIE forms should be filled in German (default —
the Reisestelle prefers it) or English.

---

*Thin by design: this skill locates the pilot and states the rules that must not
be broken. Everything else — file-sorting heuristics, form field indices, trim
recipes, per-trip history — is versioned in the repo, so it cannot drift out of
sync with the scripts it describes. Source: `skill/SKILL.md` in
`github.com/biterik/travel-forms-pilot`.*
