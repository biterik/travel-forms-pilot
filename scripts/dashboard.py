#!/usr/bin/env python3
"""Travel Forms Pilot — portable trip dashboard.

Scans a directory tree for per-trip `trip.md` files, reads their YAML headers,
computes action alerts, and renders an overview as a self-contained HTML file
(inline CSS/JS, no internet, no CDN) and/or a plain-text table.

Deliberately portable:
  * Pure Python 3.8+ standard library, plus PyYAML (already a project dep).
  * No LLM, no network, no OS-specific calls — runs the same on macOS, Linux,
    and Windows. Output is a single .html you can open in any browser.

The dashboard is READ-ONLY. When you spot something to change, edit the trip's
`trip.md` (YAML header) and re-run this script.

Usage:
    python dashboard.py [TRIPS_ROOT] [-o dashboard.html] [--text] [--open]

    TRIPS_ROOT   directory to scan recursively for trip.md (default: current dir)
    -o / --output  HTML output path (default: <root>/dashboard.html)
    --text         also print a plain-text table to stdout
    --text-only    print the text table only; write no HTML
    --open         open the generated HTML in the default browser

Alerts surfaced (configurable thresholds near the top of this file):
    • Abrechnung deadline near/overdue and not yet filed
    • Application missing/not approved as the trip approaches or has passed
    • Filed but awaiting reimbursement (money not received)
    • Registration (early-bird) deadline near/missed and not registered
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("Missing dependency: pip install pyyaml --break-system-packages\n")
    sys.exit(2)

# ---- thresholds (days) — tweak freely
ABRECHNUNG_WARN_DAYS = 30      # warn when the 3-month expense deadline is this close
ANTRAG_WARN_DAYS = 21          # warn when a trip without a submitted application is this close
REGISTRATION_WARN_DAYS = 45    # warn when a registration deadline is this close

SEV = {"overdue": 3, "warn": 2, "info": 1, "ok": 0}
MILESTONE_LABELS = [
    ("antrag_gestellt", "Antrag"),
    ("antrag_genehmigt", "Genehmigt"),
    ("reise_gebucht", "Reise"),
    ("hotel_gebucht", "Hotel"),
    ("vorschuss", "Vorschuss"),
    ("event_stattgefunden", "Event"),
    ("abrechnung_eingereicht", "Abrechnung"),
    ("erstattet", "Erstattet"),
]


# ----------------------------------------------------------------------------- scanning / parsing

def find_trip_mds(root: Path):
    for p in sorted(root.rglob("trip.md")):
        s = str(p)
        if "travel-forms-pilot" in s or "_calendar_test" in s:
            continue  # skip the repo's own template tree + the calendar test stub
        yield p


def parse_header(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def to_date(v):
    if isinstance(v, dt.date):
        return v
    if not v:
        return None
    s = str(v).strip()
    if not s or s.upper() == "YYYY-MM-DD":
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def is_true(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


# ----------------------------------------------------------------------------- model

def build_trip(path: Path, root: Path, today: dt.date) -> dict:
    h = parse_header(path)
    m = h.get("milestones") or {}
    an = h.get("anmeldung") or {}

    status = str(h.get("status") or "open").strip().lower()
    start = to_date(h.get("datum_start"))
    end = to_date(h.get("datum_ende")) or start
    af = to_date(h.get("abrechnungsfrist"))
    eb = to_date(an.get("early_bird_frist"))
    reg = to_date(an.get("frist"))
    angemeldet = is_true(an.get("angemeldet"))

    def ms(k):
        return is_true(m.get(k))

    alerts = []  # list of (level, text)
    closed = status == "closed"

    if not closed:
        # Abrechnung deadline
        if af and not ms("abrechnung_eingereicht") and not ms("erstattet"):
            d = (af - today).days
            if d < 0:
                alerts.append(("overdue", f"Abrechnung überfällig ({-d} d)"))
            elif d <= ABRECHNUNG_WARN_DAYS:
                alerts.append(("warn", f"Abrechnung fällig in {d} d"))

        # Application gap
        if not ms("antrag_genehmigt") and start:
            d = (start - today).days
            if d < 0 and not ms("antrag_gestellt"):
                alerts.append(("overdue", f"Antrag fehlt (Reise war {-d} d her)"))
            elif d < 0 and ms("antrag_gestellt"):
                alerts.append(("warn", "Antrag noch nicht genehmigt"))
            elif 0 <= d <= ANTRAG_WARN_DAYS and not ms("antrag_gestellt"):
                alerts.append(("warn", f"Antrag fehlt (Reise in {d} d)"))

        # Awaiting reimbursement
        if ms("abrechnung_eingereicht") and not ms("erstattet"):
            alerts.append(("info", "wartet auf Erstattung"))

        # Registration (early-bird preferred, else regular)
        if not angemeldet:
            fr, label = (eb, "Early-bird") if eb else (reg, "Anmeldung")
            if fr:
                d = (fr - today).days
                if d < 0:
                    lvl = "info" if (eb and reg and (reg - today).days >= 0) else "warn"
                    alerts.append((lvl, f"{label}-Frist verpasst ({-d} d)"))
                elif d <= REGISTRATION_WARN_DAYS:
                    alerts.append(("warn", f"{label}-Frist in {d} d"))

    severity = max((SEV[l] for l, _ in alerts), default=0)
    return {
        "folder": path.parent.name,
        "relpath": str(path.parent.relative_to(root)) if path.parent != root else ".",
        "event": str(h.get("event") or "").strip() or path.parent.name,
        "ziel": str(h.get("ziel") or "").strip(),
        "status": status,
        "start": start,
        "end": end,
        "af": af,
        "early_bird": eb,
        "reg": reg,
        "angemeldet": angemeldet,
        "reisenummer": str(h.get("reisenummer") or "").strip(),
        "zweck": str(h.get("reisezweck_kurz") or "").strip(),
        "milestones": {k: m.get(k) for k, _ in MILESTONE_LABELS},
        "alerts": alerts,
        "severity": severity,
        "backlog": is_true(h.get("backlog_imported")),
    }


def sort_trips(trips):
    """Action-first: needs-attention (by severity, soonest first), then upcoming,
    then closed (most recent first)."""
    far = dt.date.max
    active = [t for t in trips if t["status"] != "closed"]
    closed = [t for t in trips if t["status"] == "closed"]
    active.sort(key=lambda t: (-t["severity"], t["start"] or far))
    closed.sort(key=lambda t: (t["start"] or dt.date.min), reverse=True)
    return active + closed


# ----------------------------------------------------------------------------- rendering: shared

def fmt_range(t) -> str:
    s, e = t["start"], t["end"]
    if not s:
        return "—"
    if e and e != s:
        return f"{s.strftime('%a %d.%m.%Y')} → {e.strftime('%a %d.%m.%Y')}"
    return s.strftime("%a %d.%m.%Y")


# ----------------------------------------------------------------------------- rendering: text

def render_text(trips, today) -> str:
    out = [f"Travel Forms — dashboard ({today.isoformat()}), {len(trips)} trips", "=" * 78]
    for t in sort_trips(trips):
        line = f"[{t['status']:<11}] {fmt_range(t):<26} {t['event']}"
        out.append(line)
        meta = []
        if t["ziel"]:
            meta.append(t["ziel"])
        if t["reisenummer"]:
            meta.append(t["reisenummer"])
        if t["af"]:
            meta.append(f"Frist {t['af'].isoformat()}")
        if t["early_bird"]:
            meta.append(f"Early-bird {t['early_bird'].isoformat()}")
        if meta:
            out.append("    " + " · ".join(meta))
        for lvl, txt in t["alerts"]:
            mark = {"overdue": "!!", "warn": " !", "info": " ·"}[lvl]
            out.append(f"   {mark} {txt}")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- rendering: HTML

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1f2733;--muted:#6b7682;--line:#e4e8ee;
--open:#2563eb;--unsure:#b45309;--closed:#16794a;
--overdue:#c0322b;--warn:#b45309;--info:#2563eb;--ok:#16794a;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 2px}
.sub{color:var(--muted);font-size:13px;margin-bottom:16px}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
input#q{flex:1;min-width:200px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:14px}
.btn{padding:6px 10px;border:1px solid var(--line);background:var(--card);border-radius:999px;cursor:pointer;font-size:13px;color:var(--muted)}
.btn.active{background:var(--ink);color:#fff;border-color:var(--ink)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr.closed{opacity:.6}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;color:#fff;white-space:nowrap}
.badge.open{background:var(--open)}.badge.open-unsure{background:var(--unsure)}.badge.closed{background:var(--closed)}
.event{font-weight:600}
.muted{color:var(--muted);font-size:12px}
.chip{display:inline-block;padding:2px 7px;border-radius:6px;font-size:12px;margin:1px 3px 1px 0;white-space:nowrap}
.chip.overdue{background:#fbe6e4;color:var(--overdue);font-weight:600}
.chip.warn{background:#fdf0db;color:var(--warn)}
.chip.info{background:#e7eefb;color:var(--info)}
.ms{display:flex;flex-wrap:wrap;gap:3px}
.m{font-size:10.5px;padding:1px 5px;border-radius:5px;border:1px solid var(--line);color:var(--muted)}
.m.yes{background:#e3f3ea;border-color:#bfe3cd;color:var(--ok)}
.m.no{background:#fbe6e4;border-color:#f1c9c5;color:var(--overdue)}
.foot{color:var(--muted);font-size:12px;margin-top:14px}
"""

