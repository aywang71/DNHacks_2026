# Investigation Brief 03 — Hospital Supply Chain Coordination

**Feasibility verdict for DNHacks 2026, Health & Public Service track**
*All data claims below were verified by live API call or primary-source fetch on 2026-08-23. Nothing here is from memory.*

---

## 1. Verdict: **BUILD REDUCED**

**The single most important reason: the coordination premise is dead, but the substitution premise is alive and better than expected.**

FDA shortage data has no facility dimension and no regional dimension. Hospital-to-hospital routing has no factual substrate — you would have to invent every input, and therefore every output. Drop it.

But the investigation surfaced something the brief did not anticipate: the openFDA shortage record **carries an RxNorm `rxcui` natively**, which opens a fully free, no-API-key, verified path from "this drug is short" to "here are its pharmacologic alternatives — and here is which of those are *also* short." That cross-reference is real, computable end to end from public data, non-obvious, and not covered by existing tools.

Separately, a genuine geographic dimension does exist — just not in the shortage data. CMS Part B and Part D utilization files give **provider-NPI-level drug volumes with city and state**, 2013–2024, free. Joining shortage drugs to real utilization produces a real exposure map with nothing invented.

So the project survives, at full strength, with the center of gravity moved from *coordination* to **substitution triage + exposure**.

---

## 2. The granularity finding

**openFDA `/drug/shortages` is national, at the granularity of drug × dosage form × presentation × company.**

It is *finer* than the brief feared — it is per-manufacturer, not merely per-drug, so you can see that 3 of 5 labelers of a molecule are out while 2 still ship. That is a real supply-concentration signal.

But it has **no facility field, no state field, no region field, no quantity field, and no inventory field.** There is no geography in it of any kind.

Verified live: 1,651 records, `last_updated` 2026-08-07.

| Status             | Count        |
| ------------------ | ------------ |
| Current            | 1,177        |
| To Be Discontinued | 441          |
| **Resolved** | **10** |

**Consequence for coordination:** dead. There is no "which hospital has surplus," because there is no hospital in the data at all.

**Consequence for forecasting — and this contradicts the brief's assumption:** the resolved-shortage count is **10**, not thousands. The API is a live snapshot, not a historical panel. Resolved records roll off. You cannot fit a survival model on 10 uncensored observations, and training only on shortages that are *still active* is textbook survivorship bias. The brief guessed forecasting was "probably the strongest fallback." **It is the weakest.** See §4.

---

## 3. Verified data access

### Confirmed working, free, no gate

| Source                                                              | URL                                                                            | Format / granularity                                                                    | Update freq                          | Notes                                                                                                                                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **openFDA Drug Shortages**                                    | `api.fda.gov/drug/shortages.json`                                            | JSON; drug × form × presentation × company; national                                 | Snapshot,`last_updated` 2026-08-07 | 1,651 records.**Confirmed live.**                                                                                                                                         |
| **RxNav / RxNorm REST**                                       | `rxnav.nlm.nih.gov/REST/`                                                    | JSON; concept-level                                                                     | Continuous                           | No API key. Verified`rxcui/{id}/related.json`.                                                                                                                                |
| **RxClass**                                                   | `rxnav.nlm.nih.gov/REST/rxclass/`                                            | JSON; ATC / EPC / MOA classes                                                           | Continuous                           | **"No license is needed."** Verified both legs (see below).                                                                                                               |
| **CMS Hospital General Information**                          | `data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0`               | JSON/CSV;**5,419 hospitals**                                                      | Quarterly                            | Verified live.                                                                                                                                                                  |
| **CMS Part D Prescribers by Provider & Drug**                 | `data.cms.gov/data-api/v1/dataset/9552739e-3d05-4c1b-8eff-ecabf391e2e5/data` | JSON + CSV;**NPI-level**, city + state, generic name, claims, cost, beneficiaries | Annual, 2013–2024                   | Verified live. Public domain.                                                                                                                                                   |
| **CMS Physician & Other Practitioners by Provider & Service** | `data.cms.gov/data-api/v1/dataset/92396110-2aed-4d63-a6a2-5d6207d46a29/data` | NPI × HCPCS incl.**drug J-codes**                                                | Annual, 2013–2024                   | This is the Part B leg — where the injectables live.                                                                                                                           |
| **openFDA NDC Directory**                                     | `api.fda.gov/drug/ndc.json`                                                  | JSON; product/package level                                                             | Weekly                               | Verified. Has`marketing_start_date`, `packaging`, `marketing_category`. **No `marketing_status` or `marketing_end_date` at top level** — do not plan on those. |
| **340B OPAIS CE Daily Report**                                | `340bopais.hrsa.gov/Reports`                                                 | Excel + JSON; entity + address + 340B ID + contract pharmacies                          | **Daily**, 00:00–02:00 ET     | Explicitly "anonymously accessible," no login.                                                                                                                                  |
| **FDA Orange Book**                                           | `open.fda.gov/data/orangebook/`                                              | Zipped text files; TE codes (AB ratings)                                                | Monthly                              | Free download. The rigorous equivalence layer if you want one.                                                                                                                  |

