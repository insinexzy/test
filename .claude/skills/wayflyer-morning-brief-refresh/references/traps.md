# Traps

Every one of these produced a wrong number on this specific business's data during the build, and every one looks like ordinary correct reasoning right up to the figure it produces. Each is written with its wrong answer attached, because the wrong answer is what makes the trap recognisable when you meet it again.

Read this before trusting any figure, and again whenever one looks wrong.

## Contents

- Churn and the subscription lifecycle (1 to 5)
- Payments (6, 7)
- Attribution and counting people (8 to 11)
- Prices and money (12 to 15)
- Windows and comparisons (16, 17)
- Sources that will not answer (18)
- The page itself (19)

---

## 1. Counting `incomplete_expired` as churn

2,749 of the 6,736 rows in `public.subscriptions` carry status `incomplete_expired`. These are checkout attempts where the card never succeeded. Nobody ever paid, so nobody churned.

**Wrong answer:** churn roughly doubles. Including them drags 12.4% up past 25% and makes the business look like it is dying when it is not.

Every population in this skill excludes them. If a churn figure comes back near double what you expected, check this first.

## 2. Reading `canceled_at` as an end date

Stripe stamps `canceled_at` the moment a member *asks* to leave. On a monthly plan they keep paying for up to another month; the subscription only reaches status `canceled` when the period actually closes. The mirror has no `ended_at` column, so `canceled_at` is the only timestamp available and it is a request stamp, not an end stamp.

**Wrong answer:** 155 departures in 30 days instead of 84, churn 20.2% instead of 12.39%, and 79 people counted as gone who are still paying you.

Departures are rows whose status *is* `canceled`. The still-open ones with a stamp are the "leaving now" card, and they are the reachable ones.

## 3. Using `canceled_at` as the end marker for rows that are still open

The mirror image of trap 2, and it bites in the opposite direction. If you compute `end = coalesce(canceled_at, infinity)` you push 79 still-paying subscriptions into the past, because their request stamp is older than the window you are testing.

**Wrong answer, twice over:** the opening balance came back 661 instead of 678, so the reconciliation opened by 17 and looked like missing reactivations. And historical MRR read $57,240.83 for today instead of $64,987.25, understating by $7,649 on every single date in the series, because every pending-cancel subscription was excluded from every past month too.

The correct expression is `end = canceled_at only when status = 'canceled', otherwise open`.

## 4. Population drift between the two sides of the reconciliation

`paused` and `trialing` are neither active nor canceled. Putting them inside the opening balance and outside the closing one silently breaks the line.

**Wrong answer:** `678 + 73 - 84 = 667` against a closing count of 666. Off by exactly one, which is small enough to shrug at and is exactly the kind of discrepancy that hides a real error.

Pick one definition of "open" and use it on both sides. This skill uses "not ended", which is 667 today, and reports the billing population, 666, separately on the card.

## 5. Deduplicating on `member_id`

`member_id` is null on the majority of rows: 209 of the 283 on the main $97 plan alone. It is the Circle linkage and it was never backfilled.

**Wrong answer:** 393 distinct members instead of 666. The count collapses silently, and every per-member rate comes out roughly 70% too high.

Deduplicate on `customer_email`, which is present on every row. Today 666 subscriptions map to 666 distinct emails, so the two agree, but that is a fact to re-verify rather than assume.

## 6. Summing every failed charge attempt

Dunning retries the same card. In the last 7 days, 53 failed attempts came from 24 distinct customers, and one card was tried 5 times.

**Wrong answer:** $6,330.32 outstanding instead of $3,439.89. An 84% overstatement of what is actually recoverable, which turns a morning of chasing into a wasted one.

Group by customer, take the latest attempt per customer, sum those.

## 7. Detecting duplicates on one page of results

Stripe's charge search caps at 100 per page. The 7-day succeeded-charge window held 132.

**Wrong answer:** a confident "zero duplicates" derived from the first 100 charges, with 32 unexamined. A false negative that reads exactly like a real verified zero.

Follow `next_page` until `has_more` is false. Read the token from the response; do not reconstruct it. The zero is only reportable once the whole window has been scanned, and the card says how many charges were checked for exactly this reason.

## 8. Reading `utm_source` off the purchase event

The purchase events (`accelerator_purchase`, `community_purchase`, `circle_purchase_completed`) carry no UTM properties at all. The tag lives on `campaign_page_view`.

**Wrong answer:** zero YouTube attributed buyers out of 145, which reads as "YouTube sends us nobody" for the channel that is actually the main source of the business.

Join purchasers to their earlier `campaign_page_view` on `person_id`. That gives 46 of 77. And note the honest ceiling: 24 of the 77 carry no tag anywhere, so 60% is a floor on YouTube's contribution, never a precise share.

## 9. Counting purchase events as new members

