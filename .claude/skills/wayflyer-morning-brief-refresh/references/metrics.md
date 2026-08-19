# Metric definitions

Every figure on the page, with its numerator, its denominator, and the population both are drawn from. Reference values are as at the build date, **20 Aug 2026 (IST)**, so a future run can sanity-check itself against a known-good day.

The governing rule: a numerator and a denominator must come from the same population. Most wrong rates in this domain come from breaking it, and the breakage always looks plausible.

## Scope: what "community" means

The community is Stripe product **`prod_RXDHmdMsfARKqe`**. Its price ids are listed in `connectors.md`.

Everything on the Revenue and Retention bands is community-only. Other recurring products exist and are worth about $7,240/month; they were deliberately cut from the page because they do not change this week's decisions.

Two populations recur, and every card states which it uses:

- **Billing population**: status `active` or `past_due`. 666 subscriptions today. Used for MRR, price mix, ARPU.
- **Open population**: any status except `canceled` and `incomplete_expired`, i.e. not yet ended. 667 today. Used for the reconciliation and the historical series. The extra one is a single paused subscription worth $97.

`past_due` stays in until the member actually cancels. That is the owner's explicit definition: a bounced card is a collections problem, not a departure.

---

## Revenue

### Community MRR (headline)

Sum over the billing population of `unit_amount / interval_months`, in USD.

- `interval_months` is 1 for monthly, 12 for yearly, and **the `interval_count`** for anything else. The two $229 plans are `interval: month, interval_count: 3`, so they divide by 3.
- Amounts are Stripe minor units. Divide by 100.
- No currency conversion. Every community price is USD-denominated.
- Not yet net of discounts: the mirror's `discount_percent` is null on every row, so discounts would need a live per-subscription Stripe pull. The footer says so.

**Reference: $64,890.25 across 666 subscriptions, ARPU $97.43.**

### MRR against target

`value / 100000`. The target is a standing figure the owner runs at, with no date attached.

**Reference: 64.9%.**

### Net this month

Today's month-to-date MRR minus the closing MRR of last month, both on the **open** basis so the two are comparable.

Direction is declared, not inferred: up is good, but anything inside ±$2,000 renders as **flat**, in the neutral accent rather than green. Flat is the state the owner specifically wants flagged, because it is the month where effort is producing nothing.

**Reference: +$1,294.42, flat. Monthly adds: Mar +10,375, Apr +11,079, May +2,203, Jun +1,439, Jul +2,275, Aug +1,294 MTD.** The deceleration after April is the real story and it is why the card carries the series.

### Historical MRR series

MRR at each month end, on the open basis: subscriptions started on or before the date, and not ended on or before it.

The mirror stores only *current* status, so past `paused` and `past_due` states cannot be reconstructed. That is why the series is on the open basis and the headline is on the billing basis, and why they differ by $97 today. The tooltip states this. Do not "fix" the gap by forcing one basis onto the other; the information to do it correctly does not exist.

**Reference: 28 Feb $36,322.58 · 31 Mar $46,697.25 · 30 Apr $57,776.00 · 31 May $59,978.67 · 30 Jun $61,417.58 · 31 Jul $63,692.83 · 20 Aug $64,987.25 (partial).**

### Price mix

Count of billing-population subscriptions grouped by `unit_amount` and interval. Sums to the same 666 as the MRR card, which is the check that the two agree.

**Reference: $97/mo 383 · $127/mo 133 · $797/yr 90 · $997/yr 38 · $597/yr 11 · $147/mo 4 · $1,048/yr 4 · $229/3mo 3.**

### Failed payments

Distinct **customers** with at least one failed charge in the last 7 days, from live Stripe, never the mirror. The amount is the sum of the *latest* failed attempt per customer.

Customers rather than attempts, because dunning retries the same card and the actionable unit is a person to contact.

**Reference: 24 customers, $3,439.89 outstanding, from 53 attempts; 14 customers retried, one card tried 5 times.**

### Duplicate charges

Succeeded charges in the last 7 days grouped by (customer, amount); any group larger than one is a suspect, and the page reports those within 24 hours of each other.

Reportable only once the full window has been paginated. The card states how many charges were checked so the zero is auditable.

**Reference: 0, across 132 charges from 131 customers totalling $12,513.89.**

---

## Retention

### Churn rate

Numerator: subscriptions that **actually ended** in the window, meaning status `canceled` with the end falling inside it.
Denominator: subscriptions **open at the start** of the window.
Both from the community open population.

Reported in percent, and movement in **percentage points**, never as a percent of a percent.