### Confirmed gated — do not build on these

| Source                                           | Status                                                                                                                                                                                                                                    |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ASHP Drug Shortages API**                | **Licensed. API key required.** Docs public at `github.com/ASHP-Software/drugShortagesDoc`; the key is not. "To request an API key and licensing information, contact softwaresupport@ashp.org." Their RSS feed was discontinued. |
| **HIFLD Open Hospitals** (beds + lat/long) | **Availability uncertain.** Now surfaced via the Data Rescue Project / DataLumos archive, which implies removal from the original open portal. Do not make bed counts load-bearing.                                                 |

The ASHP gate stings, because their schema contains exactly what this project wants — `alternativeAgent`, `patientCareImplications`, `resupplyEstimateNote`, and `/pastDrugShortages` history with `shortageStatus: Resolved`. **This is the "mid-event discovery" the investigation existed to prevent.** Do not plan around ASHP. If someone wants to email for a key as a lottery ticket, fine, but assume no.

### The substitution chain — verified end to end

This is the core technical asset. Both legs confirmed by live call:

1. Shortage record → `openfda.rxcui` *(present in the shortage payload itself — no fuzzy name matching needed)*
2. `rxclass/class/byRxcui.json?rxcui=6902&relaSource=ATC` → methylprednisolone → **H02AB Glucocorticoids** (plus 3 other ATC classes)
3. `rxclass/classMembers.json?classId=H02AB&relaSource=ATC` → **17 members**: dexamethasone, prednisone, prednisolone, hydrocortisone, betamethasone, triamcinolone, cortisone, deflazacort, vamorolone, …
4. Re-join those members back against the shortage list → **which alternatives are also short**

Step 4 is the product. Steps 1–3 are plumbing.

### Fields actually present in a shortage record

`update_type`, `initial_posting_date`, `update_date`, `change_date`, `status`, `availability`, `shortage_reason`, `resolved_note`, `related_info`, `generic_name`, `company_name`, `contact_info`, `therapeutic_category`, `dosage_form`, `presentation`, `package_ndc`, and nested `openfda{ rxcui, product_ndc, brand_name, generic_name, substance_name, manufacturer_name, unii, spl_id, spl_set_id, application_number, route, product_type }`.

**Answering the brief's specific questions:**

- **Shortage reason? Yes**, verified distribution: Other 142, Demand increase 100, Discontinuation of manufacture 71, API shortage 57, Shipping delay 24, GMP compliance 20, Inactive ingredient 4, Regulatory delay 3. Note the largest single bucket is "Other" — the field is weaker than it looks.
- **Estimated resolution date? Partially.** No structured field. It appears as free text inside `availability` (one record read: methylprednisolone acetate, "estimated recovery November 2026"). Parseable, but it is NLP on prose, not a column.
- **Historical availability? `initial_posting_date` goes back to 01/01/2012** on still-current records (fentanyl citrate injection, atropine sulfate injection). So **shortage *age* is computable today for every active shortage** — a genuinely useful variable that needs no historical archive.
- **How often does the list change?** Not daily. `update_date` values cluster in the weeks before the 2026-08-07 refresh; data.gov registers the underlying FDA dataset as **weekly (R/P1W)**. Nothing real-time is meaningful here. Do not build a live ticker; it will sit still during your demo.

