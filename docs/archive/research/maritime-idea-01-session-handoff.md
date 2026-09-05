> **Archived 2026-09-05.** Historical planning/handoff document for wake.ai. Superseded by [docs/candidate-pipeline.md](../../candidate-pipeline.md), [docs/status.md](../../status.md) and [docs/data.md](../../data.md). Status claims, branch advice and any schedules in this file are stale and must not be acted on.

# Maritime Idea 01 — Research and Product Handoff

**Prepared:** September 5, 2026
**Purpose:** Preserve the research, corrections, product conclusions, and next-step specification from this session so another model can synthesize the final solution and build plan.

## Bottom line

The original concept—identifying potentially suspicious ship-to-ship activity from paired AIS disappearances—has a real operational problem behind it, but it is neither wholly novel nor a reliable way to *detect* a transfer by itself.

The strongest fast product is a transparent, historical **candidate-triage demonstration**, not a claim to discover previously unseen dark rendezvous. It should show how two vessels' AIS-gap endpoints can be paired, then explicitly test and penalize the dominant alternative explanations: satellite coverage artifacts, clustered fleet behavior, and sequential MMSI use.

Recommended working name: **GapPair: Coverage-Conditioned Dark-Gap Triage**. Avoid using the term “Dark Rendezvous” as the product name because Skylight already uses it for an existing event type.

## Original thesis and necessary corrections

| Original framing | Research conclusion |
| --- | --- |
| “Nobody detects paired AIS absences.” | Incorrect. Skylight has a production *Dark Rendezvous* event; Global Fishing Watch (GFW) supports encounter/gap analysis; an Oxford working paper explicitly uses spatially close, temporally overlapping AIS gaps to identify dark tanker activity. |
| A matched pair is evidence of a dark transfer. | Too strong. It is an **investigative candidate** only. Missing AIS can result from reception gaps, satellite/terrestrial transition, congestion, equipment issues, safety/security decisions, or normal fleet patterns. |
| GFW’s 55,368 events show maritime-wide transfer behavior. | Incorrect scope. The public Welch et al. corpus covers **fishing-vessel AIS disabling on the high seas**, not tankers, reefers, carriers, or all shipping. |
| A simple proximity join will produce the signal. | Incorrect. The historical corpus shows strong non-random co-occurrence, but fleet correlation and local reception conditions are serious confounders. An explicit null model and explanation layer are core product features. |
| This needs a new tracking data system. | Not for a showcase. The public GFW event data are enough to demonstrate endpoint pairing. Production use would require licensed/current data and independent corroboration. |

## Why the problem matters

The relevant problem is real: AIS disablement and opaque transshipment can support IUU fishing, sanctions evasion, fraud, and safety risks. But system value comes from narrowing an investigator’s queue, not from making an unsupported accusation.

- Welch et al. identified **55,368** apparently intentional AIS-disabling events from **5,269 MMSIs** and **101 flags** in 2017–2019, using 3.7 billion AIS messages. They estimated **100,800–206,707 vessel-days** of obscured fishing activity (roughly 2.42–4.96 million hours), or **3.2–6.0%** of fishing activity in their study area.
- The paper reports that more than **40%** of fishing vessels in the studied high-seas waters had at least one disabling event. This is an event/behavior metric, not proof of illegal activity or transfer volume.
- The scale of IUU fishing is material but uncertain. The UN World Ocean Assessment cites roughly **8–14 million tonnes** of unreported catch traded illicitly per year, with **$9–17 billion** estimated gross illicit revenue and broader economic impacts of **$26–50 billion**. Do not attribute these figures specifically to dark rendezvous.
- Existing enforcement already uses data fusion. The U.S. GAO reports that the Coast Guard and NOAA analyze location data, including cessations of positional broadcasts, to target potential illegal transshipment and patrols. A 2025 Coast Guard Project Minerva description gives the operational pattern: AIS silence plus satellite imagery becomes an analyst alert that can guide a cutter.

## What the historical paired-gap exercise found

These figures were calculated from the public GFW/Welch event corpus during the session. They are useful for a demo design, but should be re-run reproducibly and described as an internal historical analysis rather than an independently published statistic.