Direction: down is good. A rising churn figure renders bad even though the number went up. Colour comes from that declaration, never from the sign of the change.

This window is **right-censored**: members who requested cancellation recently have not reached period end, so the count is a floor and will rise. The card says so and the comparison against the prior window renders neutral. Trap 17 explains why treating the fall as a win is wrong.

**Reference: 84 / 678 = 12.39% against a 10.0% target. Prior 30 days: 163 / 669 = 24.37%.**

### The reconciliation

```
open at start + new + reactivated - departed = open today
678 + 73 + 0 - 84 = 667   ✓
```

Must close before publishing. The working goes in the churn card's tooltip: a number whose arithmetic is visible gets trusted, one that is asserted gets questioned every month.

### Leaving now

Subscriptions not yet ended that carry a cancellation request. The MRR at risk is those subscriptions' normalised monthly value.

This is the leading indicator and the only genuinely actionable retention number on the page, because these people are still reachable.

**Reference: 79 subscriptions, $7,746.42/month at risk, 11.9% of MRR. 78 of the 79 are active or past_due; the other is trialing. 8 ended in the last 7 days.**

### Churn by tenure

Rate **per band**, not a share of cancellations. A share chart only tells you most members are new, which is true of every business and actionable in none.

- Numerator: subscriptions that ended with tenure falling inside the band.
- Denominator: every subscription that **reached the start of that band**, whether it later left or is still open.
- Tenure is `end - started_at` for ended rows and `now - started_at` for open ones.

Bands and reference values:

| Band | Ended | Reached | Rate |
|---|---|---|---|
| 0 to 1 mo | 1,118 | 3,451 | 32.4% |
| 1 to 3 mo | 1,018 | 2,254 | 45.2% |
| 3 to 6 mo | 401 | 1,036 | 38.7% |
| 6 mo + | 247 | 414 | 59.7% |

The final band is **open-ended**, so its rate is not comparable with the fixed-width bands above it: it accumulates everyone who ever left after six months, including at two years. It is drawn in a different accent and the caveat is in the tooltip. Do not present it as "six-month members churn worst".

This is a lifetime hazard across all cohorts. It moves in fractions of a point per day, so weekly recomputation is honest as long as the card says when it was last computed.

The decision it drives: heavy in the first band is an onboarding problem and the welcome sequence gets fixed. Heavy in the last band is a value problem and what gets delivered has to change. Two different actions, which is why a single churn percentage cannot replace this card.

---

## Acquisition

### New paying members

New community subscriptions started in the window, from the mirror.

Cross-checked against PostHog's distinct purchaser count over the same window. Two sources within 5% is corroboration; a wider gap means one is broken and should be reported.

The prior-window comparison is **confounded** and renders neutral: the previous 30 days contained a launch spike of 67 and 44 in the first two July weeks. A like-for-like comparison is not available, and rendering a 58% fall in red would assert a conclusion the data does not support.

**Reference: 73 in 30 days, 172 prior. PostHog: 77 distinct purchasers. Weekly: 44, 67, 18, 19, 15, 18, 20, 3 (partial).**

### Of which YouTube

Purchasers in the window who had an earlier `campaign_page_view` carrying `utm_source = youtube`, joined on `person_id` over a 120-day lookback.

A **floor**, not a share: 24 of the 77 purchasers carry no source tag anywhere, so untagged traffic could include more YouTube. The card says "at least".

The fix that would make this precise is tagging outbound video links so `utm_content` carries a video id. That is a one-off job and it would unlock per-video conversion, which was cut from this page only because the tag does not exist yet.

**Reference: 46 of 77, at least 60%. 28,862 tagged YouTube arrivals in 120 days.**

---

## Audience

### Email list

Kit `get_growth_stats` over the window. Use `subscribers` for the size and `net_new_subscribers` for the change.

Direction: up is good, so the current value renders bad.

**Reference: 33,311 subscribers, net −1,167 over 30 days, 2,831 in and 3,998 out.**

### Upload cadence

Not tracked. YouTube needs one OAuth approval through Composio. The card renders hatched and empty with the reason inside it.

When the connection goes live: `YOUTUBE_LIST_CHANNEL_VIDEOS` with `mine: true`, bucket `publishedAt` into the last 8 ISO weeks in Asia/Kolkata, and mark weeks below the target of 2. Cast the string-typed counters before arithmetic and read `videoId` from `items[].snippet.resourceId.videoId`.

Do not show the channel subscriber count. It was cut deliberately: a follower total with no direction cannot be good or bad, and YouTube rounds it publicly, so a delta built from two rounded totals can be wrong by the whole rounding unit.
