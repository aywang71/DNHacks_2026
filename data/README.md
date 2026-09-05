# Data

`raw/disabling_events.zip` is the Global Fishing Watch AIS-disabling corpus (Welch et al. 2022), 55,368 events, 2017–2019.
Source: https://github.com/GlobalFishingWatch/AIS-disabling-high-seas (branch `master`, `data/disabling_events.zip`).
`raw/gfw_config.py` is the upstream filter config (12 h min gap, >50 nm from shore at the off end).

To reproduce locally:

```bash
unzip data/raw/disabling_events.zip -d data/raw
python3 -m venv .venv && .venv/bin/pip install pandas numpy pyarrow scikit-learn scipy
.venv/bin/python -m pipeline.load      # writes data/derived/gap_events.parquet + exclusions.json
```

`derived/exclusions.json` is committed as a checkpoint: 815 invalid MMSIs (1.47%) quarantined, matching the 31 Aug feasibility run.