### Therapeutic concentration (verified counts)

Anesthesia 372 · Pediatric 294 · Psychiatry 275 · Gastroenterology 177 · Neurology 177 · Analgesia/Addiction 164 · Cardiovascular 161 · Endocrinology 156 · Oncology 134 · Anti-Infective 101

And **834 of the current records are injections.** This is the injectable-shortage story, which matters for source selection: injectables are Part B / inpatient-administered, so **Part B (Physician & Other Practitioners, J-codes) is the higher-yield utilization join, not Part D.** Part D is retail outpatient and will miss most of your shortage list. If you only wire up one, wire up Part B.

### Stakes anchors (verified, citable on a slide)

- **Vizient, June 2025:** drug shortages cost US hospitals **~$900M annually in labor**, ~**20 million hours** in 2023, up from ~$360M in 2019 (**+150%**). 132 respondents; average hospital managed **43 concurrent shortages**; pediatric facilities managed ≥25% more. *This is your taxpayer-cost slide, and it is a labor-hours number — which is precisely what a triage tool attacks.*
- **ASPE, 2018–2023 analysis:** 710 distinct shortage events, 258 active ingredients, 1,961 NDC-9 products. **Median duration 2.55 years overall; 4.60 years for injectables; 1.59 oral.** Injectables were 50% of shortages and lasted 2–3× longer.
- **Penn Medicine / JAMA-adjacent, Dec 2024, platinum chemo shortage:** 11,797 patients. Platinum use fell 2.7% overall, peaking at **15.1% in June 2023** — and there was **no mortality difference** at 7.6-month median follow-up.

That last one is the most useful finding in this whole brief, and it is counterintuitive. **The harm from shortages is not primarily death — it is the scramble.** Clinicians substituted, and substitution worked. What it cost was 20 million pharmacist-hours and a switch to more expensive alternatives. That reframes the pitch away from mortality theater and directly onto the track's stated criteria: cost to taxpayers, and the experience of the people doing the work. Use it.

---

## 4. Recommended framing

**Substitution triage, with exposure as the prioritizer. Not coordination. Not forecasting.**

The demo claim:

> *"When a drug goes short, a pharmacist manually works out what to switch to — and whether the thing they'd switch to is also short. That is 20 million hours a year. Here is that answer computed from public data, for every shortage, ranked by how many patients are actually exposed."*

Every element of that is real:

- shortage list — real, FDA
- alternatives — real, RxNorm/RxClass
- alternative-also-short flag — real, computed by self-join
- exposure ranking — real, CMS Part B/D utilization by NPI and state
- shortage age — real, `initial_posting_date`
- cost of the problem — real, Vizient

**Why not forecasting:** 10 resolved records. And even with perfect history, the published median is 2.55 years — so "will this shortage persist?" is a base rate of *yes* and your model adds nothing a constant doesn't. Person A's instincts are right about base rates; here the base rate eats the model. If you want the quantitative flourish without the fiction, use the ASPE published hazard medians (4.60y injectable / 1.59y oral) plus the observed `initial_posting_date` age to state an actuarial expected-remaining-duration. That is honest, defensible, takes an hour, and reads as sophisticated because it *is* — it just isn't a trained model. Say so out loud in the demo; judges respect the distinction.

**Why exposure rather than access/equity as the headline:** equity framing needs population denominators and invites "did you risk-adjust?" questions you can't answer in a weekend. Exposure — raw beneficiary and claim counts per drug per state — is the same join with a defensible claim attached.

