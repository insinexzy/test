# Connectors

The exact calls, in the order the refresh needs them. Repeat these rather than rediscovering them: the shapes, caps and scope gaps below cost real time to establish.

Everything here is **read only**. Stripe, Kit and Circle are production systems holding real money, real subscribers and real members. No figure on this page justifies a write, and a mistake there is not recoverable by editing a file.

## Identities

| Source | Identity | Note |
|---|---|---|
| Stripe | `acct_1QVJOBPt99AmVdwW`, `livemode: true` | named "Ben AI", predates the rename |
| Supabase | project `blyfzoqypkindqlcwzqg` ("Accelerator") | eu-west-1 |
| PostHog | project 245743, org BenAI | project timezone America/Sao_Paulo |
| Kit | account 2155422, creator_pro | owner ben@benai.co |
| Circle | community 222607, slug `bens-ai` | 33,662 active members, mostly free |
| Composio | toolkit `youtube`, account `youtube_prosy-mome` | **no active connection yet** |

## Windows

Compute every window in **Asia/Kolkata**, and stamp the timezone on the page. The readers are in three zones and the PostHog project computes its own days in a fourth, so an unstated timezone makes "month to date" ambiguous on the first and last day of every month.

---

## 1. Stripe price catalogue

`GetPrices` with `{limit: 100, active: true}`. Returns 66 prices, `has_more: false`.

Amounts are **minor units**. Currency is per price, not per account.

Community price ids (`prod_RXDHmdMsfARKqe`), with amount and interval months:

```
price_1Qe8qnPt99AmVdwWKcTef6f3   9700   1
price_1TnbSXPt99AmVdwWhSAi9kn9  12700   1
price_1TYXxuPt99AmVdwWbDboA5Ov   9700   1
price_1TXIYdPt99AmVdwW1gy8LQQJ  14700   1
price_1RWDIYPt99AmVdwWhz8wDzkk  22900   3
price_1SHm45Pt99AmVdwWuf5jnen1  22900   3
price_1Sct0YPt99AmVdwWQ8oJnA6Y  79700  12
price_1TYnqWPt99AmVdwWFHGVD5ut  79700  12
price_1Tny7LPt99AmVdwW8f4FH6wG  99700  12
price_1SAV3CPt99AmVdwWHTaVEpK4  99700  12
price_1TXIYePt99AmVdwWgCT3I8mP  99700  12
price_1RRp3DPt99AmVdwW3jT4fXvd  59700  12
price_1Qe8qnPt99AmVdwWkd3stqUv 104800  12
price_1TnbVyPt99AmVdwWoZ2i6spk 119700  12
```

Re-pull this only when a new price appears in the mirror that is not in the list. `scripts/refresh.py` raises rather than guessing when it meets an unmapped plan, which is what stops a new price from silently scoring zero.

### Scope gap, worth knowing before you try

`stripe_analytics` refuses on both `search_query_tables` and `execute_query_template` with `reporting_write permission is required`. Stripe's own MRR and churn reporting is therefore unavailable, and the page says so in the footer. Do not reconstruct a substitute and present it as the provider's figure. If the scope is ever granted, use it as a cross-check and report divergence.

---

## 2. Supabase, the churn mirror

Freshness is hours, not days: on the build date the last cancellation stamp was 03:47Z and `members.updated_at` was 04:01Z. Even so, anything for a window shorter than a few days comes from live Stripe, because a replica lags and the first symptom is a mirror reporting zero new members while the live system had three.

`public.subscriptions` columns: `stripe_subscription_id`, `member_id`, `customer_email`, `status`, `plan`, `started_at`, `canceled_at`, `discount_percent`.

- `plan` holds the Stripe **price id**, which is what makes MRR computable here.
- No amount, currency or interval column. They come from the catalogue above.
- `discount_percent` is **null on every row**. Net-of-discount MRR is not available from here.
- `member_id` is **null on most rows**. Never use it as a dedupe key (trap 5).

### The one query that produces most of the page

```sql
with px(price_id, amt, months) as (values
  -- the 14 community rows from section 1
),
s as (
  select sub.status, sub.started_at, sub.canceled_at, sub.customer_email,
         (px.amt::numeric / px.months) as mrr_minor,
         case when sub.status = 'canceled' then sub.canceled_at else null end as end_real
  from public.subscriptions sub
  join px on px.price_id = sub.plan
  where sub.status <> 'incomplete_expired'
)
select ... from s
```

Two things in that CTE are load-bearing and both have their own trap entry:

- `where status <> 'incomplete_expired'` excludes 2,749 failed checkouts (trap 1)
- `end_real` is null unless the row has genuinely ended (traps 2 and 3)

Derive from `s`:

| Figure | Expression |
|---|---|
| billing MRR | `sum(mrr_minor) where status in ('active','past_due')` |
| billing subs | `count(*) where status in ('active','past_due')` |
| open now | `count(*) where end_real is null` |
| open at date `d` | `count(*) where started_at < d and (end_real is null or end_real >= d)` |
| new in window | `count(*) where started_at >= t0 and started_at < t1` |
| departed in window | `count(*) where status='canceled' and canceled_at >= t0 and canceled_at < t1` |
| pending cancel | `where status <> 'canceled' and canceled_at is not null` |
| MRR at `d` | `sum(mrr_minor) where started_at::date <= d and (end_real is null or end_real::date > d)` |
| tenure days | `extract(epoch from (coalesce(end_real, now()) - started_at))/86400` |

Unmapped-plan check, run it every time:

```sql
select s.plan, count(*) from public.subscriptions s
left join px on px.price_id = s.plan
where px.price_id is null group by s.plan
```

On the build date this returned exactly one row: the tiered "Team monthly volume" plan, 3 rows, 0 live. Anything else is a new price that needs adding to the catalogue.

---

## 3. Stripe, live, for the 7-day operational figures

Both of these exceed the tool's inline output limit and get written to a file. Aggregate with `jq`; do not let raw charge records into context.

**Failed payments**

```
GetChargesSearch  query: status:'failed' AND created>{now-7d epoch}   limit: 100
```

Then group by customer, take the latest attempt per customer, sum those amounts (trap 6).

**Duplicate charges**

```
GetChargesSearch  query: status:'succeeded' AND created>{now-7d epoch}   limit: 100
```

**Caps at 100 per page and the 7-day window holds ~132.** Follow `next_page` until `has_more` is false, reading the token from the response body rather than reconstructing it (trap 7). Then group by (customer, amount) and flag groups larger than one.

---

## 4. Kit

`get_growth_stats` with `starting` and `ending`.

Returns `subscribers` (point-in-time, excludes inactive, bounced and complained), `new_subscribers`, `cancellations`, `net_new_subscribers`.

Kit exposes three subscriber counts that never agree. Stay on this one (trap 10).

---

## 5. PostHog

Live events that matter: `campaign_page_view`, `accelerator_purchase`, `community_purchase`, `circle_purchase_completed`, `thank_you_page_viewed`, `churned`, `$pageview`, `$identify`.

`campaign_page_view` carries `utm_source`, `utm_campaign`, `utm_content`, `utm_medium`, `$referrer`, `$referring_domain`, `$current_url`. Observed `utm_source` values: `youtube`, `dailymail`, `convertkit`, `promo`, `newsletter`, `promomail`.

The purchase events carry **no** UTM properties, so attribution joins on the person (trap 8):

```sql
WITH buyers AS (
  SELECT DISTINCT person_id AS pid FROM events
  WHERE event IN ('accelerator_purchase','community_purchase','circle_purchase_completed')
    AND timestamp >= now() - INTERVAL 30 DAY),
yt AS (
  SELECT DISTINCT person_id AS pid FROM events
  WHERE event = 'campaign_page_view' AND properties.utm_source = 'youtube'
    AND timestamp >= now() - INTERVAL 120 DAY),
anysrc AS (
  SELECT DISTINCT person_id AS pid FROM events
  WHERE event = 'campaign_page_view' AND properties.utm_source IS NOT NULL
    AND timestamp >= now() - INTERVAL 120 DAY)
SELECT (SELECT count() FROM buyers) AS buyers_30d,
       (SELECT count() FROM buyers WHERE pid IN (SELECT pid FROM yt)) AS buyers_from_youtube,
       (SELECT count() FROM buyers WHERE pid IN (SELECT pid FROM anysrc)) AS buyers_with_any_utm
```

`buyers_30d` is also the cross-check on the mirror's new-member count (trap 9).

---

## 6. Circle

`list_community_members` with `per_page: 1`, then read `count` from the envelope.

**Never paginate.** A single member record is several KB and there are 33,662 of them. The count is in the response envelope precisely so you do not have to.

Circle also carries the original brand colour in `prefs.brand_color` (`#E6C885`). The page does not use it: the brand is Wayflyer, extracted from wayflyer.com.

---

## 7. YouTube, once connected

Not connected. `has_active_connection: false` on the Composio `youtube` toolkit. One OAuth approval is needed, and until then the upload cadence card stays hatched with the reason.

Read-only tools, and the only three this skill should ever call:

- `YOUTUBE_GET_CHANNEL_STATISTICS`
- `YOUTUBE_LIST_CHANNEL_VIDEOS` (`mine: true`)
- `YOUTUBE_GET_VIDEO_DETAILS_BATCH` (caps at 50 ids)

Pitfalls Composio records: statistics counters are string-typed, so cast before arithmetic; `videoId` sits at `items[].snippet.resourceId.videoId`; `snippet` is sometimes a stringified object.

If the approval is declined, the Apify scenarios already in the Make account are a second route.

---

## Reachable but unused

Attio, Calendly, Fireflies, lemlist, Make and Vercel all respond and none of them feeds a card on this page. Recorded so nobody spends a morning re-probing them. Vercel is the alternative host if the dashboard ever needs a custom domain or a login in front of it.
