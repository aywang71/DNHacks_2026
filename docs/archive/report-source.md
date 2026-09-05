> **Archived 2026-09-05.** Historical planning/handoff document for wake.ai. Superseded by [docs/candidate-pipeline.md](../candidate-pipeline.md), [docs/status.md](../status.md) and [docs/data.md](../data.md). Status claims, branch advice and any schedules in this file are stale and must not be acted on.

# Maritime Idea 01: Dark Rendezvous Due Diligence

**Decision:** Build with a material pivot for a research/demo product. Do not proceed with the original market, novelty, or detection claims.

**As of:** 5 September 2026  
**Audience:** founding team / hackathon judges  
**Question:** Is the proposed pairing of two vessels' AIS-dark intervals a credible, differentiated, operationally useful way to identify IUU-fishing or transshipment candidates?

## Executive answer

The method is technically plausible as a **retrospective, uncertainty-labelled candidate-ranking signal**. The public Welch / Global Fishing Watch (GFW) corpus is well suited to demonstrating that two known fishing vessels had anomalously synchronized, spatially reconcilable gaps. Its documented start and end timestamps and locations permit a reproducible downstream pairing experiment [S1, S2].

It is **not** a transfer detector. GFW itself describes AIS-derived activity events as estimates that can be missing or wrong; it requires contextual review for gap, encounter, and loitering events [S3]. In a regulated Western-Central Pacific purse-seine study, 78% of visible AIS potential transshipments remained unsubstantiated after triangulation; most observer-covered cases were non-transshipment activity [S10]. A pair that is dark for the alleged event has still less direct evidence.

It is **not novel as “paired dark-gap detection.”** An Oxford working paper explicitly scores potential dark ship-to-ship transfers using two vessels that are geographically close with overlapping AIS gaps, using pre/post-gap position, heading and time data [S6]. Skylight already deploys an alert named “Dark Rendezvous” for a visible vessel whose trajectory suggests a meeting with a non-AIS vessel [S7]. The public material does not show that either product uses the proposed exact two-endpoint pairing and local-density null, but it rules out claims that nobody detects dark rendezvous or dark transfers.

The viable product is therefore narrower: **Coverage-Conditioned Paired AIS-Gap Triage** - an auditable research/analyst layer that ranks historical fishing-vessel gap pairs, shows the null model and competing explanations, and packages corroboration requests. It should be sold as a complement to existing MDA tooling, not as a replacement.

## Viability scorecard

| Dimension | Finding | Decision |
|---|---|---|
| Historical demo | Public, endpoint-defined 2017-19 corpus supports a reproducible pair-ranking demo. | Green |
| Intentional-gap inference | The source classifier controls important reception effects, but correlated local reception/fleet behavior remains a pair-level confound. | Amber |
| “Was there a transfer?” | No public two-dark-vessel ground truth found; visible encounter data also has high ambiguity. | Red |
| Differentiation | Exact conditional-null / two-endpoint implementation may differ, but the category and core method are prior art. | Amber |
| Operational use | Government uses AIS cessation and transshipment-like movement as leads, then fuses sensors and records. | Green |
| Real-time interdiction | Both vessels must resume broadcasting; alert is retrospective. Real-time action requires one-ended cues plus imagery/RF/VMS. | Red |
| Commercial data path | GFW API requires authentication and its ordinary terms are non-commercial; GAP data is marked prototype. | Red |

## What is currently in practice

### Analysts already use transmission loss and transshipment patterns

GAO reports that U.S. Coast Guard and NOAA analyze vessel location data for patterns that indicate illegal transshipping and for ceasing positional transmissions. The resulting suspect lists guide patrol targeting; this is a lead-generation workflow, not automatic enforcement [S8]. In 2025, the Coast Guard described Project Minerva's intended operational pattern: AIS loss plus satellite imagery triggers an analytics alert, which is reviewed and sent to a cutter's C2 system [S9].

The same pattern appears in commercial and civil tools. GFW's current Events API exposes GAP, ENCOUNTER, and LOITERING event types [S4]. Its public transshipment approach detects visible fishing-carrier encounters and treats carrier loitering as a possible transfer where the other vessel is not visible [S5]. Skylight's named Dark Rendezvous product warns that it is only an indication and that ground truth is limited; it reports average alert latency of four hours under its one-visible-vessel approach [S7]. Windward publicly markets fused AIS, SAR and RF context for dark activity and suspicious STS transfers [S13]. An Associated Press report also documents Canada's sharing a satellite-based “Dark Vessel Detection System” with the Philippines, illustrating that dark-vessel detection is an active government capability rather than a missing category [S14].

### AIS silence is neither universal illegality nor an unambiguous sensor event

