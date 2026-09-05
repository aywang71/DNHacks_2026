# GapPair — research notes (verification log, reuse maps, references)

Superseded as the plan by `build-plan.md`, which is the design document. This file keeps the verified facts, the Oxford and Skylight reuse maps, the Atlantes dig, and the documented thresholds with sources.

**Prepared:** Sat 5 Sep 2026, 14:00 EDT.
**Status:** historical proposal and verification log. It predates the current
Python ingestion CLI, GFW Bronze/Silver collections, Node presence importer,
and frontend viewer. Use [REPO_MAP.md](../REPO_MAP.md) for the live repository
state and data locations.
**Positioning in one line:** Skylight detects rendezvous when two vessels broadcast (Standard) or one does (Dark). GapPair is the missing third tier: **neither broadcasts**. We pair the absences, score them with the Oxford dark-shipping algorithm, and corroborate them with Skylight's own open-source night-lights detector.

---

## 1. What we verified today (facts that shape the plan)

| Question | Finding | Source |
|---|---|---|
| Can we modify Skylight's Dark Rendezvous model? | No. It is proprietary. Only AI2's imagery detectors are open (`allenai/vessel-detection-viirs`, `allenai/vessel-detection-sentinels`). | GitHub allenai org |
| Can we get a Skylight account or push events into its UI? | No. Org-level letter/MOU, no timeline, read-only API, public map excludes Dark Rendezvous and tracks. | skylight.global/api-policy, support docs |
| What does Skylight's model do, in words? | "A single vessel transmitting AIS displays rendezvous-like behavior for at least 15 minutes (speed, course)... A second vessel not transmitting AIS may be present... but is not visible to Skylight." | support.skylight.global/en_US/dark-rendezvous |
| Is the Oxford paper's code public? | No. "Available upon request." We re-implement from Appendix A pseudocode (A.1–A.4). | paper p.A-3 |
| Is Skylight's VIIRS detector runnable on a laptop? | Yes. Docker image, CPU only, 4 GB RAM, "results in under a second". Pretrained weights included. | allenai/vessel-detection-viirs README |
| Is there nightly boat-detection data for 2017 without running a model? | Yes. NOAA EOG VIIRS Boat Detection, global, nightly CSV, CC BY 4.0 for the FINAL tier. | eogdata.mines.edu/products/vbd |
| Would SAR/optical imagery cover the showcase pair? | Almost certainly not. GFW: "Sentinel-1 SAR data does not sample most of the open ocean." | GFW data caveats |
| GFW API token? | Free, self-service, immediate. Events API serves fishing / encounters / loitering / port visits from 2017. | globalfishingwatch.org/our-apis |
| Frozen research corpus | 55,368 derived GAP events (2017-2019); use only for endpoint-level research and validate its own provenance before analysis. | `data/disabling_events.zip`; live data locations are in [REPO_MAP.md](../REPO_MAP.md) |
| Local implementation status | The earlier `pipeline/` paths are not part of this checkout. Current ingestion is in `src/dark_rendezvous/`; the experimental Presence-to-ATLAS adapter is `src/dark_rendezvous/atlantes_adapter.py`. Candidate pairing and null-model work remain proposed. | [REPO_MAP.md](../REPO_MAP.md) |
| Is there a fisheries analog to the paper's "sanctioned country" list? | Yes. The EU IUU carding list. Taiwan held a yellow card from Oct 2015 to 27 Jun 2019, spanning the whole corpus and the TWN vessel in the showcase pair. Vietnam carded 2017; Cambodia red. | ec.europa.eu/commission/presscorner/detail/en/ip_19_3397 |
| Is the showcase water managed by an RFMO with a registry and IUU list? | Yes. 42.7°N 162°E is inside the North Pacific Fisheries Commission area, which manages neon flying squid, keeps a vessel registry, and has kept an IUU vessel list under CMM 2017-02. | npfc.int/npfc-iuu-vessel-list |
| Does Skylight publish any of its AIS behaviour code? | Yes. `allenai/atlantes` (Apache-2.0, pushed Jul 2026) holds the ATLAS activity and vessel-type models with weights, the changepoint detector (2 h gap rule), and the one-sided-rendezvous label script. No rendezvous model or weights are public. Details in §4. | github.com/allenai/atlantes |

