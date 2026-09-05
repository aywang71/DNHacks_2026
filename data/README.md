# Data

`raw/disabling_events.zip` is the Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), 55,368 events, 2017–2019.
Source: https://github.com/GlobalFishingWatch/AIS-disabling-high-seas (branch `master`, `data/disabling_events.zip`). License CC BY-NC 4.0; attribute GFW in any UI.
`raw/gfw_config.py` is the upstream filter config (12 h min gap, >50 nm from shore at the off end).

```bash
unzip data/raw/disabling_events.zip -d data/raw
python3 -m venv .venv && .venv/bin/pip install pandas numpy pyarrow scipy scikit-learn httpx
```

No pipeline code exists yet; the design is in `plan/build-plan.md` §8. `derived/` is gitignored output. `derived/exclusions.json` is a checkpoint from an earlier loader: 815 invalid MMSIs (1.47%) quarantined.

Note for anyone writing code here: pandas 3 parses these timestamps to `datetime64[us, UTC]`. Use `Timedelta` arithmetic for durations.