AIS is principally a collision-avoidance system. U.S. requirements call for continuous use on covered vessels, but permit shutdown where continued operation compromises safety or security, with a log/reporting expectation [S12]. AIS carriage and VMS rules vary by vessel size, flag, fishery and jurisdiction. In particular, the project must not assume all fishing vessels are subject to the same AIS duty.

GFW identifies intentional-looking gaps with stringent filters: at least 12 hours; start more than 50 nautical miles from shore; satellite reception quality above 10 positions/day; and at least 14 satellite positions in the prior 12 hours. It still identifies satellite periodicity, terrestrial/satellite handoff, traffic interference, and coverage variation as causes of gaps [S3]. A nearby pair of gaps can therefore be caused by the same coverage artifact or coordinated fleet behavior; a broad timestamp shuffle does not eliminate that risk.

## Evidence assessment

### Data and reproducibility

The 2022 Welch et al. work is a sound starting point, not complete validation. It published 55,368 suspected disabling events from 2017-19 and documented event-level classifier performance. The accompanying GFW repository provides the final event data and endpoint fields, but says raw AIS inputs are licensing-restricted; the reproducible claim must be limited to the downstream pair analysis [S1, S2]. The data has only fishing-gear classes (trawler, drifting longline, squid jigger, tuna purse seine, other), not carrier/reefer/tanker labels. It can demonstrate paired **fishing-vessel gaps**, not a fishing-to-reefer transfer.

Current API availability does not solve this automatically. GFW documents GAP events and intentionally-disabling filters, but requires a registered token. Its standard API terms are CC BY-NC 4.0/non-commercial and reserve the right to modify or withdraw service. The GFW documentation also labels GAP data as prototype/QA and says reception-quality estimates currently rely on Welch's 2017-19 period while later monthly coverage estimates are being automated [S3, S4, S11]. A commercial product needs a paid/rightful data agreement or a different licensed feed.

### Prior art and market position

The original pitch's clean prior-art gap does not survive diligence. The Oxford method is the closest published match: it considers vessels geographically close with overlapping gaps and uses pre/post-gap movements to infer possible dark STS transfers [S6]. It is tanker/sanctions focused, is a working paper rather than a peer-reviewed fisheries study, and is not proof of an identical implementation. It nonetheless makes “nobody publishes paired dark-gap detection” false.

Likewise, “everybody else's tool requires both vessels to broadcast” is false. GFW treats single-carrier loitering as a potential dark-partner event [S5], and Skylight explicitly has a Dark Rendezvous model for one AIS-visible vessel [S7]. The defensible claim is only that this project is testing a transparent, fisheries-specific **two-known-vessel gap-pair score** with an explicitly displayed conditional null and evidence ledger. No exhaustive patent or closed-government-tool search was conducted, so even that is a positioning hypothesis, not an exclusivity claim.

### Operational fit

There is a genuine problem and a credible user workflow. FAO's 2023 voluntary transshipment guidance says monitoring and control have been inadequate, creating loopholes for IUU catch [S15]. NOAA's seafood-import program requires records including transshipment declarations and bills of lading for covered products, and U.S. agencies already use risk targeting [S16]. This makes the best potential users RFMO/flag-state analysts with VMS access, NGO/investigative teams, and port-state/traceability risk teams.

However, a public AIS score cannot by itself authorize a boarding, sanction, or illegal-transfer finding. The governing workflow is: **candidate -> analyst review -> sensor/record corroboration -> lawful referral or inspection**. Evidence should include VMS where authorized, SAR/optical/RF observations, observer coverage, e-logbooks, transshipment notices, port declarations, ownership/authorization records, and boarding evidence [S8, S9, S10].

## Required pivot

### Product language

Use: “Coverage-Conditioned Paired AIS-Gap Triage: rank retrospective, anomalous paired gaps for analyst review.”

Do not use: “we detect transfers,” “nobody does dark rendezvous,” “existing tools only see broadcasting vessels,” “real-time interdiction,” “oil/sanctions coverage,” or “free current production data.”

Every event view should show: the two endpoint records; gap duration; counterpart/gear/flag context; local contemporaneous dark-vessel count; null model and rank; counter-hypotheses (coverage, fleet coordination, safety/security, equipment); corroboration available/not available; and a conspicuous “not a confirmed transfer” state.

### Minimum validation before a stronger build verdict

1. **Pre-register the pairing test.** Preserve each gap's duration and endpoint cells/times. Generate a conditional null within narrow local space-time, gear-class, duration and concurrent-dark-count strata. Report sensitivity across all thresholds, not only the best cell.
2. **Benchmark against alternatives.** Compare pair ranking against single-gap risk, one-visible-vessel loitering, and a local-density baseline. Demonstrate incremental precision at a fixed analyst-review budget.
3. **Obtain adjudication.** Assemble even a small blinded set linked to observer, VMS, SAR/optical/RF, port, RFMO, or enforcement records. Measure precision/recall or, where labels are incomplete, state the verification rate and confidence intervals.
4. **Test currency and rights.** Run a token-backed pilot against current GFW GAP data, measure latency and schema stability, and resolve a commercial data license before representing the system as a product.
5. **Separate fleet class from bilateral class.** Detect connected components / sequential-MMSI fleet behavior before ranking possible bilateral pairs. Do not suppress the dominant fleet explanation.