JS = """
const rows=[...document.querySelectorAll('tbody tr')];
const q=document.getElementById('q');
function apply(){
  const term=q.value.toLowerCase();
  const f=document.querySelector('.btn.active').dataset.f;
  rows.forEach(r=>{
    const okText=r.textContent.toLowerCase().includes(term);
    const okFilter=f==='all'||(f==='action'?r.dataset.sev>'0':r.dataset.status===f);
    r.style.display=(okText&&okFilter)?'':'none';
  });
}
q.addEventListener('input',apply);
document.querySelectorAll('.btn').forEach(b=>b.addEventListener('click',()=>{
  document.querySelector('.btn.active').classList.remove('active');
  b.classList.add('active');apply();
}));
document.querySelectorAll('th').forEach((th,i)=>th.addEventListener('click',()=>{
  const tb=document.querySelector('tbody');
  const asc=th.dataset.asc!=='1';th.dataset.asc=asc?'1':'0';
  [...tb.querySelectorAll('tr')].sort((a,b)=>{
    const x=a.children[i].dataset.k||a.children[i].textContent;
    const y=b.children[i].dataset.k||b.children[i].textContent;
    return (x>y?1:x<y?-1:0)*(asc?1:-1);
  }).forEach(r=>tb.appendChild(r));
}));
"""


