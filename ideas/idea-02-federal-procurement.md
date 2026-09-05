# Idea 02 — Federal Procurement Anomaly Detection

**Verdict: VIABLE, with one unresolved question that decides it.**
**Track:** Defense, or Open.

---

## The idea

Detect contract splitting — the practice of breaking one large requirement into several smaller awards that each land just under a procurement threshold, to avoid competition requirements.

The federal government obligates hundreds of billions of dollars a year through contracts, and every transaction is public. Award value, awarding office, vendor identity, competition type, and product code all land in USAspending, downloadable by anyone with no authentication.

Procurement rules create thresholds. Above the simplified acquisition threshold a buyer faces full competition requirements — synopsis, solicitation, evaluation. Below it the process is dramatically lighter. The predictable response is to split the requirement. GAO and agency inspectors general write about this pattern regularly.

## The premise

**Every federal contract tool faces the vendor. None faces the auditor.**

The US federal contract data ecosystem is almost entirely market intelligence for contractors — GovWin, GovTribe, Bloomberg Government and a long tail of cheaper competitors help vendors find opportunities, track recompetes, identify vulnerable incumbents, and price to win. Procurement fraud detection products from SAS, Zycus and others are enterprise software sold to organizations for auditing their own internal spend. Academic work on procurement anomaly detection exists but runs largely on EU tender data rather than US federal awards.

Nothing free runs oversight-facing detection over US federal award data with a published false-positive rate.

## The method

**Threshold bunching**, a standard estimator from public finance.

In a clean market, award values form a smooth distribution. If splitting is occurring there is excess mass immediately below the threshold and a deficit immediately above it. The estimator: fit the distribution excluding a window around the threshold, extrapolate the counterfactual through the window, measure observed-minus-expected mass, bootstrap for a confidence interval.

The null is principled rather than invented, the methodology is published and citable, and the output is a single visceral number — *"$X in excess awards clustered just under the line."*

Then drill: which awarding offices and vendor pairs contribute most of the excess, and do the same pairs recur? That ranked list is what the agent narrates.

## The second component

An agent writes the analyst-facing narrative for each flagged cluster, and **every factual span is checked against the source record** — vendor identifier, award value, count, threshold delta, office, date span. Each renders verified, unverifiable, or contradicted. Adversarial mode feeds a degraded record, the agent confabulates, the verifier catches it live.

This lands harder here than in most domains, because the hallucinated claim is about a **named company**. An unverified agent making assertions about specific vendors is not a research curiosity, it is legal exposure. That is a strong demo beat and a real argument.

## The product thesis

The durable asset is an **entity ontology** — vendors resolved across name variants and identifiers, linked to awarding offices, product codes, competition history, and timing. Entity resolution is the genuinely hard part of this domain and everything downstream depends on it.

A one-off analysis is a report. A resolved entity graph that ingests each new quarter is recurring audit infrastructure.

## The unresolved question

**We have not confirmed that bunching is actually visible in the data.**

This is the material difference between this idea and the maritime one, and the team should understand it clearly. The maritime finding has been reproduced on real data. This one has not been tested at all. The effect might be large and clean, or small and ambiguous, and we would find out during the event.

**It can be resolved before the event, without writing code.** Download a USAspending extract for one agency, filter to base awards, take the correct value field, and build a histogram around the threshold in a spreadsheet. Just look at the shape. If there is a visible pile-up below the line, this idea is de-risked substantially. If the distribution looks smooth, we have learned that now.

## Two traps that would quietly ruin the analysis

**Modifications versus base awards.** USAspending transaction data includes contract modifications alongside base awards, and modifications vastly outnumber base awards. Build the distribution without filtering and you double-count, include negative de-obligations, and measure nothing — but the histogram still renders and still looks plausible. This is the failure mode where you do not notice.

**Which value field.** Thresholds apply to the anticipated value of the requirement, not to a single transaction's obligation. Several value fields exist and they mean different things. Choose wrong and the distribution has no reason to bunch, because the threshold never governed that quantity.

Both must be settled before the histogram check is meaningful.

## Honest weaknesses

**Bunching has innocent explanations** — genuine small requirements, budget cycles, standing pricing. Output must be framed as statistical anomalies warranting review, never findings of wrongdoing.

**Entity resolution is the hidden time sink.** Vendor names are inconsistent across records; the federal identifier system changed from DUNS to UEI, so an extract spanning that transition carries both inconsistently. Budget real time and state the residual error rate rather than pretending it is solved.

**Data volume.** Millions of transactions is not a weekend dataset. Scope to one agency and one or two fiscal years before arriving.

**Less visually striking** than a map of ships. Dollar figures are visceral but distributions are not.

## Why it is worth keeping live

The prior-art gap is genuinely clean, the method is squarely in our quantitative wheelhouse, the stakes are legible to any judge, and the entity-ontology thesis is a credible company shape. The architecture is also largely shared with other candidates, so the decision can be deferred.

## What would change the verdict

The spreadsheet histogram. If bunching is visible by eye, this becomes a genuine first-choice contender. If it is not, drop it.
