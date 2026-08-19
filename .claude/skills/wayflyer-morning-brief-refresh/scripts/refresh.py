#!/usr/bin/env python3
"""
Refresh the Wayflyer morning brief.

The agent fetches; this script computes and patches. Numbers derived in prose
cannot be repeated, diffed or checked, and they drift for no reason. Same
inputs in, same numbers out, every morning.

  refresh.py --snapshot                 save the live D object to snapshots/
  refresh.py --print-schema             show the pull file shape
  refresh.py --compute  pulls/DATE.json compute, reconcile, run guards, write nothing
  refresh.py --apply    pulls/DATE.json the above, then patch the page and log

A source absent from the pull file keeps yesterday's values and its card is
marked not tracked. That is deliberate: a blank prompts a fix, a plausible
number prompts a decision.
"""

import argparse, json, os, subprocess, sys, datetime, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PAGE = os.environ.get("BRIEF_PAGE") or os.path.join(SKILL, "..", "..", "..", "dashboard", "index.html")
PAGE = os.path.abspath(PAGE)
SNAPS = os.path.join(SKILL, "snapshots")
LOG = os.path.join(SKILL, "refresh-log.tsv")

# Keys the render reads. If one vanishes the page breaks silently, so refuse.
REQUIRED = [
    "meta.date", "meta.tz", "meta.fresh",
    "mrr.value", "mrr.target", "mrr.subs", "mrr.arpu", "mrr.series", "mrr.pop", "mrr.tip",
    "net.value", "net.band", "net.adds",
    "newmem.v30", "newmem.vprior", "newmem.weeks",
    "yt.buyers", "yt.total", "yt.visitors120", "yt.untagged",
    "churn.rate", "churn.target", "churn.prevRate",
    "churn.open0", "churn.new", "churn.gone", "churn.openNow",
    "pending.subs", "pending.mrr", "pending.gone7d", "pending.shareOfMrr",
    "tenure.bands", "mix.rows", "mix.total", "mix.arpu",
    "failed.customers", "failed.amount", "failed.attempts",
    "dupes.count", "dupes.scanned", "dupes.customers", "dupes.gross",
    "email.subs", "email.net", "email.gained", "email.lost",
    "upload.tracked", "caveats",
]

GUARDS = {"mrr_pct": 10.0, "subs_pct": 5.0}


# ---------------------------------------------------------------- page access
def read_page():
    if not os.path.exists(PAGE):
        die("cannot read the page at %s. Stop: patching a page you could not "
            "read means rebuilding it, which is what this skill exists to prevent." % PAGE)
    return open(PAGE, encoding="utf-8").read()