## Decision

**Build a constrained demo; do not build the original business thesis.** The project can impress as a transparent research-quality workflow because the strongest material is honest calibration, source-aware verification, and a visible uncertainty state. The current evidence does not support a category-creation, real-time, commercial-MDA, or confirmed-transshipment pitch.

The next 40-hour build should deliver one historical pair investigation, its conditional null, a fleet/coverage counterfactual, and an evidence packet that explicitly asks for corroboration. A future product decision should wait until the five validation gates above are satisfied.

## Scope and limitations

Research completed 5 September 2026 across primary scientific papers and data documentation, U.S. government postings, international guidance, commercial documentation, and independent news. The report verifies public claims and does not inspect private vendor algorithms, non-public government systems, a live authenticated GFW response, or a patent database. Vendor performance claims are not treated as independently validated.

## Sources

- **S1.** Welch et al., “Hot spots of unseen fishing vessels,” *Science Advances* 8(44), 2 Nov. 2022. https://doi.org/10.1126/sciadv.abq2109
- **S2.** Global Fishing Watch, “AIS-disabling-high-seas” repository/data README, accessed 5 Sep. 2026. https://github.com/GlobalFishingWatch/AIS-disabling-high-seas/tree/main/data
- **S3.** Global Fishing Watch API, “Data Caveats,” accessed 5 Sep. 2026. https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/data-caveats
- **S4.** Global Fishing Watch API, “Get All Events,” accessed 5 Sep. 2026. https://globalfishingwatch.org/our-apis/documentation/docs/v3/events/get-all-events
- **S5.** Global Fishing Watch, “Downloadable Transshipment Data,” accessed 5 Sep. 2026. https://globalfishingwatch.org/datasets-and-code-transshipment/
- **S6.** Fernandez-Villaverde, Li, Xu and Zanetti, “Charting the Uncharted: The (Un)Intended Consequences of Oil Sanctions and Dark Shipping,” Oxford Discussion Paper, 2025; revised Jul. 2026. https://users.ox.ac.uk/~wadh4073/research_files/Dark_Shipping.pdf
- **S7.** Skylight, “Dark Rendezvous,” current documentation, accessed 5 Sep. 2026; and *Skylight User Guide*, updated 8 Mar. 2024. https://skylight.helpjuice.com/en_US/vessel-behavior-events/dark-rendezvous ; https://www.skylight.global/Custom/Support/conservation-user-guide.pdf
- **S8.** U.S. Government Accountability Office, *Combating Illegal Fishing: Clear Authority Could Enhance U.S. Efforts to Partner with Other Nations at Sea*, GAO-22-104234, 5 Nov. 2021. https://www.gao.gov/products/gao-22-104234
- **S9.** U.S. Coast Guard, “How the Coast Guard is transforming data into action at sea,” 29 Jul. 2025. https://www.mycg.uscg.mil/News/Article/4258464/how-the-coast-guard-is-transforming-data-into-action-at-sea/
- **S10.** Western and Central Pacific Fisheries Commission, “Tracking Purse Seine Transshipment in the WCPO: Preliminary Findings,” 6 Dec. 2018. https://meetings.wcpfc.int/file/6935/download
- **S11.** Global Fishing Watch API, “License and Rate Limits,” accessed 5 Sep. 2026. https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits
- **S12.** U.S. Coast Guard Navigation Center, “AIS Frequently Asked Questions,” accessed 5 Sep. 2026. https://navcen.uscg.gov/ais-frequently-asked-questions
- **S13.** Windward, “All-Source Operational Intelligence for Maritime Ops,” accessed 5 Sep. 2026. https://windward.ai/multi-source/
- **S14.** Associated Press, “Canada and Philippines are in final negotiations for defense pact to boost joint military exercises,” 8 Feb. 2025. https://apnews.com/article/129b827017ade938af3c1f1e262fc72f
- **S15.** Food and Agriculture Organization of the United Nations, “Voluntary Guidelines for Transshipment,” 27 Apr. 2023. https://www.fao.org/iuu-fishing/resources/detail/en/c/1638082/
- **S16.** NOAA Fisheries, “Seafood Import Monitoring Program Facts and Reports,” updated 7 Jan. 2025. https://www.fisheries.noaa.gov/international/international-affairs/seafood-import-monitoring-program-facts-and-reports