The showcase pair is two **squid jiggers**. Squid jiggers fish under lights so bright they are the single most detectable vessel class in VIIRS night imagery. That is the luckiest fact in this project and the plan is built around it.

---

## 2. Reuse map — the Oxford paper

Appendix A gives four algorithms. Our corpus has only gap endpoints (no headings, speed, draft, or tracks), so each is either reused, adapted with a stated substitution, or dropped.

| Paper component | Verdict | How we use it |
|---|---|---|
| **Level 1 trip classification** (trip starts or ends at a port in a sanctioned country → suspicious before any gap analysis) | **Adapt as a "trip and identity context" block.** | No sanctions list for fishing, so four public risk lists play the same role: (1) flag-state risk from the EU IUU carding list, the fisheries analog of the paper's Paris MoU list; (2) RFMO authorization for the water where the vessel went dark, from GFW Vessels API public authorizations (NPFC registry for the showcase pair); (3) port country before and after the gap from GFW port-visit events, with non-parties to the FAO Port State Measures Agreement as risk ports; (4) the combined RFMO IUU vessel list. Together these are `context_risk`. |
| **Fig. 1c geometry** (last signal → dashed projection → intersection point → first signal, two colours, "long data gap" brackets) | **Reuse as the per-candidate map drawing.** | Render exactly this from the four endpoints. Square marker labelled "feasible meeting point (heuristic)". |
| **A.2 ship-to-ship suspicion score** (overlapping gaps → meeting time = overlap midpoint → required speed out and back → 1 − percentile of required speed) | **Adapt.** | Meeting point: no headings, so evaluate a small set of candidates (midpoint of starts, midpoint of ends, centroid, and a 5×5 grid around the centroid) and take the one minimising the larger vessel's required speed. Percentile reference: the corpus-wide distribution of implied gap speed (start→end distance / gap hours). Output: `sts_plausibility ∈ [0,1]`. |
| **A.3 heading intersection** | **Drop, state why.** | Headings are not in the public corpus. Optional Sunday-morning add: the vessel's last GFW fishing event before the gap gives a coarse direction of travel. |
| **A.1 port-based suspicion** (required speed to reach the nearest suspicious port and return during the gap; low required speed → high suspicion) | **Reuse with the paper's sign.** | Against the risk-port list from Level 1 (non-PSMA ports, ports in carded flag states) it is a positive feature `risk_port_reach`: a vessel dark offshore that could have reached a risk port and returned is the unreported-landing pattern. Against a generic port list (Natural Earth `ne_10m_ports`) the same geometry only yields the `possible-port-transit` label. 7% of gaps end inside 50 nm with a 66 h median, so this fires often enough to matter. |
| **Long-gap definition** (per-vessel 99th percentile of inter-signal time) | **Reuse.** | GFW already applies ≥12 h. We add `gap_unusualness` = this gap's percentile within the vessel's own gap history. |
| **A.4 vessel-level clustering** (trip score, idle ratio, age, operator fleet size, Paris MoU flag rank; 2-cluster k-means) | **Adapt, partially.** | Flag rank → EU carding status (and Tokyo MoU list for Asia-Pacific flags). Repeat-participation (MMSI 577101000 has 173 events, 7 of 27 cross-flag pairs) replaces "idle ratio". Owner/fleet size and build year via GFW Vessels API registry fields, token-gated. k-means kept as an optional "paper-style partition" toggle, not as the ranking. |
| **Level 3 kinematics** (detour factor, speed std-dev, average speed per trip) | **Drop.** | Need tracks. The only proxy is `gap_unusualness` above. Say so in the methodology drawer. |
| Sanctions/tanker figures (558 dark tankers/yr, 43% of seaborne crude) | **Borrow for context only.** | One slide: "the method is the paper's; the evidence here is fishing vessels; the paper shows the tanker scale." Label as the paper's model estimates. |

