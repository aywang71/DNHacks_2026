# Idea 01 — Maritime Dark Rendezvous Detection

**Verdict: BUILD. Strongest of the four candidates.**
**Track:** Defense, or Open.

---

## The idea

Detect ship-to-ship transfers that happen with both vessels' transponders switched off.

Vessels broadcast position over AIS. It is a cooperative system — a ship reports where it is because it wants to be seen, mainly for collision avoidance. That design is also the vulnerability: a vessel that does not want to be observed simply switches the transponder off.

Deliberate AIS disabling is the operational signature of activity that has to happen out of sight — sanctioned oil moving between hulls, catch transferred from illegal fishing vessels to reefers that carry it into legitimate supply chains, smuggling of every kind. The transfer requires two vessels to meet, hold station, and separate, which means it requires *both* to be dark for the same window.

We detect that by pairing the absences: two vessels that stop transmitting within minutes of each other in the same patch of ocean, and resume within minutes of each other.

## The premise

**Everyone else's tool requires the vessels to be broadcasting.** Global Fishing Watch publishes encounter detection and it works well, but it finds the rendezvous nobody was hiding. Commercial platforms — Windward, Spire, Kpler — sell risk scoring built on the same premise plus watchlists. The entire industry is oriented toward vessels that are visible.

Nobody publishes paired dark-gap detection, and nobody publishes a chance baseline for it, which means nobody can say how often that coincidence happens for innocent reasons.

## What we verified

**The data is free, complete, and already downloaded.** Global Fishing Watch publishes a corpus of 55,368 deliberate AIS disabling events covering 5,269 vessels, 2017–2019, as a plain CSV in a public GitHub repo. No token, no signup, 12MB. Coordinates and timestamps on both ends of every gap.

**The core finding has already been reproduced on real data.** Running the pairing against a timestamp-permutation null:

| Threshold | Lift over chance |
|---|---|
| Co-location within 50km / 24h | **1.00×** — literally chance |
| Within 5km / 3h | 1.59× |
| **Both ends match, 5km / 1h** | **5.2×** — 5,538 candidates, 3,417 vessel pairs |
| Both ends match, 2km / 30min | **9.9×** |

Simple co-location is a chance-level detector. The signal is simultaneity at *both* ends. **That is a real result we own before the event starts.**

**Sanity check passed.** Top candidates cluster at 45°S/60°W — the Argentine squid grounds, a known IUU fishing hotspot. Sequential MMSIs in those clusters indicate fleet-level coordinated disabling rather than pairwise transfer, which we plan to detect and report as a distinct category rather than hide.

**A measured sensing gap.** Terrestrial AIS receivers reach roughly 40–50nm offshore. Every event in the corpus begins at ≥50nm. The blind zone is quantified, not asserted — which turns "where would you put sensors" into a computed output rather than a roadmap slide.

## The second component

An agent writes the analyst-facing assessment for each candidate event, and **every factual span in that narrative is checked against the source record** — vessel identifier, timestamps, positions, gap duration, distance. Each span renders as verified, unverifiable, or contradicted. Adversarial mode feeds a degraded record, the agent confabulates, and the verifier catches it live on screen.

This matters because the Defense track description names exactly one specific problem: agent trust for autonomous systems. Most teams will put an LLM on top of something and call the output AI-powered. Demonstrating the failure mode and its mitigation on the same screen is a direct answer to the stated prompt.

The verifier is also domain-general — it knows nothing about ships. Any agent narrating over structured records has this problem, and almost nobody solves it at span granularity.

## Honest weaknesses

**Corpus ends 2019.** Mitigated by building a source abstraction and registering for the GFW API token, so the recency answer is architectural rather than rhetorical.

**No coordinate-level ground truth.** No public dataset of confirmed transfers with positions exists. We claim *candidate events for analyst review*, never confirmed detections, and argue convergent evidence via hotspot concordance.

**Detection is retrospective.** Two-ended matching requires both vessels to come back on, so you learn about the rendezvous after it finished. This is targeting intelligence, not real-time interdiction cueing. The honest bridge: the retrospective corpus is what calibrates the prior for a one-ended real-time detector, which is the version you would actually need operationally.

**US waters are empty.** The Gulf of Mexico has two disabling events in three years. This is a high-seas problem and cannot be framed as a domestic Coast Guard tool.

## Why this wins

It is the only candidate where nothing is mocked, the core finding is already verified, the prior-art gap is clean, and the data is a 12MB download. Both team members have a genuinely hard component that is genuinely theirs — the null calibration is quantitative work, the verifier is agent-systems work, and they proceed in parallel without blocking.

## What would change the verdict

If the corpus turns out to lack coordinates or timestamps on both ends of the gap, the method cannot be reproduced and the project changes shape entirely. **Open the CSV and read the header before committing.** That check takes two minutes and costs nothing.
