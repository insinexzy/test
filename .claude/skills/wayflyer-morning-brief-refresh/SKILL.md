---
name: wayflyer-morning-brief-refresh
description: Refreshes the Wayflyer morning brief dashboard with today's figures from Stripe, the Supabase churn mirror, Kit, PostHog and YouTube, then republishes it to the same artifact URL. Use this skill whenever the morning dashboard needs updating, when a scheduled morning refresh fires, or when anyone asks about Wayflyer's MRR, community members, churn rate, churn by tenure, pending cancellations, failed or duplicate payments, price mix, new members, YouTube attributed signups, or email list size. Use it even when they only want a single figure, because this skill carries the metric definitions and the traps that make those figures correct, and quoting a number without them is how a wrong number gets acted on. Also use it before quoting any of these figures anywhere else, when asked how one of them is calculated, or when asked to add a metric to the dashboard. The accounts still read "Ben AI" because they predate the rename to Wayflyer; that is the same business.
---

# Wayflyer morning brief refresh

One job: put today's numbers into the page that already exists, without redesigning it and without inventing anything.

The page is read with coffee, once, by three people. It is trusted because every figure on it traces to a pull and the arithmetic is visible. A single wrong number costs more than a whole morning of being late, because a wrong number gets acted on.

## Where the page lives

| | |
|---|---|
| Artifact URL | `https://claude.ai/code/artifact/b9978f14-d36f-4682-b38a-c4e76b78a9c2` |
| Source file | `dashboard/index.html` on branch `claude/analytics-dashboard-builder-iosga3` |
| Title | `Wayflyer Morning Brief` (must not change: it is how people find the page) |
| Favicon | 📈 (must not change, same reason) |

Update it **in place**. From this conversation, republish the same `file_path`. From any other conversation, pass the URL above as the `url` parameter. Publishing without that URL creates a second artifact: the readers keep opening the first one, which has quietly stopped updating, while a fresher copy sits somewhere they never look. That failure is silent and can run for weeks.

## The split that keeps this reliable

**You fetch. The script computes and patches.**

Run `scripts/refresh.py` to do the arithmetic and rewrite the page's `D` object. Do not compute rates conversationally and type them in. Numbers derived in prose cannot be repeated, diffed or checked, and they drift for no reason. The script takes the raw pulls as JSON and produces the same answer from the same inputs every time.

## Order of operations

1. **Snapshot first.** `python3 scripts/refresh.py --snapshot` reads the current `D` object out of `dashboard/index.html` and saves it to `snapshots/D-YYYY-MM-DD.json`. If the page cannot be read, stop and say so. Patching a page you could not read means rebuilding it, which is the exact outcome this skill exists to prevent. The snapshot is also what makes tomorrow's deltas real rather than invented.
2. **Pull.** Run the calls in `references/connectors.md` exactly as written. They are recorded so you repeat them rather than rediscover them. Write the raw results to `pulls/YYYY-MM-DD.json` in the shape the script expects (`--print-schema` shows it).
3. **Compute and check.** `python3 scripts/refresh.py --compute pulls/YYYY-MM-DD.json`. The script does the arithmetic, runs the reconciliation, and trips the guards. It writes nothing if a guard fires.
4. **Patch.** `python3 scripts/refresh.py --apply pulls/YYYY-MM-DD.json` replaces the `D` object and nothing else. It refuses if any key the page reads has gone missing.
5. **Publish** to the URL above.
6. **Log.** The script appends one line to `refresh-log.tsv`. Two mornings should be diffable.
7. **Report** only what the page cannot say. See below.

## The reconciliation that has to close

```
open at window start + new - departed = open today
```

On the day this was built: `678 + 73 - 84 = 667`. It closed exactly.

If it does not close, one of the terms is wrong, and it is usually the departure term. The two ways it has actually broken here are both in `references/traps.md`, with the wrong answer each one produced. Do not publish a churn figure while this line is open, and do not "fix" it by widening a window until the numbers happen to agree.

Reactivations are the term people forget. This mirror stores one row per subscription and no row reactivates, so the term is zero today. If a returning member ever appears as a new row against an old customer, the line will open by exactly that count, and that is the first thing to check.

## Guardrails

Stop and report rather than publish when any of these trip. They are deliberately loose: they exist to catch a broken pull, not a bad week. A genuinely bad week should reach the reader. A source silently returning empty should never reach them dressed as a real number.

| Guard | Threshold |
|---|---|
| Community MRR moved more than 10% in a day | stop |
| Community subscription count moved more than 5% in a day | stop |
| Any headline figure came back zero | stop |
| A required source returned something unusable | stop |
| A key the page reads has disappeared from `D` | stop |

A zero is almost never real. It usually means a source returned an empty list and the arithmetic collapsed quietly. The one genuine zero on this page today is duplicate charges, which the script treats as a real value only when the succeeded-charge scan actually returned charges to check.

## When a source will not answer

Leave its values exactly as they were and render the affected card as not tracked with the reason. `scripts/refresh.py --apply` does this for you when a source key is absent from the pull file.

Never age a number forward as though it were today's. A stale figure presented as current is the single failure mode that actually costs money, because it is the one that gets acted on. The instinct to fill the gap is the thing to resist: a blank prompts a fix, a plausible number prompts a decision.

The upload cadence card ships in exactly this state. YouTube needs one OAuth approval through Composio, and until it is live that card stays hatched and empty. Do not infer upload dates from anywhere else.

## Efficiency

**Rolling windows append, they do not re-pull.** The MRR sparkline needs today's month-end value, not seven months re-derived. The weekly new-member series needs this week's count and the oldest week dropped. Re-pulling the whole window every morning costs seven or eight times as much for the same answer.

**The slow figures do not need daily recomputation.** Churn by tenure is a lifetime hazard over thousands of subscriptions; it moves in fractions of a point per day. Recompute it weekly and let the card state when it was last computed. The script does this automatically from the `computed_on` field, so a daily run stays cheap and the number stays honest.

**Large pulls stay out of the main context.** The Stripe charge searches return well over 100KB per page. Write them to a file and aggregate with `jq` or the script. The page needs the totals, and letting hundreds of raw charge records into context is slow, expensive and adds nothing.

## Patch, do not rebuild

The design is finished and signed off. Replace the `D` object and touch nothing else: no CSS, no chart code, no markup, no layout. If a figure needs a new card, that is a conversation with the reader, not a morning job.

The one structural rule worth remembering: acquisition and retention sit side by side under one rule, at the same size. That arrangement exists because the owner once spent a week pushing the top of the funnel when the problem was out the back. Do not separate them, do not shrink one, do not push retention below the fold.

## Reporting back

They are about to read the page, so do not restate it. Report only what the page cannot tell them:

- What moved and by how much, in percentage points for anything that is already a rate
- Anything rendered as not tracked, and why
- Any guard that tripped, and what happened instead
- Anything that looks like a data problem rather than a business change

If everything refreshed cleanly and nothing moved much, one line is the right length.

## Reference files

| File | Read it when |
|---|---|
| `references/metrics.md` | Any question of what a figure means. Every numerator, denominator and population, plus reference values for the build date so a run can sanity-check itself |
| `references/traps.md` | Before trusting any figure, and whenever one looks wrong. Every way this specific business's data has produced a wrong number, each with the wrong answer it produced. The most valuable file here |
| `references/connectors.md` | Step 2, for the exact calls, response shapes, freshness lags, caps and scope gaps |
