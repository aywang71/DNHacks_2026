# DNHacks 2026 — Judging Mechanics and Positioning

**Section 1 is fact from dnhacks.org. Sections 2–4 are inference** drawn from the guest list, sponsor businesses, and category wording. Treat them as a strong prior, not as rules — and override them with any challenge prompt or rubric released on-site.

---

## 1. What the site actually says about judging

- *"Projects are judged across our challenge categories by industry and public-sector judges."*
- *"Each category and special award will have its own set of judges. Plan to be judged by three groups of judges during project demos."*
- *"Only winners and runners up from the category prizes will be eligible to win the overall prize and runner up."*
- *"Special awards can be granted to any project."*
- *"Yes, you can use AI to help build your project, but judges will heavily weight the technical depth that you bring to your project."*
- Health & Public Service adds a second axis: *"evaluated not just on technical quality, but on their potential to reduce costs for taxpayers and improve the experience of interacting with government."*
- Open Category states: *"judged on the strength of their idea, the quality of their execution, and the real-world impact their project could have at scale."*
- Prizes include *"grant conditional on continued work"* and entry to *"a curated talent cohort working on real-world problems throughout the year."*

**No numeric rubric is published.** The recurring words across all of it are: technical depth, execution, real-world impact at scale, cost reduction.

### The judging timeline
| Time (Sunday) | Event |
|---|---|
| 12:00 p.m. | Submission closes |
| 1:00 p.m. | Project Showcase — **three separate judge groups** come to us |
| 4:00 p.m. | Finalists announced → **live demo** on stage |
| 4:30 p.m. | Winners |

Two consequences worth designing around:
1. **The pitch gets delivered at least three times to different audiences**, likely with different domain expertise each time. It needs to be modular — a 60-second core that works for anyone, with track-specific depth we can swap in depending on who's standing there.
2. **The demo has to run twice, three hours apart.** Anything dependent on live API calls, venue wifi, or a warm cache is a risk at 4:00 p.m. that it wasn't at 1:00. Pre-compute and cache; keep at most one live call, behind a button, with a recorded fallback. (The existing `../ideas/ag_orches.md` brief already reached this conclusion independently: *"Treat the demo as cache-first regardless."*)

---

## 2. What this specific audience rewards

The judge pool is dominated by people who **buy, deploy, or accredit** technology inside government and industry — not by researchers. Recurring themes across their day jobs:

**They will reward:**
- **A named user and a named buyer.** Nearly every attending operator lives on the procurement side. "Who is the actual user, and what do they do today instead?" is the most likely first question in the room.
- **Deployability.** Second Front's entire business is the gap between working software and *authorized* software. Knowing what classification our data is, and where an ATO would be needed, is cheap and lands hard.
- **Degraded-environment thinking.** Forterra (contested EM), Guardian RF (passive sensing), Second Front Frontier (disconnected edge), Navy CTO (GPS-denied). If our system assumes clean connectivity, clean GPS, or cooperative data, expect that assumption to be attacked — and expect the attack to be correct.
- **Measured claims over demos.** Fanelli's stated posture is *measurable mission impact over technology demonstrations*. A number with a stated baseline beats a slick UI.
- **Honest failure modes.** A stated false-positive budget, a known-limitations slide, an adversarial "how would this be defeated" answer. Tim Booher (ex-DARPA, ex-Air Force Red Team) is in the room; so is Model Behavior from OpenAI.
- **Continuation.** The prize structure funds work that keeps going. A credible "what the next six months looks like" is directly rewarded.

**They will discount:**
- Thin LLM wrappers. Stated outright in the FAQ, and there is an applied AI engineer plus an ML lead in the room.
- Unquantified impact claims, especially in Health & Public Service where cost reduction is an explicit criterion.
- Anything that would obviously lose to an existing commercial product in the first 30 seconds of Q&A. Several judges *are* the existing commercial product.

---

## 3. Framing

The host organization's mission is explicitly about redirecting technical talent toward American industrial, military, and technological capability. The cheapest available points come from framing work in those terms: national capability, sovereignty, taxpayer cost, institutional capacity, reducing dependence on adversary supply chains.

This is a framing choice, not a content choice. The same project can be pitched as "a neat ML pipeline" or as "closing a gap in how the US sees a specific threat," and the second costs nothing extra. Avoid pitches whose central argument is a critique of US institutions or of a sponsor's business.

---

## 4. Mapping our existing ideas to this room

Cross-referencing `../ideas/`:

**`idea-01-maritime-dark-rendezvous.md`** — Defense, or Open. Strongest fit with the room of the four. Direct hooks: Justin Fanelli (Navy CTO; Defense track explicitly names "naval warfare systems"), Chase Ried (Aslan — literally maps smuggling and illicit networks; will both grasp it fastest and probe it hardest), Matt Cronin (a16z; sanctions/tech-transfer/China), Mario Mancuso (export control, sanctions). Charles Swannack (Forterra EMSO) is the one to prepare for on the "what if the signal environment is contested" question. The brief's existing chance-baseline work is exactly the kind of measured claim this audience rewards.

**`idea-02-federal-procurement.md` / `procurement.md`** — Health & Public Service. Hooks: Andrew McCarthy (White House anti-fraud), Nick Lanham (Advana; federal data plumbing), Jake Fischer (Army financial management/audit), Joshua Levine (FAI; published thesis on making government data AI-ready), and **Statecraft**, a partner already selling into this exact space. Note the competitive risk: Statecraft's existence means "AI for federal back-office" is a live commercial category — we need an angle they don't already cover.

**`idea-03-agricultural-orchestration.md` / `ag_orches.md`** — Energy & Industrialization. Fits the track's named examples, but the site *itself* names "satellite imagery models that forecast crop yields" as an example, so expect company. The existing brief's own verdict (BUILD REDUCED; narrow to anomaly triage with a stated false-positive budget) is the right instinct for this audience — the narrowed, measured version is what gets rewarded here, and the "holistic operational picture" version is what loses to FieldView in Q&A.

**`idea-04-hospital-drug-shortages.md` / `hospital.md`** — Health & Public Service. Hook: Jonathan Merril (Oncovera). The track's taxpayer-cost axis needs an explicit dollar figure attached.

**Track-selection note:** we must place in a category to reach the overall prize, so choose the track where we're strongest *relative to the field*, not the most literal fit. Energy & Industrialization skews hardware — its sponsors are all physical-manufacturing companies — which may make it a harder room for a software entry, or a thinner field. Worth reading the room on Saturday.

**Two free extra shots:** Best in Design and Best Use of AI are event-wide and stack on a category placement. Best Use of AI likely has OpenAI staff on it, including Model Behavior — meaning evals, measured failure modes, calibration, and agent trust read better there than raw API volume. Visible, competent use of **Codex** is aligned with the sponsor at no cost. Participant's Choice is peer-voted, so the pitch also needs to be legible and memorable to other students, not only to domain experts.

---

## 5. Open questions to resolve on-site

- Are there **partner-defined challenge prompts**? The Defense description promises them; check at the opening before locking scope.
- Is there a **published rubric or scoring sheet** given to teams at check-in?
- What is the **submission format** (repo? deck? video? Devpost-equivalent?) — not stated anywhere on the site.
- **How long is each showcase pitch**, and is it booth-style or timed?
- **What is Torus Systems?** Unidentified partner — see `04-companies.md`.
- Which judges are assigned to which category?