**Narrow the demo to one therapeutic class.** Recommend **corticosteroids** (verified: 17-member ATC class, methylprednisolone injection currently short, and published dose-equivalence tables exist in every pharmacology reference) or **anesthesia agents** (largest category at 372, and the operating-room stakes are legible to a non-clinical judge in one sentence). Go deep on one; show the general pipeline behind it.

---

## 5. What must be mocked, and is it defensible

**Under the recommended framing: nothing.** That is the whole argument for the reframe.

Applying the brief's own test — *if you synthesize the data, do you also synthesize the answer?*

| Element                   | Synthetic?                                       | Verdict                                                                                                          |
| ------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Hospital inventory levels | Would be                                         | **Fails the test — so drop it.** You'd invent who has surplus, which *is* the routing answer. Circular. |
| Shortage list             | No — FDA                                        | Clean                                                                                                            |
| Alternatives              | No — RxNorm/RxClass                             | Clean                                                                                                            |
| Alternative-also-short    | No — computed                                   | Clean, and this is the differentiator                                                                            |
| Exposure ranking          | No — CMS                                        | Clean                                                                                                            |
| Dose-equivalence ratios   | **Hand-curated from published references** | Defensible*if cited*                                                                                           |

That last row is the one honest caveat, and you should state it in the demo rather than let a judge find it. **ATC class membership is pharmacologic, not therapeutic equivalence.** H02AB returns 17 glucocorticoids; it does not tell you that 4mg methylprednisolone ≈ 5mg prednisone. Two options:

1. **Cheap and honest:** hand-enter the standard corticosteroid equivalence table for your one demo class, cite the reference, and label the tool's output "candidate alternatives for pharmacist review" — never "recommended substitution."
2. **More rigorous:** layer FDA Orange Book TE codes (AB ratings) for true generic-level substitutability. Free, but it is a different and narrower relation (same molecule, different labeler), so it complements rather than replaces the class approach.

Do option 1 for the demo and mention option 2 as the roadmap. **Do not let the tool render anything that looks like a clinical recommendation** — that is the one thing that will get you correctly torn apart in Q&A, and a single "for pharmacist review" label prevents it.

**One mock is acceptable:** a fictional hospital persona ("you are the pharmacy director at a 400-bed regional hospital in Ohio") as *demo framing*. That is narrative scaffolding, not synthesized evidence — the numbers on screen stay real. Say "let's say you're at a hospital in Ohio," not "our system shows this hospital has 3 days of supply."

---

## 6. Pre-hackathon prep list

Prep is explicitly allowed. Do all of this before the event — it is roughly 4–6 hours and it removes every discovery risk.

**Accounts and keys (do first, they are the only things with any latency):**

1. Register a free openFDA API key at `open.fda.gov/apis/authentication`. Verified limits: **without a key, 1,000 requests/day** — you will blow through that in an afternoon of iteration. With a key, 120,000/day. This is the single highest-value 5-minute task on the list.
2. RxNav/RxClass need **no key** — confirmed. Nothing to do.
3. CMS data APIs need **no key** — confirmed.

**Bulk downloads (do them cold; do not depend on live APIs during the demo):**

4. Snapshot the full shortage list: `api.fda.gov/drug/shortages.json?limit=1000&skip=0` and `&skip=1000`. All 1,651 records, ~2 calls. **Cache to disk.** Re-pull the morning of the event for freshness, but never let the demo hit the network live.
5. CMS Hospital General Information — 5,419 rows via the datastore API. Small.
6. CMS Physician & Other Practitioners by Provider & Service (2024) — **this file is large (multi-GB).** Do not download it at the venue on conference wifi. Either pull it in advance, or pre-filter to only the HCPCS J-codes matching your demo therapeutic class. **Pre-filtering is the right call** — do it at home, ship a 10MB file.
7. Optional: 340B OPAIS daily CE report (Excel/JSON) if you want the cost angle.
8. Optional: Orange Book zip from `open.fda.gov/data/orangebook/`.

**Build ahead of time (this is the part that saves the weekend):**