PostHog logged 145 purchase events in 30 days. The mirror recorded 73 new community subscriptions.

**Wrong answer:** 145 new members, double the truth, because the event fires for other products and can fire more than once per purchase.

New members come from the mirror. PostHog's distinct purchaser count, 77, is the cross-check: two independent sources within 5% of each other is corroboration. A gap much wider than that means one of them is broken, and that is worth reporting.

## 10. Kit's three different subscriber counts

`get_growth_stats.subscribers`, `list_subscribers.total_count` and `filter_subscribers.total_count` all look official and all count different populations: point-in-time excluding bounced and complained, active only, and all states respectively. They will never agree.

**Wrong answer:** the email list appears to jump by thousands between two runs that both did nothing wrong.

Stay on `get_growth_stats.subscribers`. 33,311 today.

## 11. Reading Circle's member count as paying members

Circle reports 33,662 active members. That is the whole community including every free member.

**Wrong answer:** 33,662 paying members against $64,890 of MRR, which implies an ARPU of $1.93 and makes every unit economic look absurd.

666 subscriptions pay. Circle's 33,662 and Kit's 33,311 are similar in size and are genuinely different populations, not one number counted twice. Every count on the page states which population it counts, and this trap is why.

## 12. Tiered prices with a null `unit_amount`

One price is volume-tiered: "Team monthly volume - $97 (1-3 seats), $77 (4+ seats)". Its `unit_amount` is null. Reading that field scores the plan at zero without raising an error.

**Wrong answer:** those subscriptions contribute $0 to MRR and nothing anywhere says so.

No live subscription carries it today (3 rows, all ended), so the current figure is unaffected. If one appears, the script raises rather than scoring it zero.

## 13. Quarterly plans stored as a monthly interval with a count of 3

`price_1RWDIYPt99AmVdwWhz8wDzkk` and `price_1SHm45Pt99AmVdwWuf5jnen1` are $229 with `interval: month, interval_count: 3`. Dividing by the interval name alone treats them as monthly.

**Wrong answer:** $229/month each instead of $76.33, overstating those subscriptions threefold.

Always divide by the interval count. This is the single most expensive gotcha in recurring revenue arithmetic.

## 14. Treating BRL amounts as USD

Six live subscriptions are denominated in BRL. Prices in this account are per-price, not per-account: the BRL you see in the Stripe dashboard is the *settlement* layer, not the price denomination.

**Wrong answer:** R$497 read as $497, inflating those subscriptions by roughly 5.4 times.

The community product is entirely USD, so the headline needs no conversion at all. The BRL subscriptions sit outside community scope and carry no converted figure, because a converted number without a sourced and dated rate is untraceable.

## 15. Forgetting that Stripe amounts are in minor units

Every monetary value from Stripe is in the smallest unit. USD cents, BRL centavos.

**Wrong answer:** a 100x overstatement, which is at least obvious. The dangerous version is mixing units within one sum, which is not.

## 16. Plotting a partial period as a real low

The current week and the current month are incomplete. The week of 17 August shows 3 new members because it is four days old, not because acquisition stopped.

**Wrong answer:** reads as a collapse from 20 to 3, an 85% fall, when nothing has happened.

The page marks partial periods in muted ink and labels them "(partial)". Keep that. Never let a partial period set a baseline or an average.

## 17. Comparing a censored window against a settled one

Departures in the last 30 days are systematically undercounted, because members who asked to leave recently have not reached their period end yet. 79 are queued.

**Wrong answer:** churn appears to have halved, 24.4% down to 12.39%, and gets reported as a retention win. Part of that fall is real and part is timing, and nobody can say how much until the queue lands.

The comparison renders neutral, never green, and the card says "window incomplete, will rise". If you are asked whether churn is genuinely improving, the settled answer is the window ending 30 days ago, and say so.

## 18. Reconstructing a figure a refusing source was supposed to give

Stripe's reporting API is blocked: `search_query_tables` and `execute_query_template` both refuse with `reporting_write permission is required`. That is the layer that would have provided an independent MRR and churn cross-check.

**Wrong answer:** a substitute reconstructed from raw records once trended upward for a month the provider itself reported as down. Worse than no chart, because it was believed.

The figures on this page are computed from subscription records, which is defensible, and the footer says plainly that they cannot be cross-checked against Stripe's own. Do not quietly drop that caveat. If the scope is ever added, cross-check and report any divergence rather than assuming the page was right.

## 19. The page's own CSS

`table.bars td { padding: 4px 0 }` outranks `td.vl { padding-right: ... }` on specificity, so the shorthand silently reset every horizontal padding.

**Wrong answer:** bar labels, values and sample sizes rendered touching, as `32.4%n=3,451`. Nothing errored, and it is invisible in the markup.

If a layout edit is ever unavoidable, render it in a browser and look at it. Reading the CSS is not sufficient, because this class of fault only exists in the output.