| Pairing rule | Observed pairs | Approx. regional null A | Lift vs. null A | Approx. regional null C | Lift vs. null C | Vessels | Top-five vessel share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Start endpoints within 50 km / 24 h | 125,878 | 14,904 | 8.4x | 47,915 | 2.6x | 2,154 | 6% |
| Start endpoints within 5 km / 1 h | 1,240 | 25 | 50x | 132 | 9.4x | 435 | 15% |
| Both endpoints within 25 km / 3 h | 5,659 | 74 | 76x | 389 | 14.5x | 616 | 12% |
| Both endpoints within 10 km / 1 h | 437 | 1.9 | 230x | 12.4 | 35.2x | 216 | 28% |
| Both endpoints within 5 km / 1 h | 105 | 0.4 | 263x | 3.5 | 30x | 77 | 40% |

Interpretation:

- Strict endpoint co-occurrence is far above the tested random baselines. That makes it worth investigating, but does **not** establish ship-to-ship transfer.
- The strict 10 km / 1 hour rule produces about **437 candidates over three years** (about 146/year), which is workable for a review-queue demo.
- Only **27** of those strict candidates were cross-flag (about nine/year; 6.18% of the strict candidate set). Cross-flag is a useful risk/suspicion feature, not an outcome label.
- **94%** of candidates shared a flag, and about **58%** involved sequential MMSIs. This strongly suggests that coordinated fleets, duplicated/rotating identities, or local operating patterns can explain many candidates.
- Local density is a major confounder: the median cross-flag candidate had **12 other vessels** going dark within 200 km and +/- 1 hour. Only two of 27 were locally quiet.
- One illustrative, non-adjudicated candidate was CHN MMSI `412331147` and TWN MMSI `416004105` on 2017-07-01 near 42.7°N, 162°E: 6.6 km apart at disappearance, roughly 482 nautical miles offshore, with off-times five seconds apart, return-times 43 seconds apart, and a 41.8-hour gap. It was one of only three vessels dark within 200 km +/- one hour. Present it as a candidate story, never a confirmed transfer.

### Calibration warning

The WCPFC’s purse-seine transshipment evaluation is the right cautionary precedent: **78% of 77 AIS-only potential transshipment events remained unsubstantiated** after further triangulation. Of 34 events with observer coverage, 25 were not transshipments (examples included provisioning, salt/spares, and crew transfer). This supports a candidate-and-evidence workflow, not a binary “caught” product.

## Current practice and competitive landscape

### Global Fishing Watch

GFW already offers the surrounding analytical ecosystem:

- Its events API includes `ENCOUNTER`, `FISHING`, `LOITERING`, `GAP_START`, and `PORT_VISIT` event types.
- Its published transshipment method models a fisheries vessel and carrier within 500 m for at least two hours, moving under two knots and away from anchorages. It also flags potentially suspicious carrier loitering. That is more than a broadcast-gap-only workflow.
- GFW’s documentation is unusually clear that events are algorithmic estimates, not ground truth. AIS gaps can reflect satellite geometry, terrestrial/satellite handoff, network congestion, and other coverage artifacts.
- A 2026 GFW IUU-risk dataset release covers 2017–2025 and includes disabling and gap fields, but it is described as proof-of-concept data and does not publish a total for paired dark-event transfers.

For a public showcase, the downloadable Welch data are appropriate. For a live or commercial product, validate API terms and data availability. GFW’s standard API terms describe authenticated, non-commercial access under CC BY-NC 4.0, with rate limits; do not assume those data may be embedded in a commercial product.

### Skylight

Skylight is a mature maritime monitoring platform for agencies and organizations working to reduce IUU fishing and related maritime risk. It is not simply an AIS map.

Its documented capabilities include:

- Near-real-time commercial AIS ingestion (ORBCOMM), vessel/event histories, and APIs using GraphQL.
- A broad fusion stack: AIS, Sentinel-1 SAR, Sentinel-2/Landsat optical imagery, VIIRS nighttime-light data, commercial high-resolution imagery/radar/RF, and GFW metadata.
- Standard rendezvous events: two AIS-broadcasting vessels in close proximity for a sustained period.
- **Dark Rendezvous** events: a machine-learned pattern in which one AIS-broadcasting vessel behaves as if interacting with a nearby partner that is absent from AIS. Skylight documents at least 15–30 minutes of qualifying behavior depending on its documentation version, notes that events may last hours, and explicitly warns that it cannot guarantee a vessel was present or identify the reason for behavior.
- Evidence workflows: imagery/RF/other source overlays that help an analyst corroborate or reject an event.