def esc(s) -> str:
    return html.escape(str(s))


def render_html(trips, today, root: Path, hidden_closed: int = 0) -> str:
    counts = {"open": 0, "open-unsure": 0, "closed": 0}
    for t in trips:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    n_action = sum(1 for t in trips if t["severity"] > 0)

    head = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Travel Forms — dashboard</title><style>" + CSS + "</style></head><body><div class='wrap'>"
        "<h1>Travel Forms — dashboard</h1>"
        f"<div class='sub'>Generated {esc(today.isoformat())} · scanned <code>{esc(root)}</code> · "
        f"{len(trips)} trips · {n_action} need action · "
        f"{counts.get('open',0)} open · {counts.get('open-unsure',0)} open-unsure · {counts.get('closed',0)} closed</div>"
        "<div class='controls'>"
        "<input id='q' placeholder='Filter trips…'>"
        "<button class='btn active' data-f='all'>All</button>"
        "<button class='btn' data-f='action'>Needs action</button>"
        "<button class='btn' data-f='open'>Open</button>"
        "<button class='btn' data-f='open-unsure'>Unsure</button>"
        "<button class='btn' data-f='closed'>Closed</button>"
        "</div>"
        "<table><thead><tr>"
        "<th>Trip</th><th>Dates</th><th>Status</th><th>Destination</th>"
        "<th>Trip&nbsp;#</th><th>Abrechnungsfrist</th><th>Registration</th>"
        "<th>Alerts</th><th>Milestones</th></tr></thead><tbody>"
    )

    rows = []
    for t in sort_trips(trips):
        start_k = (t["start"] or dt.date.min).isoformat()
        af_txt = t["af"].isoformat() if t["af"] else "—"
        if t["early_bird"]:
            reg_txt = f"EB {t['early_bird'].isoformat()}"
        elif t["reg"]:
            reg_txt = t["reg"].isoformat()
        else:
            reg_txt = "—"
        if t["angemeldet"]:
            reg_txt += " ✓"
        alert_html = "".join(
            f"<span class='chip {lvl}'>{esc(txt)}</span>" for lvl, txt in t["alerts"]
        ) or "<span class='muted'>—</span>"
        ms_html = "".join(
            (lambda v: f"<span class='m {'yes' if v is True else ('no' if v is False else '')}' "
                       f"title='{esc(lbl)}'>{esc(lbl)}</span>")(t["milestones"].get(key))
            for key, lbl in MILESTONE_LABELS
        )
        zweck = f"<div class='muted'>{esc(t['zweck'])}</div>" if t["zweck"] else ""
        rows.append(
            f"<tr class='{esc(t['status'])}' data-status='{esc(t['status'])}' data-sev='{t['severity']}'>"
            f"<td data-k='{esc(t['event'].lower())}'><span class='event'>{esc(t['event'])}</span>"
            f"<div class='muted'>{esc(t['relpath'])}</div>{zweck}</td>"
            f"<td data-k='{esc(start_k)}'>{esc(fmt_range(t))}</td>"
            f"<td data-k='{esc(t['status'])}'><span class='badge {esc(t['status'])}'>{esc(t['status'])}</span></td>"
            f"<td>{esc(t['ziel'] or '—')}</td>"
            f"<td>{esc(t['reisenummer'] or '—')}</td>"
            f"<td data-k='{esc(t['af'].isoformat() if t['af'] else '')}'>{esc(af_txt)}</td>"
            f"<td data-k='{esc(t['early_bird'].isoformat() if t['early_bird'] else (t['reg'].isoformat() if t['reg'] else ''))}'>{esc(reg_txt)}</td>"
            f"<td data-k='{t['severity']}'>{alert_html}</td>"
            f"<td><div class='ms'>{ms_html}</div></td></tr>"
        )

    hidden_note = (f" · {hidden_closed} closed trip(s) from earlier years hidden "
                   f"(run with <code>--all-closed</code> to show)") if hidden_closed else ""
    foot = (
        "</tbody></table>"
        "<div class='foot'>Read-only view. To change a trip, edit its <code>trip.md</code> "
        "and re-run <code>dashboard.py</code>. Click a column header to sort." + hidden_note + "</div>"
        "<script>" + JS + "</script></div></body></html>"
    )
    return head + "".join(rows) + foot


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="Directory to scan (default: current dir).")
    ap.add_argument("-o", "--output", default=None, help="HTML output path (default: <root>/dashboard.html).")
    ap.add_argument("--text", action="store_true", help="Also print a plain-text table.")
    ap.add_argument("--text-only", action="store_true", help="Print text only; write no HTML.")
    ap.add_argument("--open", dest="open_", action="store_true", help="Open the HTML in the default browser.")
    ap.add_argument("--all-closed", action="store_true",
                    help="Show closed trips from all years (default: only the current year).")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")
    today = dt.date.today()

    trips = [build_trip(p, root, today) for p in find_trip_mds(root)]
    if not trips:
        sys.exit(f"No trip.md files found under {root}.")

    # Closed trips clutter over time — by default only show this year's; keep all
    # open / open-unsure regardless of year.
    hidden_closed = 0
    if not args.all_closed:
        def keep(t):
            if t["status"] != "closed":
                return True
            yr = (t["end"] or t["start"] or dt.date.min).year
            return yr == today.year
        kept = [t for t in trips if keep(t)]
        hidden_closed = len(trips) - len(kept)
        trips = kept

    if args.text or args.text_only:
        sys.stdout.write(render_text(trips, today))

    if not args.text_only:
        out = Path(args.output) if args.output else root / "dashboard.html"
        out.write_text(render_html(trips, today, root, hidden_closed), encoding="utf-8")
        print(f"\nDashboard written: {out}  ({len(trips)} trips, "
              f"{sum(1 for t in trips if t['severity'] > 0)} need action)")
        if args.open_:
            import webbrowser
            webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
