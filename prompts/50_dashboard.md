# 50 — Dashboard (overview across all trips)

A portable, read-only overview of every trip, built from the `trip.md` headers.
Surfaces what needs action (deadlines, missing applications, registrations,
pending reimbursements) so nothing slips.

## Trigger

The user asks for "the dashboard", "an overview", "what's open", "what needs
doing", "show all trips", etc.

## How it works

```bash
python scripts/dashboard.py <trips-root>            # writes <trips-root>/dashboard.html
python scripts/dashboard.py <trips-root> --text     # also print a text table
python scripts/dashboard.py <trips-root> --text-only # text only, no file
python scripts/dashboard.py <trips-root> --open      # open the HTML in the browser
```

`<trips-root>` is the folder that contains the trip folders (e.g. `TRAVEL-FORMS`).
The script scans it recursively for `trip.md`, skipping the repo's own template
tree and the calendar-test stub.

Output is **one self-contained HTML file** — inline CSS/JS, no internet, no CDN,
no fonts to download. It opens in any browser on macOS, Linux, or Windows. The
table is filterable (text box + status buttons) and sortable (click a header).

## Portability (important)

The dashboard is deliberately tool- and OS-agnostic: pure Python 3.8+ stdlib
plus PyYAML (already a project dependency). No LLM is involved in *viewing* it —
any user can run the script and open the HTML. Keep it that way: do not add
network calls, CDN links, or platform-specific commands.

## Read-only by design

The dashboard never edits anything. The workflow is: look at the dashboard →
spot something → edit that trip's `trip.md` (YAML header) → re-run the script.
If a column or alert you want isn't there, that's a signal to (a) add the field
to `trip.md` / `trip.md.tmpl` and fill it, and (b) extend `dashboard.py`.

## Alerts (thresholds are constants at the top of `dashboard.py`)

- **Abrechnung deadline** — trip not closed, expense not filed, and the 3-month
  `abrechnungsfrist` is within 30 days or already passed.
- **Application gap** — `antrag_genehmigt` not set and the trip is within ~3
  weeks or already in the past (with no `antrag_gestellt`).
- **Awaiting reimbursement** — `abrechnung_eingereicht` true but `erstattet` not.
- **Registration** — `anmeldung.early_bird_frist` (preferred) or `frist` within
  45 days or passed, and `angemeldet` not true.

Trips are sorted **action-first**: highest-severity alerts at the top (soonest
deadline first), then upcoming trips, then `closed` ones last.

## Note

The dashboard only shows trips that have a `trip.md`. Old folders show up once
they've been imported with `backlog_trip.py` (see `prompts/40_backlog.md`).