Important access constraints:

- Skylight access is provided to qualifying public-interest organizations/agencies under an account and EULA; its public map is a limited delayed demo and does not expose AIS tracks, dark-rendezvous events, alerts, downloads, or 2017–2019 history.
- The platform documentation describes APIs but does not publish Skylight’s detection-model source code or a reusable full data feed. No Skylight account, token, or private source code was accessed in this session.

### What Skylight means for this idea

Skylight makes a direct “we uniquely detect dark rendezvous” thesis obsolete. It does **not** make a showcase obsolete if the showcase has a different purpose:

1. Make the paired-gap method fully transparent and inspectable.
2. Show how a candidate’s risk score changes under coverage, fleet, identity, and local-density challenges.
3. Use a reproducible public historical corpus, where Skylight’s public map cannot provide an equivalent 2017–2019 case-study workflow.
4. Position the tool as an upstream triage and explanation layer that could later send high-quality candidates into Skylight, GFW, imagery, or enforcement workflows.

If valid Skylight credentials are later provided, its GraphQL API and corroborating detections could be integrated as an evidence panel. Do not make the initial demo depend on that access.

## Oxford “Dark Shipping” paper: usable ideas and limits

Paper: *Charting the Uncharted: The (Un)Intended Consequences of Oil Sanctions and Dark Shipping*, Fernández-Villaverde, Li, Xu, and Zanetti (Oxford working/discussion paper; not treated here as peer-reviewed operational guidance).

The paper is highly relevant methodological prior art. Its tanker-focused method identifies likely dark ship-to-ship behavior from ships that are geographically close and have overlapping AIS data gaps. It estimates a likely meeting area using last known positions and headings before disappearance.

Its multi-level procedure can be summarized as:

1. Identify sanctioned-port trip context.
2. Identify unusual AIS gaps and spatial/temporal overlap between vessel gaps.
3. Add kinematic and route behavior features, such as average speed, speed variability, and detours.
4. Combine event features with vessel/operator/flag/age/idling characteristics and cluster/rank vessels.

The paper uses a much richer proprietary/raw tanker AIS panel: roughly 330 million records, tanker identifiers, timestamps, positions, speed, heading, and draft. It reports roughly 558 dark tankers per year on average during 2017–2023, but those are the paper’s model-derived estimates and should not be presented as independently verified facts.

### Reuse recommendation

Reuse the **methodological pattern**, not a claim of novelty or an attempted direct port:

- Reuse: temporal overlap, endpoint proximity, prior heading where available, duration similarity, route/kinematic features, and a staged score.
- Do not reuse in the initial GFW demo: its tanker-specific sanctions labels, draft-based analyses, precise pre-gap trajectory-intersection calculation, or unsupervised clustering output. The public GFW gap CSV does not expose the raw AIS tracks, headings, drafts, or cargo context required to reproduce those parts honestly.
- Treat the initial product as an adaptation of published methodology to public fishing-vessel disabling-event records, with a much stronger false-positive explanation UI.

## Recommended showcase product

### Product claim

> GapPair converts public AIS-disabling events into an auditable, ranked investigation queue. It highlights synchronized paired gaps while showing whether the pattern survives coverage, fleet, identity, and local-density challenges.

Do **not** say “we detect illegal transshipment,” “we prove a dark rendezvous,” or “we are the first to find this behavior.”

### User and decision

Primary user: maritime analyst, NGO researcher, or enforcement intelligence team.

Decision supported: “Which 10 candidates deserve corroborating imagery, registry checks, port-call records, or human review first?”

### MVP screens

