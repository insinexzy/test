# Connector map — Ben AI business dashboard

Recorded during step 4 of the analytics-dashboard-builder run. Probed 2026-08-19.
Every call below was executed read-only. The refresh skill inherits this file: repeat
these exact calls rather than rediscovering them.

## Surface

Claude Code on the web, hosted container. No source is local-only, so a cloud
schedule can drive the whole refresh. Connector permission prompts must be
approved once by hand before the first unattended run.

---

## Stripe — source of truth for revenue

- Account: `acct_1QVJOBPt99AmVdwW`, name "Ben AI", `livemode: true` (only account in session)
- Call for the price catalog: `GetPrices` with `{limit: 100, active: true}` → 66 prices, `has_more: false`
- **Amounts are in minor units.** USD cents, BRL centavos. Divide by 100.

### Auth scope gap (blocks the reporting layer)

Both of these refuse with `reporting_write permission is required`:

- `stripe_analytics` intent `search_query_tables`
- `stripe_analytics` intent `execute_query_template` (metrics `active_subscribers`,
  `subscriber_churn_rate`, `net_mrr_churn_rate`, ...)

Consequence: Stripe's own churn and MRR reporting cannot be read, so it cannot be
used as an independent cross-check against the figures computed here. Every
Stripe-derived number on the page is computed from subscription records joined to
the price catalog. Flagged on the page rather than hidden.

### Currency

Prices are denominated per-price, **not** in the account's settlement currency:

- USD: the large majority, including every community price
- BRL: 3 recurring prices on `prod_RdwaA6FODkJBLp` (49700/mo, 499700/yr, 644800/yr)
- EUR: one-off prices only, all zero or non-community

The BRL that appears in the Stripe dashboard is the settlement/presentment layer,
not the price denomination. So community MRR is **exact in USD with no conversion**.
A converted figure is needed only for the 6 active BRL subscriptions, and that
conversion needs a sourced and dated rate shown on the card.

### Product scope

`prod_RXDHmdMsfARKqe` is the community (Accelerator) product. Community-only
recurring population is **666 subscriptions**, MRR **$64,890.25**, ARPU **$97.43**.
All recurring products together: 771 subscriptions, $72,130.17 USD + R$2,941.75.

### Traps live in this account

- Quarterly plans stored as `interval: month, interval_count: 3` (`price_1RWDIYPt99AmVdwWhz8wDzkk`,
  `price_1SHm45Pt99AmVdwWuf5jnen1`, 22900). Divide by the interval count, not by 1.
- One tiered price with `unit_amount: null` — "Team monthly volume - $97 (1-3 seats),
  $77 (4+ seats)". Reading `unit_amount` scores it as zero without erroring.
  3 subscriptions carry it, none currently active.
- Discounts are **not** in the mirror (see below). Net-of-discount MRR requires
  reading discounts from Stripe directly.

---

## Supabase — the churn mirror

- Project `blyfzoqypkindqlcwzqg` ("Accelerator"), eu-west-1, ACTIVE_HEALTHY
- Freshness: hours, not days. Last cancellation stamp 2026-08-19 03:47Z,
  `members.updated_at` 04:01Z, `segment_counts_daily` has today's row.
- Still: anything for a window shorter than a few days comes from live Stripe,
  never from here.

Tables that matter: `subscriptions` (6,736), `members` (1,241),
`member_snapshots` (41,988), `segment_counts_daily` (782), `churn_reasons` (16),
`onboarding_calls` (501), `course_enrollments` (16,282), `calendly_bookings` (19).

`subscriptions` columns: `stripe_subscription_id`, `member_id`, `customer_email`,
`status`, `plan`, `started_at`, `canceled_at`, `discount_percent`.

- `plan` holds the Stripe **price id**, so it joins to the price catalog. This is
  what makes MRR computable from the mirror.
- **No amount, currency or interval column.** Those come from the price catalog.
- **`discount_percent` is NULL on every row** (0 distinct values). The mirror
  cannot produce net-of-discount MRR.
- **`member_id` is NULL on the majority of rows** (209 of the 283 on the main
  plan). Never deduplicate on it — the count collapses silently. Use
  `customer_email`.

### Status distribution (whole table)

| status | rows |
|---|---|
| canceled | 3,212 |
| incomplete_expired | 2,749 |
| active | 760 |
| past_due | 11 |
| paused | 3 |
| trialing | 1 |

`incomplete_expired` are checkout attempts that never became paying customers.
They are **not** churn. Including them roughly doubles any churn rate.

### The cancellation-request trap

**84 rows across all products (79 in the community, of which 78 are active or past due) are not yet ended but carry a `canceled_at` stamp.** Stripe stamps
`canceled_at` when cancellation is *requested*; the subscription stays active and
paying until the period ends. So:

- `canceled_at` in window = cancellation **requests**, a leading indicator
- Revenue actually leaving in the month is a different, later number
- Counting one as the other shifts churn by several points

Population breakdown today: 676 active with no cancellation request, 11 past_due,
84 active but leaving, 3 paused, 1 trialing.

### Flow reconciliation (30 days, `incomplete_expired` excluded)

