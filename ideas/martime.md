# Maritime Dark Rendezvous — Pre-event feasibility results

**Run 31 Aug 2026 (T−5).** Full write-up with the corrected lift table and leads:
artifact "Dark Rendezvous Feasibility"
(https://claude.ai/code/artifact/86963864-40f8-4d9d-b2cf-ed6ebd38847e)

## Verdict: BUILD — thesis revised

Corpus, access and structure all check out. The Part III numbers do not reproduce, and two
load-bearing pitch claims cannot be made from this data.

## Headline: the Part III lift table is wrong

Pairing logic validated against exhaustive brute force on a 1,500-event subsample at four
threshold settings — exact match on all four. Three nulls: **A** = global timestamp
permutation (duration preserved); **C** = permutation *within 5° ocean cell*, so shared
season and shared fishing ground cannot manufacture lift. C is the honest column.

| threshold                          | observed      | null A | lift A | null C | **lift C** | vessels | top-5 share |
| ---------------------------------- | ------------- | ------ | ------ | ------ | ---------------- | ------- | ----------- |
| start · 50 km / 24 h              | 125,878       | 14,904 | 8.4×  | 47,915 | **2.6×**  | 2,154   | 6%          |
| start · 5 km / 1 h                | 1,240         | 25     | 50×   | 132    | **9.4×**  | 435     | 15%         |
| both ends · 25 km / 3 h           | 5,659         | 74     | 76×   | 389    | **14.5×** | 616     | 12%         |
| **both ends · 10 km / 1 h** | **437** | 1.9    | 230×  | 12.4   | **35.2×** | 216     | 28%         |
| both ends · 5 km / 1 h            | 105           | 0.4    | 263×  | 3.5    | **30.0×** | 77      | 40%         |
| both ends · 2 km / 30 min         | 5             | 0.0    | —     | 0.0    | —               | 8       | 70%         |

**"Simple co-location is a chance-level detector — 1.00×" does not reproduce.** It is 8.4×
(global null) / 2.6× (within-region null). A lift of exactly 1.00 is the signature of a null
that isn't doing anything — the same time-unit bug that appeared in the first reproduction
attempt here. Part III's 5,538 candidates at "both ends 5 km / 1 h" matches *start-only
5 km / 24 h* (5,600) and *both-ends 25 km / 3 h* (5,659) — the figure lands on a different
cell of the grid than its label.

**Operate at both ends, 10 km / 1 h.** Below ~100 candidates the null mean itself goes noisy.

## Three things that must change in the pitch

1. **Kill the 1.00× slide** and the "everyone else's proximity detector is a coin flip" line.
   Replace with the lift ladder across the grid, shown against null C.
2. **No tankers in this corpus.** All five vessel classes are fishing gear types
   (`drifting_longlines, squid_jigger, tuna_purse_seines, trawlers, other`); the repo is
   *Hotspots of unseen fishing vessels* and draws from a fishing-vessel table. The
   sanctioned-oil / STS framing in Part I has no support. Lead IUU fishing + transshipment.
3. **Clique detection is load-bearing, not MAJOR 5.** 94% of candidates are same-flag, 58%
   sequential-MMSI (one fleet). Without clique detection the detector's own output
   contradicts the rendezvous story.

## The finding that replaces it: cross-flag

Same-flag conditioning adds nothing (96% observed vs 97% chance — the grounds are simply
fleet-dominated). **Cross-flag conditioning adds a lot: 27 observed vs 1.2 expected = 22.5×**
at both-ends 10 km / 1 h. Cross-flag is the class that resembles a bilateral transfer.

Repeat participant: **`577101000`, Vanuatu flag, squid jigger, 173 disabling events in three
years, in 7 of the 27 cross-flag candidates**, always alongside CHN/TWN vessels in the same
patch of the NW Pacific.

**Demo event — use this one:** CHN `412331147` + TWN `416004105`, 2017-07-01, 42.7N 162.0E,
**482 nm offshore**, 6.6 km apart. Dark **5 seconds** apart, back **43 seconds** apart, after
41.8 h. Only **3** vessels dark within 200 km / ±1 h.
*Do not use* the Argentine pair (412271470/416527000) despite tighter numbers — **46** other
vessels were dark within 200 km of it.

## The attack that lands

A satellite reception hole produces exactly this signature. Median **12** other vessels are
dark within 200 km / ±1 h of a cross-flag candidate; only 2 of 27 sit in a quiet neighbourhood.
The 5° null is too coarse to settle it. **Build local-density conditioning** — given *n*
vessels dark in the neighbourhood, how surprising is *this* pair matching at both ends? Best
hour of work in the build; do it instead of the map.

## Checklist answers

| Item                        | Answer                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Both ends present?          | **Yes.** Zero nulls on all 7 pairing-critical columns. 55,368 events, 5,269 vessels, 2017-01-01→2019-12-31.                                                                                                                                                                                                                                                                                                                                                        |
| Distance-to-shore a column? | **Yes, at both ends, in metres. Delete "source a coastline shapefile."** Quantised to whole km → verifier tolerance ≥ ±1000 m.                                                                                                                                                                                                                                                                                                                                   |
| >50 nm filter               | Applies to the**start only**. Min start distance 93 km. **3,948 gaps (7.1%) end inside 50 nm**, 1,143 inside 10 nm; those run 66.3 h median vs 23.5 h corpus-wide.                                                                                                                                                                                                                                                                                            |
| Coverage claim              | "Every event is where terrestrial AIS can't see" is**circular** — it's the corpus definition. Non-circular version: 93% also *end* beyond 50 nm.                                                                                                                                                                                                                                                                                                                 |
| Temporal density            | 86.7% of consecutive events within 1 h; mean spacing 28.5 min.**BallTree probably unnecessary** — windowed vectorised haversine is simpler.                                                                                                                                                                                                                                                                                                                        |
| Schema extras               | `vessel_class` (5, zero null), `flag` (702 blank = 1.3%), `vessel_length_m`, `vessel_tonnage_gt`, `gap_hours`.                                                                                                                                                                                                                                                                                                                                                  |
| Verifier traps              | Length/tonnage are**model estimates** (15 dp) — don't badge green without saying "estimated". `gap_hours` is **rounded to the minute**: 53,978/55,368 rows differ from the exact difference by >1 s → duration tolerance ±0.017 h or it reds out on 97% of records. **815 events (1.5%) have invalid MMSIs** (168 non-9-digit, 647 MID outside 201–775, incl. AtoN/SART ranges) → quarantine in pairing, surface one as a free `unverifiable`. |
| Download                    | `raw.githubusercontent.com/GlobalFishingWatch/AIS-disabling-high-seas/**master**/data/disabling_events.zip` (4.3 MB zip / 11.9 MB CSV) and `…/master/**ais_disabling**/config.py`. Branch is master, config is not at repo root.                                                                                                                                                                                                                                     |
| Thresholds (confirmed)      | 12 h min gap · >50 nm at off end · >10 positions/day · ≥14 positions in prior 12 h.                                                                                                                                                                                                                                                                                                                                                                                   |
| GFW token                   | **Latency still unconfirmed — register today.** Docs say "request a token" but also "max five tokens per user", which reads self-service; portal is JS-rendered.                                                                                                                                                                                                                                                                                                   |
| Token value                 | **Upgraded.** Events API serves `GAP` **and** `ENCOUNTER` **and** `LOITERING`. That's a convergent-validation set — a paired dark gap bracketed by a published carrier-loitering event is independent corroboration. Better answer to "where's your ground truth" than hotspot concordance.                                                                                                                                                      |
| Environment                 | pandas 3.0 / numpy 2.4 / sklearn 1.8 / pyarrow 25 all import. Andrew must still verify streamlit + pydeck on Windows.                                                                                                                                                                                                                                                                                                                                                     |

## Plan deltas

- **Delete:** coastline shapefile; the 1.00× slide.
- **Rewrite:** Part I opening (no tankers).
- **Promote to MAJOR 2:** clique/connected-component detection; the cross-flag cut (one boolean).
- **Add to MAJOR 3:** local-density conditioning.
- **Demote further:** the pydeck map. Two clusters, 27 events — no globe needed.
- **Keep:** the MAJOR 4 rule, the DataSource abstraction, caching discipline, fallback ladder,
  Saturday-night screen recording.

## Artifacts drafted (Part XI non-code prep, done)

`verifier-contract.md` — claim schema, 20 claim types in 3 validator classes, tolerances derived
from measured properties of the corpus, 8 `unverifiable` reason codes, and the rule that makes it
a Defense project: *a statistical claim that does not name its null model is unverifiable, not
verified.*
`agent-prompt.md` — system prompt, user template, adversarial harness (corrupt the record, never
the prompt).
`fixtures.json` — real-schema fixture event and pair, 4 corruptions, 1 naturally-invalid MMSI pair.
`deck-and-submission.md` — 10-slide outline + submission description / tech / what's-next /
limitations.

## Track read

The detector is now the stronger half again — a corrected calibration table with three nulls, a
rare cross-flag class, and named repeat vessels. The verifier is still paper, same as procurement.
Maritime's advantage over procurement is the demo (a five-second simultaneous shutdown 482 nm
offshore beats a bunching histogram in a booth); procurement's advantage is that its result has no
equivalent of the reception confound. **Defense** if the verifier comes together; **Open** if it
doesn't.
