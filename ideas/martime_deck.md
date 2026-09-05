
# Deck outline + submission text

Written T−5. **The pre-event Part III numbers did not reproduce — this deck is built on the corrected
table.** See the feasibility artifact for the reproduction and why the old numbers were wrong.

---

# PART 1 — DECK OUTLINE (10 slides, screenshots pasted Sunday)

### 1. Title

**Dark Rendezvous** — finding the meetings nobody broadcast.
One line under it: *55,368 deliberate AIS shutdowns. We pair the absences.*

### 2. The cooperative-system problem

AIS is cooperative: a ship broadcasts because it wants to be seen. A ship that does not want to be
seen switches it off. Every maritime monitoring tool in the industry is oriented toward the vessels
that are transmitting.

> Global Fishing Watch publishes encounter detection — it requires **both vessels broadcasting**.
> It finds the rendezvous nobody was hiding.

### 3. The move

*Pair the absences.* If two vessels stop transmitting within minutes of each other in the same water,
**and resume within minutes of each other**, the coincidence is the event.
Nobody publishes paired dark-gap detection. More importantly — **nobody publishes a chance baseline
for it**, so nobody can say how often that coincidence happens innocently.

### 4. Three nulls, not one  ← *the credibility slide, and the one judges will remember*

Anyone can write a proximity rule and show hits. The question is what the same rule finds on data
where the signal has been destroyed.

|                                              | observed      | vs shuffled time | vs shuffled**within region** |
| -------------------------------------------- | ------------- | ---------------- | ---------------------------------- |
| co-located, 50 km / 24 h                     | 125,878       | 8.4×            | **2.6×**                    |
| co-located, 5 km / 1 h                       | 1,240         | 50×             | 9.4×                              |
| **both ends, 5 km / 1 h**              | **105** | 263×            | **30×**                     |
| **both ends, cross-flag, 10 km / 1 h** | **27**  | —               | **22.5×**                   |

Say out loud: *"the third column is the honest one. It permutes timestamps only among events in the
same 5° cell — so 'these vessels fish the same ground in the same season' cannot produce lift.
Simple co-location survives that at 2.6×. Two-ended simultaneity survives it at 30×."*

### 5. What two-endedness buys

Going dark near each other is common — fleets fish together.
Going dark near each other **and coming back together** is not.

> Same vessels, same threshold, one extra condition: **1,240 → 105**. Lift **9.4× → 30×**.

### 6. The event

CHN squid jigger `412331147` and TWN squid jigger `416004105`. Northwest Pacific high seas,
1 July 2017, **482 nm from the nearest land**, 6.6 km apart.

- Dark **5 seconds** apart.
- Back on **43 seconds** apart — after **41.8 hours**.
- Only **3** vessels went dark within 200 km and one hour of them. This was not a regional blackout.
  *(Pause here. The five-second number does the work of the whole deck.)*

> Do **not** use the Argentine-grounds pair for this slide even though its numbers look tighter —
> 46 other vessels were dark within 200 km of it, and the first sharp judge will find that.

### 7. Two classes, and we separate them

94% of what the detector finds is **same-flag**: whole squid-jigger fleets with sequential MMSIs going
dark together. That is fleet-coordinated dark time — a real IUU signal, and we report it as its own
category rather than pretending it is a rendezvous.
The 6% that is **cross-flag** is the class that looks like a bilateral transfer. 27 events in three
years, 22.5× over the regional null.
**One vessel appears in seven of them**: `577101000`, Vanuatu flag, 173 shutdowns in three years,
always alongside Taiwanese and Chinese vessels in the same patch of the Northwest Pacific.

### 8. What we do not claim  ← *put this in the deck; do not wait to be asked*

- Candidate events for analyst review. Never confirmed detections.
- The corpus is **fishing vessels only** — no tankers. Our claims are about IUU fishing and
  transshipment. The method transfers to any AIS population; the evidence here does not.
- **Median 12 other vessels are dark within 200 km / 1 h of a candidate.** These are crowded grounds.
  Separating a targeted pair from a busy neighbourhood is the estimator's job, and it is the next
  thing we would build.

### 9. Verification, and why it generalises

Every factual span in the assessment checked against the record it came from: verified / contradicted /
**unverifiable**. The three-state design is the point — an honest "cannot check" is what separates a
tool from theatre.
The rule that matters: **a statistical claim that does not name its null model is unverifiable, not
verified.** No citation-link or confidence-score system catches that.

> *This verifier knows nothing about ships.*

### 10. Detection → coverage → sensing → interdiction

Terrestrial AIS reaches ~40–50 nm. 93% of these gaps also *end* beyond that line — the vessel was
never seen from shore at any point. The 7% that end inshore run **66 hours** dark against a 23-hour
corpus median: long dark transits that terminate at a coast.
That distribution is a sensor-placement problem, computed rather than asserted. What sensing returns
cues interdiction.

---

# PART 2 — SUBMISSION TEXT

### Elevator (one line)

Existing maritime tools detect rendezvous between vessels that are broadcasting. We detect the ones
that aren't — and we publish the chance baseline that says how often we'd be wrong.

### Description (~200 words)

AIS is a cooperative system: vessels broadcast position because they want to be seen. Vessels that do
not want to be seen switch the transponder off. Every commercial maritime-risk platform is built
around the ships that are transmitting.

Dark Rendezvous pairs the absences. Working from Global Fishing Watch's corpus of 55,368 deliberate
AIS disabling events, we identify pairs of vessels that stopped transmitting within minutes of each
other in the same water and resumed within minutes of each other — a two-ended simultaneity signal
that no published tool detects.

The result is calibrated, not asserted. Against a conservative null that permutes event times only
within the same 5° ocean cell — so shared seasons and shared fishing grounds cannot manufacture a
signal — simple co-location runs 2.6× above chance, while two-ended simultaneity runs 30×. Restricted
to cross-flag pairs, the class that resembles a bilateral transfer, 27 events across three years run
22.5× above chance.

An agent narrates each candidate, and every factual span it emits is checked against the source
record and rendered verified, contradicted, or unverifiable — including statistical claims that
fail to name their baseline.

### Tech

Python · pandas · NumPy · scikit-learn (BallTree, haversine) · Streamlit · pydeck · PyArrow ·
Global Fishing Watch AIS disabling corpus (Welch et al. 2022) · GFW Events API · LLM API for narration

### What's next

1. **Local-density conditioning.** A candidate pair sits in a neighbourhood with a median of 12 other
   dark vessels. The next estimator conditions on that neighbourhood rather than on a 5° cell, which
   sharpens the pair signal and rules out regional reception artefacts directly.
2. **Convergent validation against GFW encounter and loitering events.** There is no public
   coordinate-level ground truth for transshipment. There is the next best thing: if a paired dark gap
   is bracketed by a published carrier-loitering event in the same water, that is independent
   corroboration. This is the validation strategy the corpus alone cannot provide.
3. **Live sourcing.** The detector reads through a source interface; the GFW Events API serves GAP
   events for current years behind the same interface.
4. **Coverage → sensing.** Turning the offshore distribution into a sensor-placement recommendation.

### Known limitations (say these first, not last)

Corpus is fishing vessels only (2017–2019); no tankers, so nothing here speaks to sanctioned-oil STS.
No coordinate-resolution ground truth exists, so outputs are candidates for review. 1.5% of records
carry structurally invalid MMSIs and are quarantined. Candidates concentrate in two fishing grounds
and among a small number of repeat vessels — we report that concentration rather than averaging over it.
