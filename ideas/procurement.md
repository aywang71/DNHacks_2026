# Federal Procurement Anomaly Detection — Pre-event feasibility results

**Run 31 Aug 2026 (T−5).** Full write-up with charts: artifact "Threshold Bunching Feasibility"
(https://claude.ai/code/artifact/c6a19047-37a0-4dcb-ab69-c4cedae12044)

## Headline: bunching is real and large

Army (awarding sub-agency), award types B + D, transactions 2022-10-01 → 2025-09-30,
award-level total obligation, via USAspending `spending_by_award_count`:

$1,000 bins, 240K–252K — total (of which R&D PSCs):

```
240K  43 (3)    244K  43 (1)    248K   96 (25)
241K  46 (2)    245K  62 (12)   249K  528 (336)   <-- the bunch
242K  43 (2)    246K  54 (6)    250K   90 (51)
243K  54 (3)    247K  51 (11)   251K   26 (0)
```

$100 bins near the line: 249,000–249,400 ≈ 16–20 each; 249,800 → 71;
**249,900 → 284**; 250,000 → 70; **250,100 → 1**.

## Two confounds found

**1. R&D / SBIR dominates the spike.** PSC AC12 alone = 280 of 528. Top recipients are
the DoD SBIR small-business roster (Physical Sciences, TDA Research, Intellisense,
CPS Technologies). R&D PSCs = 336 of 528 in the bunch bin vs 1–12 in neighbours.
Almost certainly Phase I contracts priced to a program ceiling, not splitting.
**Residual after removing R&D: 192 vs ~45 baseline = 4.3× excess — still a real result.**
Exclude or separately model: AC11 AC12 AC21 AC22 AC31 AC32 AC41 AC42 AC51 AC52 AC91
AC92 AJ11 AJ12 AJ21 AJ22 AR11 AR12 AR21 AR22.

**2. Round-number clustering exists independently.** Last-$100 bin vs local baseline:
$100K ≈ 3×, $150K ≈ 4×, $200K ≈ 5×, $300K ≈ 2×, **$250K ≈ 17×**. Round-number dummies
are mandatory in the counterfactual. Direction also separates them: at $100K/$300K the
mass sits *on* the round number; at $250K it sits *below* it 4:1.

## Checklist answers

| Item                 | Answer                                                                                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Base vs modification | `action_type` blank = base award (absence of reason-for-modification code). Cross-check `modification_number` = 0 / P00000.                             |
| Value field          | `potential_total_value_of_award` — FAR 13.003 turns on anticipated value of the requirement. Obligation as robustness check.                             |
| Bunching visible?    | Yes, decisively.                                                                                                                                            |
| Threshold            | $150K pre-2018;**$250K through 30 Sep 2025**; **$350K from 1 Oct 2025** (FAR inflation adjustment). MPT $10K → $15K. Do not span the boundary. |
| Entity ID            | DUNS retired Apr 2022 — FY23–25 extract is all-UEI. Vendor resolution is a**lookup, not a matching problem**. Big schedule win.                     |
| Download             | Custom Award Data, not Award Data Archive. No auth needed.**Andrew must do this — sandbox egress blocks usaspending.gov.**                           |
| Environment          | Andrew must do.                                                                                                                                             |

## Scope decision

Army · 2022-10-01→2025-09-30 · award types B, D only (exclude A, C, IDV_* — delivery
orders run under fair-opportunity rules, not the SAT) · prime award **transactions**
(need `action_type`) · sub-awards off.

## Estimator spec (settled)

Notch, not kink. $1,000 bins; fit $100K–$500K; polynomial p=5 (report 3,4,6,7);
excluded window [$245K, z⁺] with z⁺ solved by the integration constraint; round-number
dummies at $10K and $50K multiples; 500 bootstrap resamples of residuals.

Dropped: micro-purchase threshold as second primitive (signal ~2×, tangled with the
$10K round number). Deferred to MAJOR 5: the FY2026 $350K migration test — first look
shows mass has *not* migrated, but award-level queries, the DoD 90-day reporting lag,
and staggered class-deviation adoption all confound it.

## Prior art confirmed

Closest published work (Empirical Economics 2022, "Bunching below thresholds to
manipulate public procurement") uses **EU TED data** and the Cattaneo–Jansson–Ma density
discontinuity test; finds 10–13% of authorities bunch. Confirms the plan's claim that
nobody has done this on US federal awards. No mature Python CJM implementation — fit the
polynomial counterfactual directly.

## Track read

The estimator is now the stronger half (real result, quantified confound, placebo table).
The verifier is still paper. Leans **Open** unless the verifier comes together fast.
