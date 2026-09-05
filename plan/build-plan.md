# GapPair — proposal and plan of action

**Prepared:** Sat 5 Sep 2026, 14:00 EDT. Submission Sun 12:00. ~22 hours.
**Status:** proposal only. Nothing beyond data download and a partial loader has been built.
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
| Data on disk? | Yes. 55,368 gaps, all 15 columns, 815 invalid MMSIs quarantined (matches the Aug 31 run exactly). | `data/raw`, `data/derived/exclusions.json` |
| Local prior work? | `pipeline/load.py` done; `pipeline/pair.py` written, never run; nulls/features not written. Skylight UI screenshots saved to `tmp/skylight-ref/`. Paper Figure 1 at `tmp/pdfs/dark-page-11.png`. | this session |

The showcase pair is two **squid jiggers**. Squid jiggers fish under lights so bright they are the single most detectable vessel class in VIIRS night imagery. That is the luckiest fact in this project and the plan is built around it.

---

## 2. Reuse map — the Oxford paper

Appendix A gives four algorithms. Our corpus has only gap endpoints (no headings, speed, draft, or tracks), so each is either reused, adapted with a stated substitution, or dropped.

| Paper component | Verdict | How we use it |
|---|---|---|
| **Fig. 1c geometry** (last signal → dashed projection → intersection point → first signal, two colours, "long data gap" brackets) | **Reuse as the per-candidate map drawing.** | Render exactly this from the four endpoints. Square marker labelled "feasible meeting point (heuristic)". |
| **A.2 ship-to-ship suspicion score** (overlapping gaps → meeting time = overlap midpoint → required speed out and back → 1 − percentile of required speed) | **Adapt.** | Meeting point: no headings, so evaluate a small set of candidates (midpoint of starts, midpoint of ends, centroid, and a 5×5 grid around the centroid) and take the one minimising the larger vessel's required speed. Percentile reference: the corpus-wide distribution of implied gap speed (start→end distance / gap hours). Output: `sts_plausibility ∈ [0,1]`. |
| **A.3 heading intersection** | **Drop, state why.** | Headings are not in the public corpus. Optional Sunday-morning add: the vessel's last GFW fishing event before the gap gives a coarse direction of travel. |
| **A.1 port-based suspicion** (required speed to reach the nearest port and return during the gap) | **Reuse as an alternative explanation.** | For fishing vessels this is the "port run" hypothesis. 7% of gaps end inside 50 nm with a 66 h median; a high A.1 score means the gap may be a transit, not a meeting. Port list: Natural Earth `ne_10m_ports` (free, ~1,000 ports). |
| **Long-gap definition** (per-vessel 99th percentile of inter-signal time) | **Reuse.** | GFW already applies ≥12 h. We add `gap_unusualness` = this gap's percentile within the vessel's own gap history. |
| **A.4 vessel-level clustering** (trip score, idle ratio, age, operator fleet size, flag risk; 2-cluster k-means) | **Adapt, partially.** | Flag is in the corpus. Repeat-participation (MMSI 577101000 has 173 events, 7 of 27 cross-flag pairs) replaces "idle ratio". Owner/fleet size and build year via GFW Vessels API if the token arrives. k-means kept as an optional "paper-style partition" toggle, not as the ranking. |
| Detour factor, speed std-dev | **Drop.** | Need tracks. Say so in the methodology drawer. |
| Sanctions/tanker figures (558 dark tankers/yr, 43% of seaborne crude) | **Borrow for context only.** | One slide: "the method is the paper's; the evidence here is fishing vessels; the paper shows the tanker scale." Label as the paper's model estimates. |

---

## 3. Reuse map — Skylight

