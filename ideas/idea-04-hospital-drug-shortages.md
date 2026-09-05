# Idea 04 — Hospital Drug Shortage Substitution Triage

**Verdict: TECHNICALLY VIABLE, but deprioritized. Lowest ceiling of the four.**
**Track it would target:** Health & Public Service.

---

## The idea

When a drug goes into shortage, a pharmacist manually works out what to substitute — and whether the thing they would switch to is *also* short. Automate that, ranked by how many patients are actually exposed.

The original framing was hospital-to-hospital coordination: who has surplus, who has none, route between them. **That version is dead** — see below. What survived is substitution triage, and it survived in better shape than the original idea.

## The premise

Drug shortages cost US hospitals roughly **$900 million a year in labor** — about 20 million pharmacist-hours, up 150% from 2019. The average hospital manages 43 concurrent shortages. That is the taxpayer-cost argument, and it is a labor-hours number, which is exactly what a triage tool attacks.

The most useful thing we learned, and the counterintuitive one: in a major chemotherapy shortage, platinum drug use fell 15% at peak and there was **no mortality difference** at follow-up. Clinicians substituted, and substitution worked. **The harm from shortages is not primarily death — it is the scramble.** That reframes the pitch away from mortality theater and directly onto the track's stated criteria: cost to taxpayers, and the experience of the people doing the work.

## What we verified

**The coordination premise is dead.** FDA shortage data has no facility field, no state field, no region field, no quantity field, and no inventory field. There is no geography in it of any kind. There is no "which hospital has surplus" because there is no hospital in the data at all. Building it would mean inventing every input and therefore every output — you would synthesize the data *and* synthesize the answer.

**But the substitution chain is real and verified end to end.** The FDA shortage record carries an RxNorm concept identifier natively — no fuzzy name matching required. From there: identifier → drug class → all class members → **re-join those members against the shortage list**. That last step is the product: *which of your alternatives are also short*. Confirmed working by live API call, entirely free, no key required.

**Forecasting is dead too, and this contradicted our assumption.** The API is a live snapshot, not a historical panel — only 10 resolved records exist. You cannot fit a survival model on 10 observations, and training only on still-active shortages is textbook survivorship bias. Published median shortage duration is 2.55 years overall, so "will this persist?" has a base rate of *yes* and a model adds nothing.

**Exposure ranking is real.** CMS publishes provider-level drug utilization with city and state, 2013–2024, free. Since 834 of current shortage records are injectables, the Part B physician-administered file is the right join. That gives a genuine exposure map with nothing invented.

**Prior art is closer than expected.** A Johns Hopkins tool launched in 2025 covers 60,000 drugs, manufacturing geography, API sourcing concentration, and shortage history. It does **not** do substitution or utilization-weighted exposure — our differentiation is real, but narrower than assumed, and we would need to name it in the demo rather than get caught by it.

## What must be mocked

**Nothing.** That is the strongest single argument for this idea. Shortage list is FDA. Alternatives are RxNorm. Alternative-also-short is computed. Exposure is CMS. Shortage age is a real field going back to 2012.

One honest caveat: drug class membership is *pharmacologic*, not therapeutic equivalence — the class tells you 17 drugs are related, not that 4mg of one equals 5mg of another. Fix: hand-enter the standard equivalence table for one demo class, cite the reference, and label output "candidate alternatives for pharmacist review," never "recommended substitution." That single label prevents the one line of questioning that could correctly take the project apart.

## Why we are deprioritizing it

**The technical ceiling is low.** The honest version is a well-executed multi-source join with one clever computed feature and a clear story. There is no hard algorithm in it — the engineering is REST calls, entity resolution, and a ranked table. The investigation's own summary was "merely useful, not technically impressive," and recommended choosing that deliberately rather than discovering it at 3am.

**The name-join problem is a real time sink.** FDA generic-name strings do not match CMS generic-name strings, and bridging them is the least glamorous and most likely component to eat a Saturday.

**Interest matters over a weekend.** Neither of us is drawn to healthcare, and a weekend is short enough that motivation is a real input rather than a soft consideration.

## What it has going for it

Lowest risk of the four by a wide margin. Nothing mocked, free data, no auth, no geospatial or ML infrastructure required, and a clean stakes number. The Health & Public Service track has the lowest technical bar and is explicitly a recruiting channel — the track description notes partners actively looking to hire.

**The strongest moment available in this demo:** *"We dropped the inventory-routing version because that data doesn't exist, so we built the version that's true."* Demonstrating judgment about what data can and cannot support is the thing most hackathon projects conspicuously lack.

## What would change the verdict

If the team weighted recruiting outcomes over winning, this moves up sharply. It is the safest project of the four and the one most likely to produce a working, honest, legible demo with no unresolved risk.

We are optimizing for winning and for building something we find interesting, so it drops.