9. **The rxcui → ATC class → class members → re-join-to-shortages pipeline.** This is the project's spine and it is ~50 lines. Get it working on one drug (rxcui 6902, methylprednisolone) before you arrive. Confirmed working today; it will work then.
10. Resolve the **name-join problem** in advance — this is the hidden time sink. Shortage `generic_name` strings ("Methylprednisolone Acetate Injection") do not match CMS `Gnrc_Name` strings ("Methylprednisolone Acetate"). Bridge them via `rxcui` and `package_ndc` where possible, string-normalize where not. **Budget real time for this; it is the least glamorous and most likely thing to eat a Saturday.**
11. Hand-build the dose-equivalence table for your chosen demo class, with citations.
12. Decide the single demo scenario and write the 90-second narration before you write any UI.

**Explicitly do not:**

- Do not plan on ASHP. Do not wait on an ASHP key.
- Do not build a Wayback-based historical shortage scraper. The ASPE team did it and it is a project unto itself, and §4 explains why the payoff isn't there.
- Do not make hospital bed counts load-bearing (HIFLD availability is uncertain).

---

## 7. Open risks

1. **HIFLD Hospitals availability is unresolved.** It appears in a data-rescue archive, which strongly implies it was pulled from its original open portal. I could not confirm current live access to beds + lat/long. **Mitigation:** CMS Hospital General Information gives you 5,419 hospitals with ZIP; join ZIP → centroid via the free Census ZCTA gazetteer for mapping. You lose bed counts. Design so you don't need them.
2. **Part D vs Part B coverage of the shortage list is unquantified.** I verified both files exist and are queryable, but did not measure what fraction of the 1,651 shortage drugs appear in either. Given 834 are injections, I expect **good Part B coverage and poor Part D coverage** — but this is inference, not measurement. **Check this first at the event; it is a 30-minute check and it determines your exposure layer.** If coverage is thin for your chosen class, switch classes rather than switching projects.
3. **`availability` free-text parsing for resolution dates is unproven at scale.** I read it working on one record. I don't know how consistent the phrasing is across 1,177. Treat any resolution-date feature as a stretch goal.
4. **"Other" is the largest shortage_reason bucket (142).** Any analysis keyed on reason is weaker than the field's existence suggests.
5. **CMS provider files are annual, latest 2024.** Your exposure layer is ~2 years stale against a current shortage list. This is fine and defensible — exposure is structural, not real-time — but a judge may ask. Have the answer ready: *utilization patterns are stable; the shortage list is what moves.*
6. **JHU prior art is stronger than a casual look suggests.** `supplychain.jhu.edu` launched June 2025, free, 60,000 drugs, quarterly, DoD-funded. It covers manufacturing geography, API sourcing concentration, FDA inspections, and 5–6 years of shortage history. It does **not** do substitution or utilization-weighted exposure — confirmed. Your differentiation is real but it is **narrower than the brief assumed**, and you should name JHU in your demo and state precisely what you do that it doesn't. Judges who know the space will know it; being the team that already knows reads as competence rather than getting caught.

---

## Technically impressive, or merely useful?

**Merely useful — and you should choose that deliberately rather than discover it at 3am.**

The strongest honest version of this is a well-executed multi-source join with one genuinely clever computed feature (alternative-also-short) and a clear story. There is no hard algorithm in it. The engineering is REST calls, entity resolution, and a ranked table.

That is a good match for this track and this team. It plays to multi-source fusion and analyst-facing decision surfaces (Person B) and to base-rate reasoning and prioritization logic (Person A). It requires no geospatial or satellite experience, no ML infrastructure, and no frontend heroics — a clean ranked table with one map beats a dashboard.

If the goal weights recruiting outcomes, this is the right shape: it demonstrates judgment about what data can and cannot support, which is the thing that actually distinguishes good analysts and which most hackathon projects conspicuously lack. **The moment in your demo where you say "we dropped the inventory-routing version because that data doesn't exist, so we built the version that's true" is worth more than any feature you could add.** Lead with it.