---

## 3. Reuse map — Skylight

| Skylight asset | Verdict | How we use it |
|---|---|---|
| **Event taxonomy** Standard Rendezvous (2 of 2 on AIS) / Dark Rendezvous (1 of 2) | **Reuse as framing.** | Our event type is the missing row: **Paired-Dark Rendezvous candidate (0 of 2)**. Show all three tiers in the "how it works" panel, using our own illustrations in the style of Skylight's explainer cards (`tmp/skylight-ref/02`, `03`). |
| **UI layout** full-bleed map, floating event cards anchored at location, teal header, two-column label/value grid, "Vessels in the Vicinity" list, event-history count, thumbs up/down feedback | **Reuse the pattern.** | Wireframe in §6. Thumbs feedback becomes our `analyst_disposition` capture, which is the label the data spec says we need. |
| Icon convention black = AIS-corroborated, red = not | **Reuse.** | Filled endpoint = AIS fact; hollow red = inferred (meeting point, projected paths). |
| Speed-coloured tracks with chevrons | **Drop.** | No tracks. Replace with dashed red "dark window" projections and solid short stubs. |
| "Night Lights" event type and glow icon | **Reuse.** | VIIRS detections render as glowing dots, like Skylight's Night Lights illustration (`04`). |
| **`allenai/vessel-detection-viirs`** Docker, CPU | **Run it.** | Stretch but high-value: run Skylight's own detector on the archival VIIRS DNB granule over the showcase pair's night. "Skylight's model sees a lit vessel where AIS is silent" is the line. |
| Light basemap (pale cyan water, grey land) | **Reuse the look** via CARTO Positron (free, no key). | A dark basemap reads as "hacker"; Skylight's light one reads as "analyst tool". Decide in §8. |
| **Areas of Interest + Entry events** (rule-based: vessel crosses into a user AOI) | **Reuse as `eez_entry_while_dark`.** | Gap starts on the high seas and ends inside an EEZ, computed from the end coordinates against public EEZ polygons (Marine Regions). Also names the jurisdiction on the card. RFMO convention areas are the second AOI layer, and feed the Level 1 authorization check. |
| **Detection–AIS correlation** (black icon = a broadcasting vessel explains the detection, red = it does not) | **Reuse for VIIRS.** | A night-light counts as corroboration only if no broadcasting vessel explains it. Correlate against GFW's AIS presence layer for that day and cell; fallback is the corpus' own broadcasting endpoints within ±1 h. Uncorrelated lights render red, correlated black, exactly Skylight's convention. |
| **Dark Rendezvous single-vessel kinematic model** (ML on one visible vessel's speed and course, ≥15 min) | **Substitute.** | We cannot run it and have no tracks. GFW LOITERING events (a vessel under 2 kn for an extended period away from port) are the closest public analog and enter Detector 3 as a scored input, not as context text. |

---

## 4. Atlantes, and the rendezvous rules we cite instead of inventing

### 4.1 What `allenai/atlantes` actually contains

Apache-2.0, last push July 2026, described by AI2 as Skylight's AIS backbone since fall 2024 (paper: arXiv 2504.19036, ICLR CCAI 2025).

| Item | Finding | Use for us |
|---|---|---|
| ATLAS activity model | Weights in-repo, not LFS (19 MB). Classifies the end of a track as fishing / anchored / moored / transiting (+ other, unknown). Input columns: lat, lon, sog, cog, send, nav, mmsi, trackId, dist2coast, name, flag_code, category. | Needs raw tracks. Our corpus has endpoints only and GFW's API serves no tracks, so it cannot run on our vessels. Citable architecture; optional 20-minute demo on the repo's NOAA sample track to show "what Skylight's backbone sees". |
| ATLAS entity models | Vessel type (fishing, cargo, tanker, ...) and buoy-vs-vessel, weights in-repo. | Same track limitation. |
| Changepoint detector (`cpd/constants.py`) | `MIN_TIME_GAP = 2 h` splits a track into subpaths; `MAX_DURATION = 24 h`; `MAX_NUM_MESSAGES = 500`; SOG-distribution changepoints. | Skylight's own documented definition of an AIS gap. Cite it next to GFW's 12 h corpus threshold. |
| **One-sided rendezvous (OSR) dataset script** (`gen_dataset_label_files/create_osr_dataset.py`, config label `one_sided_rendezvous`) | Training data for the one-visible-vessel model is made by taking **two-sided Standard Rendezvous events**, keeping only vessel 0's track for that day with a week of context, and labelling the messages inside the event window as `one_sided_rendezvous`. Docs: "we have an OSR model branch but it has not been merged." No OSR model or weights are public. | **This is the documented Dark Rendezvous recipe: learn the one-sided signature from two-sided events.** See 4.3. |
| Branch `henryh/tutorials` | Adds `ais/tutorials/eval.ipynb` running `AtlasActivityClassifier` on public NOAA coastal AIS, plus NOAA-to-Atlantes converters. References a Hugging Face dataset `hherzog/atlantes-noaa-dataset` that the HF API did not resolve; verify before relying on it. | The only path to run ATLAS without AI2's cloud. NOAA data is US-coastal, so still not our vessels. |
| Other branches | `mike/atlas-sidecar` (53 commits, inference refactor), `mike/bump-cpd-timegap` (changes the 2 h constant), `debug-int-vs-prod`, dependabot, and several `josh/claude/*` buoy-pattern branches. No branch contains rendezvous model code. | Nothing further to mine. |
| Docker inference | `docker-compose.yml` mounts GCP credentials; the notebook path loads in-repo weights directly and `main_activity.py` has no GCS references. | Local inference likely works without GCP. Verify only if the demo in row 1 is wanted. |

### 4.2 Documented thresholds, quoted, and where each enters our model

| Source | Rule, as published | Where it enters GapPair |
|---|---|---|
| Skylight Standard Rendezvous | Two AIS signals within **250 m**, together **≥30 min**, speeds **<4 kn**, **>10 km** from coast; buoys excluded. | The 2-of-2 tier in the "how it works" panel. |
| Skylight Dark Rendezvous | One transmitting vessel shows rendezvous-like behaviour for **≥15 min**; not generated within **100 km** of shore; "ground truth data to create such a machine learning model is limited". | The 1-of-2 tier. The 100 km exclusion matches our corpus, whose gaps all start ≥93 km offshore. |
| GFW encounter (Miller et al. 2018; GFW FAQ) | Within **500 m** for **≥2 h**, median speed **<2 kn**, **≥10 km** from an anchorage, on a 10-minute interpolated grid. Sensitivity ranges tested: 250–1000 m, 2–12 h, 1–6 kn. | Detector 3 "known partners" feature, and the lineage for Detector 1's endpoint thresholds (below). |
| GFW loitering (Miller et al. 2018) | Average speed **<2 kn**, **≥20 nm** from shore, **≥8 h** for a reefer. The API's loitering dataset uses the same speed and shore rule with a shorter minimum duration; confirm the value when the token arrives. | Detector 3's single-vessel behaviour input, the public analog of Skylight's one-sided model. |
| Welch et al. 2022 (our corpus) | Reception **>10 positions/day**, gap **≥12 h**, **≥50 nm** from shore, boosted-regression-tree split of intentional vs coverage loss. | Provenance of every input event; quoted in the methods drawer. |
| Atlantes CPD | Time gap **≥2 h** splits a subpath. | Cited alongside the 12 h corpus threshold to show our gaps are 6× Skylight's own cut. |
| Ballinger 2024 (arXiv 2404.07607) | Dark STS in the Kerch Strait from satellite detections cross-referenced with AIS gaps; STS defined as **500 m, ≥2 h, SOG <1 kn**. | Precedent for imagery-plus-gap corroboration; cited beside our VIIRS layer. |
| Fernández-Villaverde et al. 2025 | Two vessels dark simultaneously in close proximity, required-speed plausibility (Alg. A.2). | Detector 2, and the only published precedent for reasoning about two simultaneously dark vessels. |
| OFAC / State / USCG 2020 maritime advisory | Deceptive practices list: AIS disabling or manipulation, illicit STS, extended transmission gaps, abnormal voyage patterns, MMSI manipulation. | Language for the context block and the deck's "why this matters" line. |

**Why Detector 1 uses 10 km / 1 h and not 500 m / 2 h.** Encounter rules apply to positions during the meeting. Our endpoints are the last fix before and the first fix after a gap of 12 to 40 hours, during which both vessels move. Ten kilometres and one hour at each end is the endpoint analog of the encounter rule, and the permutation null is what calibrates it. The threshold ladder in the methods drawer shows the same signal at 5 km / 1 h and 25 km / 3 h.

### 4.3 The lineage we can state on one slide

Skylight built its one-sided detector from two-sided events: take a Standard Rendezvous, hide one vessel, learn what the other looks like. GapPair takes the next step in the same direction: take the paired gap where both vessels are hidden, and calibrate it against the same two-sided events. Concretely, Detector 3 checks whether a paired gap is bracketed by a published GFW encounter or loitering event involving either vessel. That is convergent validation using the very event type Skylight trains from, and it is the honest answer to "where are your labels".

Both research agents confirm the same thing: **no published rule set exists for a zero-visible-vessel paired gap.** Skylight and GFW pair a dark or loitering vessel against a visible one; the Oxford paper is the only precedent for two simultaneously dark vessels. Gap-to-gap pairing with a permutation null is our synthesis, and the deck should say so plainly rather than claim it is replicated from anywhere.

### 4.4 Open-source code worth borrowing

- `GlobalFishingWatch/pipe-encounters` (Apache-2.0): distance and duration matching logic with `max_encounter_dist_km` and `min_encounter_time_minutes`; adapt from position pairs to endpoint pairs, and keep its parameter names.
- `GlobalFishingWatch/pipe-gaps` (Apache-2.0): gap object schema (OFF = last position, ON = first resumed position); adopt its field names for the evidence ledger.
- `GlobalFishingWatch/AIS-disabling-high-seas`: the corpus's own thresholds and reception model, for the provenance section.
- `allenai/atlantes`: CPD constants and the OSR label recipe, cited; ATLAS weights only for the optional NOAA demo.

---

## 5. The model: a transparent three-family ensemble

No labels exist, so the "ensemble" is a scorecard with a calibrated null, not a trained classifier. Every component is displayed as its own bar on the card.

```
priority = w1·synchrony_surprise      (Detector 1, ours: both-ends 10 km / 1 h, lift vs within-cell null)
         + w2·sts_plausibility        (Detector 2, Oxford A.2 adapted)
         + w3·corroboration           (Detector 3: uncorrelated VIIRS light in feasible region; GFW loitering / encounter)
         + w4·context_risk            (Oxford Level 1 adapted: flag carding, RFMO authorization, port context, IUU list)
         + w5·risk_port_reach         (Oxford A.1, paper's sign: a risk port reachable during the gap)
         − w6·local_density_penalty   (other gaps within 200 km / ±1 h)
         − w7·fleet_penalty           (component size, same-flag share, sequential MMSI)
flags    eez_entry_while_dark, possible_port_transit   (shown on the card, not weighted)
```

Labels from the sign of the penalties: `investigate` · `coordinated-fleet-pattern` · `likely-coverage-or-cluster-artifact` · `possible-port-transit` · `insufficient-evidence`.

**Level 1 in detail (the paper's trip classification, adapted).** The paper decides suspicion first from where a trip went, then from gaps. Our `context_risk` does the same with four joins, all on fields we hold or can fetch:
- **Flag-state risk**: EU IUU carding status at the gap date (yellow / red / none), joined on the corpus `flag` column with a hand-made table of card dates. Tokyo MoU flag list as a second column for Asia-Pacific flags.
- **RFMO authorization**: which convention area contains the shutoff position (NPFC, WCPFC, IATTC, ICCAT, IOTC, SPRFMO polygons), and whether the vessel held a public authorization for it at that date, from the GFW Vessels API. Dark inside an RFMO area without authorization is unregulated by definition.
- **Port context**: last GFW port visit before the gap and first after it, with port country; PSMA non-party ports flagged.
- **IUU listing**: MMSI or name on the combined RFMO IUU vessel list.

**Detector 3 in detail (the Skylight analog).** Skylight watches the visible vessel's behaviour and correlates detections with AIS. We have no tracks, so we use public substitutes for both halves:
- **GFW behaviour events** per vessel, ±7 days around the gap (Events API, needs token): a carrier LOITERING event nearby during the window (the closest public analog to Skylight's single-vessel kinematic signal), a prior ENCOUNTER between the same two vessels (known partners), FISHING events at the same spot just before (fishing ground, not transfer). Each is a signed, weighted feature with a sentence in the evidence ledger.
- **VIIRS night-lights** for the dark night(s): NOAA EOG VBD detections inside the feasible region, three-state: detection / clear-sky no detection / cloud or no coverage. A detection is corroboration only after the AIS-correlation test in §3 says no broadcasting vessel explains it. For squid jiggers, "clear sky, no lights" is itself anomalous and is reported as such.

Evaluation we can honestly show: the lift ladder against null C (prior run: 35× at the operating threshold, 22.5× cross-flag), the share of candidates each penalty removes, and the showcase pair's full ledger.

---

## 6. UI wireframe (Skylight pattern, our content)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ GapPair  ▸ Paired-dark candidates · 2017–2019 · GFW corpus        [Methods] │  ← thin teal strip
├───────────────┬──────────────────────────────────────────────────────────────┤
│ QUEUE (437)   │  MAP (MapLibre + deck.gl, CARTO Positron)                    │
│ ▣ cross-flag  │                                                              │
│ ▢ fleet       │      ●───────╌╌╌╌╌╌▶ ■ ◀╌╌╌╌╌╌───────●   vessel A (red)      │
│ ▢ artifact    │      ○───────╌╌╌╌╌╌▶   ◀╌╌╌╌╌╌───────○   vessel B (blue)     │
│───────────────│                    ✦ VIIRS 01:47 local                       │
│ #1 CHN/TWN    │      ·  ·   (other dark gaps ±1 h, grey)                     │
│  0.91 investig│                                                              │
│ #2 VUT/TWN    │   ┌─ EVENT CARD (floating, anchored) ──────────────────────┐ │
│  0.84 investig│   │ Paired-Dark Rendezvous candidate         [▾][×]        │ │
│ #3 CHN/CHN    │   │ Vessel A 412331147 CHN squid jigger │ B 416004105 TWN  │ │
│  0.31 fleet   │   │ Dark 2017-07-01 04:12Z (Δ 5 s)      │ Back +41.8 h (Δ43s)│ │
│ ...           │   │ Start sep 6.6 km │ End sep 4.1 km │ 482 nm offshore     │ │
│               │   │ ── Score ─────────────────────────────────────────────  │ │
│               │   │ Synchrony  ████████░ 35× null C                          │ │
│               │   │ STS plaus. ███████░░ req. 2.3 kn (p05)                   │ │
│               │   │ Corrobor.  ██████░░░ VIIRS lit vessel in region          │ │
│               │   │ Density   −█░░░░░░░░ 3 others within 200 km              │ │
│               │   │ Fleet     −░░░░░░░░░ component size 2, cross-flag        │ │
│               │   │ Context   ████░░░░░ TWN yellow card 2015–19 · NPFC reg ✓ │ │
│               │   │ Risk port ░░░░░░░░░ nearest risk port 890 km, needs 21 kn│ │
│               │   │ Flags: high seas → high seas (no EEZ entry while dark)   │ │
│               │   │ ── Vessels in the vicinity (±1 h, 200 km) ─────────────  │ │
│               │   │ 🇻🇺 577101000 · 🇨🇳 412…                                 │ │
│               │   │ ── Assessment (agent) ─────────────────────────────────  │ │
│               │   │ "Both vessels ceased AIS within [5 s]✓ at [6.6 km]✓ …    │ │
│               │   │  … a lift of [35×]✓ over a [within-cell null]✓ …"        │ │
│               │   │ [👍 investigate] [👎 dismiss] [⚠ adversarial mode]       │ │
│               │   └────────────────────────────────────────────────────────┘ │
│               │  ◀━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━▶ time scrubber (gap)   │
└───────────────┴──────────────────────────────────────────────────────────────┘
```

Also: a **Challenge panel** tab ("what would make this innocent?") and a **Methods drawer** (thresholds, three nulls, sources: GFW, Skylight, Oxford, WCPFC, EOG).

---

## 7. Options evaluated

**Product shape**
- **A. Standalone GapPair, Skylight-pattern UI, Oxford-adapted scoring, VIIRS corroboration.** Recommended. Every piece is public data or open code; the Skylight tie-in can use their open detector and event taxonomy.
- B. Same scoring, Streamlit + pydeck UI. Faster for a Python-only team, but click-to-select is weak, animation is clunky, and it looks like a notebook. Fallback only.
- C. Skylight-branded integration (mock API, mock "push"). A viable demo presentation option if the team chooses to prioritize a direct Skylight-style experience.

**Front end**
- **Single HTML file, CDN MapLibre + deck.gl, precomputed JSON.** Recommended for a crude prototype: no build step, opens on Windows and macOS, survives venue wifi if the tiles are cached once, and the "one live button" (adversarial verifier / GFW fetch) hits a tiny local Python server or is pre-recorded.
- Vite + React + deck.gl. Same look, cleaner code, ~1 extra hour. Choose it only if whoever owns the UI is already a React dev.
- kepler.gl: 20 minutes to a data look for us, wrong shape for the deliverable. GFW's open frontend: MIT but welded to their API config model; use as a screenshot reference only.

**Corroboration (ranked by value per hour)**
1. EOG VBD nightly CSV for the showcase pair's nights (free account, filter a bbox). ~1 hour. Shown as glowing dots inside the feasible region with local time.
2. Run `allenai/vessel-detection-viirs` in Docker on the archival VNP02DNB/VNP03DNB granules for that overpass (Earthdata login, swap NRT URLs for LAADS DAAC). ~2–3 hours, needs Docker on the Mac. Payoff: "Skylight's model, on the same night, independently." Do it only after item 1 succeeds.
3. GFW events and identity for the top 30 candidates (token). ~2 hours. Payoff: loitering/encounter inputs for Detector 3, port visits and RFMO authorizations for Level 1, owner and build year for A.4. The flag-carding and IUU-list joins need no token and take ~30 minutes.
4. SAR/optical: 15-minute check, expect nothing, and report "no coverage" honestly. The three-state coverage result is itself a feature of the product.

**Scoring model**
- Transparent scorecard + null lift. Recommended.
- Paper-style two-cluster k-means as a toggle. Cheap, cosmetic, optional.
- Trained classifier. No labels; rejected, and the methods drawer says why.

**Agent-trust component (Defense track)**
- Keep the narration + span verifier. It is ~3 hours of Sonnet work, the record is a flat JSON so verification is field lookup with tolerances (±1000 m on shore distance, ±0.017 h on duration, "estimated" badge on length/tonnage), and the adversarial button is the one live demo moment that no other team will have.

---

## 8. Decisions needed from the team

1. Light basemap (Skylight look, CARTO Positron) or dark (CARTO Dark Matter)? Recommendation: light.
2. Single-HTML or Vite + React? Recommendation: single-HTML unless the UI owner is a React dev.
3. LLM for narration: OpenAI (sponsor points) or Anthropic? Either works for the verifier.
4. Who owns UI, who owns corroboration data? Docker available on the Mac?
5. Track: Defense (verifier as the agent-trust answer) unless a partner prompt released on-site fits better.