1. **Candidate queue** — Ranked cards/table with map snippets, score, flags, gap duration, cross-flag/same-flag, and confidence category.
2. **Candidate investigation view** — Start/end endpoint map, synchronized timeline, vessel/event metadata, local contemporaneous dark-event density, and a readable evidence ledger.
3. **Challenge panel** — Explicitly shows which explanation weakens the candidate: coverage artifact, fleet correlation, sequential MMSI, crowded local blackout, or insufficient information.
4. **Methodology drawer** — Pairing thresholds, source provenance, caveats, and no-accusation language. This is crucial for credibility.

### Candidate labels

- `investigate`: a rare, synchronized, geographically tight paired-gap candidate with limited obvious confounds.
- `coordinated-fleet-pattern`: pair is structurally interesting but likely driven by shared flag, repeated vessel co-occurrence, or sequential identity behavior.
- `likely-coverage-or-cluster-artifact`: local dark-event density or reception conditions dominate the pattern.
- `insufficient-evidence`: endpoint or metadata information cannot support ranking.

### Minimal data model

```text
GapEvent
  mmsi, flag, gear_type
  off_time, off_lat, off_lon
  on_time, on_lat, on_lon
  duration_hours, distance_from_shore

CandidatePair
  event_a_id, event_b_id
  off_time_delta, on_time_delta
  off_distance_km, on_distance_km
  overlapping_gap_hours, duration_ratio
  same_flag, sequential_mmsi, cross_flag
  local_dark_count, regional_null_probability
  score, label, explanation[]
```

### Pairing and scoring logic

Start with a strict, readable candidate rule:

1. Use published GFW intentional-looking gap events (already filtered by the original research for long offshore gaps and adequate prior reception).
2. Find two events with disappearance times within one hour and start endpoints within 10 km.
3. Require overlapping AIS-gap intervals.
4. Require reappearance times within one hour and end endpoints within 10 km.
5. Rank, do not classify as fact.

Suggested positive features:

- tighter start/end proximity;
- tighter off/on timing synchrony;
- meaningful overlap and similar duration;
- far-from-shore location;
- low count of other nearby contemporaneous dark events;
- cross-flag or unusual repeat pattern, carefully described as an analyst priority feature.

Suggested penalties/explanations:

- same-flag fleet clustering;
- sequential/nearby MMSI patterns;
- high local dark-event density;
- known poor reception or region/time patterns;
- repeated co-occurrence that looks like a normal fleet behavior;
- missing endpoint/metadata fields.

Show score components, not a black-box probability. A “local permutation / shuffled-time null” result is more defensible than a generic confidence percentage.

## Build sequence for a fast demonstration

No application has been built in this session. The following is a recommended build sequence for another model/team.

1. **Data and reproducibility (2–4 hours):** download the public GFW final gap-event CSV; write a deterministic pairing script; save derived candidates and a data dictionary.
2. **Confounder features (3–4 hours):** calculate start/end distance, off/on deltas, overlap, same/cross flag, sequential MMSI heuristic, concurrent-local-gap count, and one local shuffled-time null.
3. **Ranker and explanations (2–3 hours):** implement a transparent weighted score with human-readable reasons and labels. Do not train a model without labels.
4. **Front end (4–6 hours):** build the queue, candidate map/timeline, and challenge panel. Seed it with a few varied examples: one compelling sparse pair, one fleet cluster, one high-density/reception-artifact-like pair.
5. **Credibility pass (1–2 hours):** put the caveats and all source links in the product; ensure “candidate” appears wherever a non-expert might infer guilt.
6. **Optional later integration:** if a legitimate Skylight account/API key is obtained, add Skylight evidence or event links; if not, use a static integration placeholder rather than fabricating a connection.

## What must be validated before any stronger claim

The central unknown is not whether pairs can be found—it is how often they correspond to a real interaction versus a confounder. A real pilot needs independent labels/evidence.

Measure:

- **Precision at K:** among the top 10/20/50 candidates, what fraction obtains independent corroboration (imagery, observer data, port/declaration data, registry intelligence, or credible analyst confirmation)?
- **Lift:** corroboration rate of GapPair’s top-ranked candidates versus randomly selected gap events, simple encounter candidates, and local/fleet-matched baselines.
- **Queue usefulness:** analyst review time per candidate and the number of actionable, corroborated leads per week.
- **False-positive structure:** fraction rejected due to coverage/density, normal fleet behavior, or identity issues.
- **Generalization:** performance separated by region, gear type, flag, time period, and data source.