| Skylight asset | Verdict | How we use it |
|---|---|---|
| **Event taxonomy** Standard Rendezvous (2 of 2 on AIS) / Dark Rendezvous (1 of 2) | **Reuse as framing.** | Our event type is the missing row: **Paired-Dark Rendezvous candidate (0 of 2)**. Show all three tiers in the "how it works" panel, using our own illustrations in the style of Skylight's explainer cards (`tmp/skylight-ref/02`, `03`). |
| **UI layout** full-bleed map, floating event cards anchored at location, teal header, two-column label/value grid, "Vessels in the Vicinity" list, event-history count, thumbs up/down feedback | **Reuse the pattern.** | Wireframe in §5. Thumbs feedback becomes our `analyst_disposition` capture, which is the label the data spec says we need. |
| Icon convention black = AIS-corroborated, red = not | **Reuse.** | Filled endpoint = AIS fact; hollow red = inferred (meeting point, projected paths). |
| Speed-coloured tracks with chevrons | **Drop.** | No tracks. Replace with dashed red "dark window" projections and solid short stubs. |
| "Night Lights" event type and glow icon | **Reuse.** | VIIRS detections render as glowing dots, like Skylight's Night Lights illustration (`04`). |
| **`allenai/vessel-detection-viirs`** Docker, CPU | **Run it.** | Stretch but high-value: run Skylight's own detector on the archival VIIRS DNB granule over the showcase pair's night. "Skylight's model sees a lit vessel where AIS is silent" is the line. |
| Light basemap (pale cyan water, grey land) | **Reuse the look** via CARTO Positron (free, no key). | A dark basemap reads as "hacker"; Skylight's light one reads as "analyst tool". Decide in §8. |
| Wordmark, logo, "product of Ai2", exact copy | **Do not touch.** | Cite as prior art in the drawer and deck. |

---

## 4. The model: a transparent three-family ensemble

No labels exist, so the "ensemble" is a scorecard with a calibrated null, not a trained classifier. Every component is displayed as its own bar on the card.

```
priority = w1·synchrony_surprise      (Detector 1, ours: both-ends 10 km / 1 h, lift vs within-cell null)
         + w2·sts_plausibility        (Detector 2, Oxford A.2 adapted)
         + w3·corroboration           (Detector 3: VIIRS detection in feasible region; GFW context events)
         − w4·local_density_penalty   (other gaps within 200 km / ±1 h)
         − w5·fleet_penalty           (component size, same-flag share, sequential MMSI)
         − w6·port_run_penalty        (Oxford A.1: could this gap be a port transit?)
```

Labels from the sign of the penalties: `investigate` · `coordinated-fleet-pattern` · `likely-coverage-or-cluster-artifact` · `possible-port-transit` · `insufficient-evidence`.

**Detector 3 in detail (the Skylight analog).** Skylight watches the visible vessel's behaviour. We have no tracks, so we use two public substitutes:
- **GFW context events** per vessel, ±7 days around the gap (Events API, needs token): a prior published ENCOUNTER between the same two vessels (known partners), FISHING events at the same spot just before (fishing ground, not transfer), a carrier LOITERING event nearby (transshipment context), a PORT VISIT right after (offload). Each is a signed feature with a sentence in the evidence ledger.
- **VIIRS night-lights** for the dark night(s): NOAA EOG VBD detections inside the feasible region, three-state: detection / clear-sky no detection / cloud or no coverage. For squid jiggers, "clear sky, no lights" is itself anomalous and is reported as such.

Evaluation we can honestly show: the lift ladder against null C (prior run: 35× at the operating threshold, 22.5× cross-flag), the share of candidates each penalty removes, and the showcase pair's full ledger.

---

## 5. UI wireframe (Skylight pattern, our content)

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
│               │   │ Port run  −░░░░░░░░░ nearest port 890 km, needs 21 kn    │ │
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

## 6. Options evaluated

**Product shape**
- **A. Standalone GapPair, Skylight-pattern UI, Oxford-adapted scoring, VIIRS corroboration.** Recommended. Every piece is public data or open code; nothing is mocked; the Skylight tie-in is real (their open detector) and honest (their event taxonomy has a hole we fill).
- B. Same scoring, Streamlit + pydeck UI. Faster for a Python-only team, but click-to-select is weak, animation is clunky, and it looks like a notebook. Fallback only.
- C. Fake a Skylight integration (mock API, mock "push"). Rejected. Judges who know Skylight will ask one question and the demo dies.

**Front end**
- **Single HTML file, CDN MapLibre + deck.gl, precomputed JSON.** Recommended for a crude prototype: no build step, opens on Windows and macOS, survives venue wifi if the tiles are cached once, and the "one live button" (adversarial verifier / GFW fetch) hits a tiny local Python server or is pre-recorded.
- Vite + React + deck.gl. Same look, cleaner code, ~1 extra hour. Choose it only if whoever owns the UI is already a React dev.
- kepler.gl: 20 minutes to a data look for us, wrong shape for the deliverable. GFW's open frontend: MIT but welded to their API config model; use as a screenshot reference only.