def locate(src):
    """Brace-match the D object literal. Returns (start, end) over '{...}'."""
    anchor = src.find("const D = {")
    if anchor < 0:
        die("could not find 'const D = {' in the page. Refusing to guess.")
    start = src.index("{", anchor)
    depth, i, instr, esc = 0, start, None, False
    while i < len(src):
        c = src[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == instr:
                instr = None
        elif c in "\"'":
            instr = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    die("the D object literal is unbalanced. Refusing to patch.")


def to_obj(js_text):
    """Evaluate the object literal with node, so JS syntax is handled exactly."""
    if not shutil.which("node"):
        die("node is required to read the data object safely.")
    out = subprocess.run(
        ["node", "-e", "process.stdout.write(JSON.stringify(" + js_text + "))"],
        capture_output=True, text=True)
    if out.returncode != 0:
        die("could not evaluate the data object: " + out.stderr.strip()[:400])
    return json.loads(out.stdout)


def get(obj, path, default=None):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def die(msg):
    print("STOP: " + msg, file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------- schema help
SCHEMA = {
    "as_of": "2026-08-21  (date the windows end, Asia/Kolkata)",
    "mirror": {
        "_note": "omit this whole key if Supabase did not answer",
        "billing_mrr_minor": 6489025, "billing_subs": 666, "billing_emails": 666,
        "open_now": 667, "open_at_t0": 678, "open_at_t0p": 669,
        "new_30d": 73, "new_prior_30d": 172,
        "departed_30d": 84, "departed_prior_30d": 163,
        "pending_subs": 79, "pending_mrr_minor": 774642, "departed_7d": 8,
        "month_end": [{"d": "2026-08-21", "mrr_minor": 6498725}],
        "weeks_new": [{"d": "2026-08-17", "v": 3, "partial": True}],
        "mix": [{"amt_minor": 9700, "months": 1, "n": 383}],
        "tenure": {"_note": "weekly is enough, it moves in fractions of a point",
                   "computed_on": "2026-08-20",
                   "bands": [{"l": "0 to 1 mo", "ended": 1118, "reached": 3451}]},
        "unmapped_plans": []
    },
    "stripe": {
        "_note": "omit if the charge searches did not complete",
        "failed_customers": 24, "failed_amount_minor": 343989, "failed_attempts": 53,
        "failed_retried": 14, "failed_max_attempts": 5,
        "dupe_groups": 0, "succeeded_scanned": 132, "succeeded_customers": 131,
        "succeeded_gross_minor": 1251389,
        "succeeded_fully_paginated": True
    },
    "kit": {"_note": "omit if Kit did not answer",
            "subscribers": 33311, "net": -1167, "gained": 2831, "lost": 3998},
    "posthog": {"_note": "omit if PostHog did not answer",
                "buyers_30d": 77, "buyers_from_youtube": 46, "buyers_with_any_utm": 53,
                "yt_visitors_120d": 28862},
    "youtube": {"_note": "omit entirely while the connection is not live",
                "weeks": [{"d": "2026-08-17", "uploads": 1}]},
}


# ---------------------------------------------------------------- computation
def compute(old, pull):
    """Returns (new_D, notes, stops). Never mutates old."""
    new = json.loads(json.dumps(old))
    notes, stops, untracked = [], [], []
    as_of = pull.get("as_of")
    if not as_of:
        stops.append("pull file has no as_of date")
        return new, notes, stops, untracked

    d = datetime.date.fromisoformat(as_of[:10])
    new["meta"]["date"] = d.strftime("%a %d %b %Y")
    fresh = {f["k"]: f["v"] for f in new["meta"]["fresh"]}

    # ---- mirror: revenue, churn, acquisition
    m = pull.get("mirror")
    if not m:
        untracked.append("Supabase mirror did not answer: revenue, churn and "
                         "acquisition figures are yesterday's and are not today's")
        fresh["mirror"] = "no answer"
    else:
        if m.get("unmapped_plans"):
            stops.append("unmapped plan ids in the mirror, which would score as "
                         "zero MRR without erroring: " + ", ".join(map(str, m["unmapped_plans"])))
        mrr = m["billing_mrr_minor"] / 100.0
        subs = m["billing_subs"]

        # guards, against the snapshot we are replacing
        old_mrr, old_subs = get(old, "mrr.value"), get(old, "mrr.subs")
        if old_mrr:
            mv = abs(mrr - old_mrr) / old_mrr * 100
            if mv > GUARDS["mrr_pct"]:
                stops.append("MRR moved %.1f%% in a day (%s to %s), over the %.0f%% guard"
                             % (mv, fmt(old_mrr), fmt(mrr), GUARDS["mrr_pct"]))
        if old_subs:
            sv = abs(subs - old_subs) / old_subs * 100
            if sv > GUARDS["subs_pct"]:
                stops.append("subscription count moved %.1f%% in a day (%d to %d), over the %.0f%% guard"
                             % (sv, old_subs, subs, GUARDS["subs_pct"]))
        for label, val in (("MRR", mrr), ("subscriptions", subs),
                           ("open now", m["open_now"]), ("new in 30d", m["new_30d"])):
            if not val:
                stops.append("%s came back zero. A zero here is almost never real: "
                             "it usually means a source returned an empty list and the "
                             "arithmetic collapsed quietly." % label)

        # the reconciliation, before anything is published
        lhs = m["open_at_t0"] + m["new_30d"] - m["departed_30d"]
        if lhs != m["open_now"]:
            stops.append("reconciliation does not close: %d + %d - %d = %d but %d are open "
                         "today, a gap of %d. One of the terms is wrong, usually the "
                         "departure term. See traps 2, 3 and 4."
                         % (m["open_at_t0"], m["new_30d"], m["departed_30d"], lhs,
                            m["open_now"], m["open_now"] - lhs))
        else:
            notes.append("reconciliation closes: %d + %d - %d = %d"
                         % (m["open_at_t0"], m["new_30d"], m["departed_30d"], m["open_now"]))

        # Bail before computing anything from figures a guard has already rejected.
        # A stop plus continued arithmetic is how a zero becomes a traceback instead
        # of a readable report.
        if stops:
            return new, notes, stops, untracked

        new["mrr"]["value"] = round(mrr, 2)
        new["mrr"]["subs"] = subs
        new["mrr"]["emails"] = m.get("billing_emails", subs)
        new["mrr"]["arpu"] = round(mrr / subs, 2) if subs else 0
        new["mrr"]["pop"] = "%d community subscriptions, status active or past due" % subs

        # rolling series: append today, keep 7 points. do not re-pull the window.
        for pt in m.get("month_end", []):
            append_series(new["mrr"]["series"], pt["d"], pt["mrr_minor"] / 100.0, d, 7)
        new["net"]["value"] = round(rebuild_adds(new["mrr"]["series"], new["net"]["adds"], d), 2)

        # churn, at period end, right-censored by design (trap 17)
        new["churn"]["rate"] = round(m["departed_30d"] / m["open_at_t0"] * 100, 2)
        new["churn"]["open0"] = m["open_at_t0"]
        new["churn"]["new"] = m["new_30d"]
        new["churn"]["gone"] = m["departed_30d"]
        new["churn"]["openNow"] = m["open_now"]
        if m.get("open_at_t0p") and m.get("departed_prior_30d") is not None:
            new["churn"]["prevRate"] = round(m["departed_prior_30d"] / m["open_at_t0p"] * 100, 2)
        new["churn"]["reconTip"] = (
            "Flow reconciliation, community subscriptions not yet ended: %d open at start "
            "plus %d new minus %d departed equals %d open today. Closes exactly."
            % (m["open_at_t0"], m["new_30d"], m["departed_30d"], m["open_now"]))

        new["pending"]["subs"] = m["pending_subs"]
        new["pending"]["mrr"] = round(m["pending_mrr_minor"] / 100.0, 2)
        new["pending"]["gone7d"] = m["departed_7d"]
        new["pending"]["shareOfMrr"] = round(m["pending_mrr_minor"] / 100.0 / mrr * 100, 1)

        new["newmem"]["v30"] = m["new_30d"]
        new["newmem"]["vprior"] = m["new_prior_30d"]
        for wk in m.get("weeks_new", []):
            append_series(new["newmem"]["weeks"], wk["d"], wk["v"], d, 8, partial=wk.get("partial"))

        if m.get("mix"):
            rows = sorted(m["mix"], key=lambda r: -r["n"])
            new["mix"]["rows"] = [{"l": price_label(r), "n": r["n"]} for r in rows]
            new["mix"]["total"] = sum(r["n"] for r in rows)
            new["mix"]["arpu"] = new["mrr"]["arpu"]
            if new["mix"]["total"] != subs:
                stops.append("price mix sums to %d but the billing population is %d. "
                             "Every breakdown of a card must sum to that card."
                             % (new["mix"]["total"], subs))

        t = m.get("tenure")
        if t and t.get("bands"):
            new["tenure"]["bands"] = t["bands"]
            new["tenure"]["computed_on"] = t.get("computed_on", as_of[:10])
        fresh["mirror"] = as_of[11:16] + "Z" if len(as_of) > 11 else "today"

    # ---- live Stripe, 7 day operational
    st = pull.get("stripe")
    if not st:
        untracked.append("Stripe charge searches did not complete: failed and duplicate "
                         "payments are yesterday's")
        fresh["Stripe"] = "no answer"
    else:
        new["failed"]["customers"] = st["failed_customers"]
        new["failed"]["amount"] = round(st["failed_amount_minor"] / 100.0, 2)
        new["failed"]["attempts"] = st["failed_attempts"]
        new["failed"]["retried"] = st.get("failed_retried", 0)
        new["failed"]["maxAttempts"] = st.get("failed_max_attempts", 0)
        # a zero is only reportable once the whole window has been paginated (trap 7)
        if st["dupe_groups"] == 0 and not st.get("succeeded_fully_paginated"):
            stops.append("duplicate charges came back zero but the succeeded-charge scan "
                         "was not fully paginated. That is a false negative, not a "
                         "verified zero. Follow next_page until has_more is false.")
        new["dupes"]["count"] = st["dupe_groups"]
        new["dupes"]["scanned"] = st["succeeded_scanned"]
        new["dupes"]["customers"] = st["succeeded_customers"]
        new["dupes"]["gross"] = round(st["succeeded_gross_minor"] / 100.0, 2)
        fresh["Stripe"] = "live"

    # ---- Kit
    k = pull.get("kit")
    if not k:
        untracked.append("Kit did not answer: the email list figure is yesterday's")
        fresh["Kit"] = "no answer"
    else:
        new["email"].update(subs=k["subscribers"], net=k["net"],
                            gained=k["gained"], lost=k["lost"])
        fresh["Kit"] = d.strftime("%d %b")

    # ---- PostHog attribution
    ph = pull.get("posthog")
    if not ph:
        untracked.append("PostHog did not answer: the YouTube attributed share is yesterday's")
        fresh["PostHog"] = "no answer"
    else:
        new["yt"].update(buyers=ph["buyers_from_youtube"], total=ph["buyers_30d"],
                         visitors120=ph["yt_visitors_120d"],
                         untagged=ph["buyers_30d"] - ph["buyers_with_any_utm"])
        fresh["PostHog"] = "live"
        if m:  # cross-source check (trap 9)
            a, b = ph["buyers_30d"], m["new_30d"]
            if b and abs(a - b) / max(a, b) > 0.25:
                notes.append("data problem to look at: PostHog counts %d purchasers where the "
                             "mirror counts %d new subscriptions. Beyond 25%% apart, one of "
                             "them is broken rather than merely differently scoped." % (a, b))

    # ---- YouTube: stays not tracked until the connection is live
    yt = pull.get("youtube")
    if yt and yt.get("weeks"):
        new["upload"]["tracked"] = True
        new["upload"]["weeks"] = yt["weeks"]
        fresh["YouTube"] = "live"
    else:
        new["upload"]["tracked"] = False
        fresh["YouTube"] = "not connected"

    new["meta"]["fresh"] = [{"k": k2, "v": v} for k2, v in fresh.items()]
    return new, notes, stops, untracked


def price_label(r):
    amt, mo = r["amt_minor"] / 100.0, r["months"]
    unit = "mo" if mo == 1 else ("yr" if mo == 12 else "%d mo" % mo)
    return "$%s / %s" % (("%d" % amt if amt == int(amt) else "%.2f" % amt), unit)


def append_series(series, date_str, value, today, keep, partial=None):
    """Append or replace the newest point, then trim. Rolling windows append."""
    label = datetime.date.fromisoformat(date_str).strftime("%d %b").lstrip("0")
    pt = {"d": label, "v": round(value, 2)}
    if partial:
        pt["partial"] = True
    if series and series[-1].get("d") == label:
        series[-1] = pt
    else:
        series.append(pt)
    del series[:max(0, len(series) - keep)]


def rebuild_adds(series, adds, today):
    """Net added per month, derived from the month-end series so the two agree."""
    out = []
    for i in range(1, len(series)):
        out.append({"d": series[i]["d"].split()[-1], "v": round(series[i]["v"] - series[i - 1]["v"], 2)})
    if out:
        out[-1]["partial"] = True
        del adds[:]
        adds.extend(out)
        return out[-1]["v"]
    return 0.0


def fmt(v):
    return "{:,.2f}".format(v)


# ---------------------------------------------------------------- entrypoints
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--print-schema", action="store_true")
    ap.add_argument("--compute")
    ap.add_argument("--apply")
    a = ap.parse_args()

    if a.print_schema:
        print(json.dumps(SCHEMA, indent=2))
        return

    src = read_page()
    s, e = locate(src)
    old_text = src[s:e]
    old = to_obj(old_text)

    missing = [k for k in REQUIRED if get(old, k) is None]
    if missing:
        die("keys the page reads are missing from the live data object: %s" % ", ".join(missing))

    if a.snapshot:
        os.makedirs(SNAPS, exist_ok=True)
        stamp = (datetime.datetime.now(datetime.timezone.utc)
                 + datetime.timedelta(hours=5, minutes=30)).date().isoformat()
        p = os.path.join(SNAPS, "D-%s.json" % stamp)
        json.dump(old, open(p, "w", encoding="utf-8"), indent=1)
        print("snapshot written to %s" % p)
        print("headline: MRR %s across %d subs, churn %.2f%%"
              % (fmt(old["mrr"]["value"]), old["mrr"]["subs"], old["churn"]["rate"]))
        return

    path = a.compute or a.apply
    if not path:
        ap.print_help()
        return
    pull = json.load(open(path, encoding="utf-8"))

    new, notes, stops, untracked = compute(old, pull)

    gone = [k for k in REQUIRED if get(new, k) is None]
    if gone:
        stops.append("these keys would disappear from the data object, which breaks the "
                     "page silently: %s" % ", ".join(gone))

    for n in notes:
        print("note:      " + n)
    for u in untracked:
        print("untracked: " + u)
    print("headline:  MRR %s (was %s) · subs %d (was %d) · churn %.2f%% (was %.2f%%)"
          % (fmt(new["mrr"]["value"]), fmt(old["mrr"]["value"]),
             new["mrr"]["subs"], old["mrr"]["subs"],
             new["churn"]["rate"], old["churn"]["rate"]))
    print("           churn moved %+.2f percentage points"
          % (new["churn"]["rate"] - old["churn"]["rate"]))

    if stops:
        for st in stops:
            print("GUARD:     " + st, file=sys.stderr)
        print("\nNothing was written. Being a morning late is recoverable; a wrong "
              "number that gets acted on is not.", file=sys.stderr)
        sys.exit(3)

    if a.compute:
        print("\nchecks pass, nothing written (use --apply to patch)")
        return

    patched = src[:s] + json.dumps(new, indent=2, ensure_ascii=False) + src[e:]
    open(PAGE, "w", encoding="utf-8").write(patched)
    print("\npatched %s (data object only, no markup or CSS touched)" % PAGE)

    first = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as fh:
        if first:
            fh.write("date\tmrr\tsubs\tchurn\tpending\tsources_missing\tguards\n")
        fh.write("\t".join([
            pull.get("as_of", "")[:10], "%.2f" % new["mrr"]["value"], str(new["mrr"]["subs"]),
            "%.2f" % new["churn"]["rate"], str(new["pending"]["subs"]),
            ",".join(sorted(set(u.split()[0] for u in untracked))) or "-", "-"]) + "\n")
    print("logged to %s" % LOG)
    print("\nNow republish to the artifact URL in SKILL.md. Publishing without it "
          "creates a second copy that nobody reads.")


if __name__ == "__main__":
    main()