Two different lines both close, and they answer different questions. Say which
one you mean, because they differ by more than a factor of one and a half on the
churn rate.

**All recurring products, departures counted at cancellation request:**

```
768 + 77 - 155 = 690   open today 690   ✓
```

**Community product only, departures counted when the period actually ended.**
This is the one the dashboard uses, because the owner chose period end:

```
678 + 73 - 84 = 667    open today 667   ✓
```

The 155 in the first line counts requests, so it includes the 79 members who have
asked to leave but are still paying. The 84 in the second counts only
subscriptions that have genuinely ended. Reading one as the other moves churn
from 12.4% to 20.2%.

---

## Circle — community membership

- Community `Ben AI`, id 222607, private, slug `bens-ai`, member URLs on
  `accelerator.benai.co`
- Brand colour from `prefs.brand_color`: `#E6C885`, brand text `#17141F` dark / `#111111` light
- **Active members: 33,662.** Read it from the envelope: call
  `list_community_members` with `per_page: 1` and take `count`. Never paginate;
  a single member record is several KB and there are 33k of them.
- This is the whole community including free members. Only ~666 pay. The two are
  different populations and every card must say which it counts.

---

## Kit — email list

- Account `Ben AI`, creator_pro, 35,000 subscriber limit, owner ben@benai.co
- Call: `get_growth_stats` with `starting` / `ending`
- 30 days to 2026-08-19: `subscribers` **33,311**, `new_subscribers` 2,831,
  `cancellations` 3,998, `net_new_subscribers` **−1,167**
- `subscribers` is a point-in-time snapshot, not a sum over the window, and it
  excludes inactive/bounced/complained. It will **not** match
  `list_subscribers.total_count` or `filter_subscribers.total_count` — three
  different populations. Stay on `get_growth_stats.subscribers` so the number does
  not move for no reason.

---

## PostHog — web and attribution

- Project "Ben AI - YouTube Attribution", id 245743, org BenAI, timezone America/Sao_Paulo
- Reachable. Query tools `query-web-overview`, `query-web-stats` available.

Live events (seen in the last 30 days): `$pageview`, `$identify`, `campaign_page_view`,
`accelerator_purchase`, `community_purchase`, `circle_purchase_completed`,
`thank_you_page_viewed`, `calendar_booking_clicked`, `calendar_meeting_scheduled`,
`churned`, `rm_*`, `$web_vitals`, `$rageclick`.

`campaign_page_view` carries `utm_source`, `utm_campaign`, `utm_content`,
`utm_medium`, `$referrer`, `$referring_domain`, `$current_url`.

`utm_source` observed values: **youtube**, dailymail, convertkit, promo, newsletter, promomail.

So **channel-level** YouTube attribution is live and joinable to the purchase
events. **Per-video** attribution depends on `utm_content` / `utm_campaign`
carrying a video identifier, which is not yet verified. If absent, the fix is
tagging outbound video links, a one-off job.

---

## YouTube — reachable, needs one approval

No native connector in this session. Composio has the `youtube` toolkit with the
right tools:

- `YOUTUBE_GET_CHANNEL_STATISTICS` — subscriber count, view count, video count
- `YOUTUBE_LIST_CHANNEL_VIDEOS` — uploads with publish dates
- `YOUTUBE_GET_VIDEO_DETAILS_BATCH` — per-video statistics, up to 50 ids

**`has_active_connection: false`.** One OAuth approval is required before any of
these return data. Until then, YouTube cards render as not tracked.

Pitfalls recorded by Composio: statistics counters are string-typed (cast before
arithmetic); `videoId` is nested at `items[].snippet.resourceId.videoId`; snippet
is sometimes a stringified object.

Public subscriber counts are also rounded by YouTube, so show the total without a
delta unless an exact source exists.

---

## Reachable, not used by the four agreed bands

Probed and responding, but nothing in Revenue / Retention / Acquisition / Audience
needs them. Recorded so nobody re-probes.

| Source | Identity returned |
|---|---|
| Attio | workspace "Ben AI", admin |
| Calendly | user `ben-ai-aryan` |
| Fireflies | account, 18,449 minutes transcribed |
| lemlist | team "Oskar Johnston's Team", benai.co |
| Make | user Aryan, has connected apps including Apify scenarios |
| Vercel | team `insinexzys-projects` — deploy target |

Make's Apify scenarios are a second possible route to YouTube data if the
Composio approval is declined.

---

## Published page and refresh

- Artifact: https://claude.ai/code/artifact/b9978f14-d36f-4682-b38a-c4e76b78a9c2
- Title `Wayflyer Morning Brief`, favicon 📈. Both must stay stable across
  republishes: that is how people find the page again.
- Refresh skill: `.claude/skills/wayflyer-morning-brief-refresh/`
- Routine `trig_01ProAHLxYUyy26bKp5kxXE8`, 01:27 UTC (06:57 IST) daily,
  **created disabled**: Routines made from this session cannot carry MCP
  connectors, so a fired session would have no Stripe, Supabase, Kit or
  PostHog access. Attach connectors in the claude.ai Routines UI, then enable.