**Corroboration (ranked by value per hour)**
1. EOG VBD nightly CSV for the showcase pair's nights (free account, filter a bbox). ~1 hour. Shown as glowing dots inside the feasible region with local time.
2. Run `allenai/vessel-detection-viirs` in Docker on the archival VNP02DNB/VNP03DNB granules for that overpass (Earthdata login, swap NRT URLs for LAADS DAAC). ~2–3 hours, needs Docker on the Mac. Payoff: "Skylight's model, on the same night, independently." Do it only after item 1 succeeds.
3. GFW context events for the top 30 candidates (token). ~2 hours. Payoff: the vicinity list and trip context.
4. SAR/optical: 15-minute check, expect nothing, and report "no coverage" honestly. The three-state coverage result is itself a feature of the product.

**Scoring model**
- Transparent scorecard + null lift. Recommended.
- Paper-style two-cluster k-means as a toggle. Cheap, cosmetic, optional.
- Trained classifier. No labels; rejected, and the methods drawer says why.

**Agent-trust component (Defense track)**
- Keep the narration + span verifier. It is ~3 hours of Sonnet work, the record is a flat JSON so verification is field lookup with tolerances (±1000 m on shore distance, ±0.017 h on duration, "estimated" badge on length/tonnage), and the adversarial button is the one live demo moment that no other team will have.

---

## 7. Workstreams and schedule (two people + Sonnet agents)

| When | Workstream | Who | Output |
|---|---|---|---|
| Sat 14:30 | Register GFW token, EOG account, Earthdata login; install Docker on the Mac | Human (10 min each) | `.env` |
| Sat 14:30–16:00 | Finish pipeline: run `pair.py`, write nulls, features (density, components, Oxford A.2 + A.1, gap unusualness), export `candidates.json` | Sonnet agent | numbers frozen; demo pair confirmed |
| Sat 15:00–17:00 | VBD download + bbox filter for the demo pair's nights; first VIIRS dots | Human A | `viirs_demo.json` |
| Sat 16:00–19:00 | Single-HTML UI: map, Fig. 1c drawing, queue, card, scrubber | Human B + Sonnet agent | opens a real candidate |
| Sat 17:00–19:00 | GFW context events for top 30 (cached JSON) | Sonnet agent | vicinity + trip context |
| Sat 19:00–22:00 | Score bars, challenge panel, methods drawer, illustrations for the three tiers | Human B | |
| Sat 20:00–23:00 | Optional: AI2 VIIRS detector in Docker on the demo night | Human A | second VIIRS layer |
| Sat 22:00–Sun 01:00 | Narration agent + span verifier + adversarial mode | Sonnet agent | live button works |
| Sun 01:00–06:00 | Polish, precompute narrations for top 20, record fallback video | both | |
| Sun 06:00–09:00 | Deck (update `ideas/martime_deck.md` numbers), README, submission text | Human A | |
| Sun 09:00–11:00 | Rehearse 60-second core three ways (Navy CTO / Aslan / OpenAI); screen recording | both | |
| Sun 12:00 | Submit | | |

Checkpoints: **16:00** numbers frozen · **19:00** a real candidate on the map · **01:00** verifier catches a corruption · **08:00** feature freeze.

---

## 8. Decisions needed from the team

1. Light basemap (Skylight look, CARTO Positron) or dark (CARTO Dark Matter)? Recommendation: light.
2. Single-HTML or Vite + React? Recommendation: single-HTML unless the UI owner is a React dev.
3. LLM for narration: OpenAI (sponsor points) or Anthropic? Either works for the verifier.
4. Who owns UI, who owns corroboration data? Docker available on the Mac?
5. Track: Defense (verifier as the agent-trust answer) unless a partner prompt released on-site fits better.

---

## 9. Claims discipline (paste into README, drawer, deck)

- Candidates for analyst review. Never "confirmed transfer", never "illegal".
- Fishing vessels, 2017–2019. The method is the Oxford paper's; the tanker evidence is theirs, not ours.
- No coordinate-level ground truth exists. WCPFC: 78% of AIS-only transshipment candidates were unsubstantiated. We show that number.
- The meeting point is a heuristic square, never a track, never a location.
- VIIRS "no detection" is reported as clear-sky-no-lights or no-coverage, never as absence.
- Skylight, GFW, AI2, the Oxford authors, and NOAA EOG are prior art and data providers, credited in the drawer. No affiliation implied.