A reasonable early target would be a measurable lift over baseline and some independently corroborated cases—not an arbitrary universal accuracy claim. Until labels exist, call the output a prioritization score rather than a probability of wrongdoing.

## Important source links

### Primary research and public data

- Welch et al., [“Hot spots of unseen fishing vessels”](https://pmc.ncbi.nlm.nih.gov/articles/PMC9629714/) (Science Advances, 2022).
- GFW’s public [AIS disabling high-seas repository and data](https://github.com/GlobalFishingWatch/AIS-disabling-high-seas/tree/main/data).
- GFW [data caveats](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/data-caveats) and [events API documentation](https://globalfishingwatch.org/our-apis/documentation/docs/v3/events/get-all-events).
- GFW [transshipment dataset and methodology](https://globalfishingwatch.org/datasets-and-code-transshipment/).
- GFW [IUU Fishing Risk Insights dataset release](https://globalfishingwatch.org/platform-update/iuu-fishing-risk-insights-dataset-release/).
- Fernández-Villaverde, Li, Xu, and Zanetti, [“Charting the Uncharted: The (Un)Intended Consequences of Oil Sanctions and Dark Shipping”](https://users.ox.ac.uk/~wadh4073/research_files/Dark_Shipping.pdf).

### Operational and policy context

- U.S. GAO, [Maritime Security: Coast Guard Needs to Improve Tracking of Efforts to Address IUU Fishing](https://www.gao.gov/products/gao-22-104234).
- U.S. Coast Guard, [Project Minerva: transforming data into action at sea](https://www.mycg.uscg.mil/News/Article/4258464/how-the-coast-guard-is-transforming-data-into-action-at-sea/).
- WCPFC, [Tracking Purse Seine Transshipment](https://meetings.wcpfc.int/file/6935/download) (false-positive/corroboration caution).
- FAO, [Voluntary Guidelines for Transshipment](https://www.fao.org/iuu-fishing/resources/detail/en/c/1638082/).
- UN World Ocean Assessment, [assessment document](https://www.un.org/regularprocess/sites/www.un.org.regularprocess/files/woa_iii_tc_draft4_to_web_rev2.pdf) (broad IUU context).

### Skylight

- Skylight [platform data sources](https://support.skylight.global/en_US/platform-overview/data-sources).
- Skylight [Dark Rendezvous documentation](https://skylight.helpjuice.com/en_US/vessel-behavior-events/dark-rendezvous).
- Skylight [events documentation](https://skylight.helpjuice.com/en_US/events/what-are-events).
- Skylight [API overview](https://support.skylight.global/en_US/an-overview-of-the-skylight-api) and [access requirements](https://support.skylight.global/en_US/user-basics/access-to-skylight).
- Skylight [public-map limitations](https://support.skylight.global/platform-functions/skylight-public).

### Legal/data-access caveat

- GFW [API license and rate-limit terms](https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits).

## Existing local artifacts

- [Canonical cited research report](/Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026/report-source.md)
- [Five-page due-diligence PDF](/Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026/output/pdf/maritime-idea-01-due-diligence.pdf)
- [Original idea brief](/Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026/ideas/idea-01-maritime-dark-rendezvous.md)
- [Local revised feasibility notes](/Users/Tanner/Desktop/DN_Hacks_2026/DNHacks_2026/ideas/martime.md)

## Recommended prompt for the next model

> Using this handoff and the cited local research files, design and implement a polished hackathon demonstration named “GapPair: Coverage-Conditioned Dark-Gap Triage.” Use the public Global Fishing Watch AIS-disabling event dataset only. Build a reproducible candidate-pair pipeline for gaps whose start and end events are within 10 km and one hour, then rank candidates transparently with timing/proximity, local-density, same-flag, cross-flag, and sequential-MMSI features. Build a queue, investigation map/timeline, and challenge/explanation panel. Never assert that a candidate is a confirmed transfer or illegal activity. Cite GFW, Skylight, the Oxford paper, and WCPFC caveats in the UI and README. Do not depend on Skylight API access; make any such integration optional.
