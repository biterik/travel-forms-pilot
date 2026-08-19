#!/usr/bin/env python3
"""Reconcile every trip.md against the files actually on disk.

trip.md is maintained by hand and by the agent, so it drifts: an approval comes
back from the Reisestelle, lands in 2_Application/, and nobody flips
`antrag_genehmigt`. The dashboard then reports a gap that does not exist — which
is exactly what happened to Cargese (approval on disk since May 2026, dashboard
still saying "Antrag fehlt" in August).

This script never writes. It prints, per trip, where the FILES disagree with the
MILESTONES, so the disagreement can be fixed deliberately.

Usage:
    python3 audit_trips.py <trips-root> [--all] [--quiet]

    --all     also list trips where files and milestones agree
    --quiet   only the summary counts
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml --break-system-packages")

SKIP_DIRS = ("travel-forms-pilot", "_calendar_test", "_to_delete")

# A returned/approved application, by filename. The Reisestelle is inconsistent:
# sometimes "Bitzek_6568_DR6129_…", sometimes just "…_ok.pdf".
# Approval is decided by FILENAME only. The phrase "wird wie beantragt genehmigt"
# is PRINTED on every blank form (Bearbeitungsvermerke), so searching the text
# marks unapproved applications as approved — it fired on ESMC Lyon, Superbo,
# MRS Boston and DPG Regensburg 2027 on the first run.
# What a returned approval actually looks like: "Bitzek_6568_DR6129_…pdf" or,
# when the Reisestelle omits the number, "…_ok.pdf".
APPROVAL_NAME = re.compile(r"(?<![a-z])dr\d{3,}|[_-]ok\.pdf$", re.I)
DR_IN_NAME = re.compile(r"(?<![A-Za-z])DR\s?(\d{3,})", re.I)
SIGNED_NAME = re.compile(r"sign(ed|d)eb", re.I)
TEMPLATE_NAME = re.compile(r"vorlage|template", re.I)


def pdf_text(p: Path, pages: int = 2) -> str:
    try:
        return subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", str(pages), str(p), "-"],
                              capture_output=True, text=True, timeout=60).stdout.lower()
    except Exception:
        return ""


def header(p: Path) -> dict:
    t = p.read_text(encoding="utf-8", errors="replace")
    if not t.startswith("---"):
        return {}
    parts = t.split("---", 2)
    try:
        return yaml.safe_load(parts[1]) or {} if len(parts) >= 3 else {}
    except Exception:
        return {}


def truthy(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


def evidence(folder: Path) -> dict:
    files = [p for p in folder.rglob("*") if p.is_file()]
    names = [p.name for p in files]
    app_dir = [p for p in files if p.parent.name == "2_Application"]

    approved, approval_file = False, None
    for p in app_dir:
        if APPROVAL_NAME.search(p.name):
            approved, approval_file = True, p.name
            break
    dr = None
    for n in names:
        m = DR_IN_NAME.search(n)
        if m:
            dr = "DR" + m.group(1)
            break

    expense = [p for p in files if p.parent.name == "5_Expense_Report"
               and not TEMPLATE_NAME.search(p.name)]
    return {
        # scoped to 2_Application: a signed Reiseabrechnung in 5_Expense_Report
        # is not evidence that an application was submitted (Königswinter).
        "signed": any(SIGNED_NAME.search(p.name) for p in app_dir),
        "approved": approved,
        "approval_file": approval_file,
        "reisenummer": dr,
        "expense": bool(expense),
        "expense_files": [p.name for p in expense],
        "booking": any(p.parent.name == "3_Booking" for p in files),
    }


CHECKS = [
    ("antrag_gestellt", "signed", "signierter Antrag liegt in 2_Application"),
    ("antrag_genehmigt", "approved", "genehmigter Antrag liegt in 2_Application"),
    ("abrechnung_eingereicht", "expense", "Reiseabrechnung liegt in 5_Expense_Report (gebaut — eingereicht?)"),
    ("reise_gebucht", "booking", "Datei(en) in 3_Booking"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--all", action="store_true", help="also show trips with no findings")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    trips = [p for p in sorted(root.rglob("trip.md"))
             if not any(s in str(p) for s in SKIP_DIRS)]
    if not trips:
        sys.exit(f"No trip.md found under {root}")

    n_find = 0
    for tm in trips:
        folder = tm.parent
        h = header(tm)
        ms = h.get("milestones") or {}
        ev = evidence(folder)
        findings = []

        for key, ekey, why in CHECKS:
            recorded, on_disk = ms.get(key), ev[ekey]
            if on_disk and not truthy(recorded):
                shown = "false" if recorded is False else "leer"
                findings.append(f"{key}: {shown}, aber {why}"
                                + (f" ({ev['approval_file']})" if ekey == "approved" else ""))
            elif truthy(recorded) and not on_disk and ekey in ("approved", "expense"):
                findings.append(f"{key}: true, aber keine Datei dafür ({why})")

        rec_dr = str(h.get("reisenummer") or "").strip()
        if ev["reisenummer"] and not rec_dr:
            findings.append(f"reisenummer: leer, aber {ev['reisenummer']} steht im Dateinamen")
        elif ev["reisenummer"] and rec_dr and rec_dr.upper() != ev["reisenummer"].upper():
            findings.append(f"reisenummer: {rec_dr} in trip.md, {ev['reisenummer']} im Dateinamen")

        if findings:
            n_find += 1
        if args.quiet:
            continue
        if findings or args.all:
            rel = folder.relative_to(root)
            mark = "!!" if findings else "ok"
            print(f"[{mark}] {rel}")
            for f in findings:
                print(f"      - {f}")

    print(f"\n{len(trips)} trips checked, {n_find} with findings.")


if __name__ == "__main__":
    main()
