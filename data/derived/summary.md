# GapPair export summary

## Judge-facing numbers

- Corpus: 55,368 deliberate disabling events, 5,269 vessels, 101 flags, 2017, 2018, 2019; fishing vessels only.
- Operating rule: both endpoints within 10 km and 1 h with overlapping gaps: 434 candidates.
- Null: within-cell permutation (200 draws), mean 13.19, lift 32.92×.
- Ladder: both ends 10 km / 1 h: 434; both ends 2 km / 30 min: 3; both ends 25 km / 3 h: 5630; both ends 5 km / 1 h: 103; loose: 18775; start-only 5 km / 1 h: 1230; start-only 50 km / 24 h: 101901.
- Loose rule: 18,775 pairs; feasibility retained not available.
- Structure: 237 bilateral; 173 sequential-MMSI; 183 identity twins; 26 cross-flag; 16 zero-neighbour.
- Kinematics: median required speed 0.66 kn; median plausibility 0.95.
- Showcase: 0.083 min / 6.6 km at shutoff, 0.717 min / 8.99 km at reappearance, 41.76 h overlap, 892.0 km offshore, 1 neighbour(s), p_cell 0.005.

## Honest limits

- Fishing vessels only; no coordinate-level ground truth establishes a transfer.
- Meeting points and reachable sets are inferred heuristics, never observed AIS positions.
- Detection is retrospective because both gaps must close; AIS gaps can also reflect reception conditions.
- The score is an analyst-priority aid, not a probability of wrongdoing.
- WCPFC reported that 78% of 77 AIS-only transshipment candidates were unsubstantiated after triangulation.

Attribution: Data: Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), CC BY-NC 4.0
