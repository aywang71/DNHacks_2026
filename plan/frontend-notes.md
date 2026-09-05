# Frontend notes (handed to the UI owner; not part of the backend plan)

The backend emits `data/derived/candidates.json` in the contract defined in `build-plan.md` §8. Everything below is reference material for building the analyst view on top of it.

## Skylight visual reference
Screenshots and explainer illustrations are in `tmp/skylight-ref/` (files 01–09). The paper's Figure 1c mechanism diagram, which is the per-candidate map drawing to emulate, is at `tmp/pdfs/dark-page-11.png`.

Elements worth emulating, most specific first:
1. Full-bleed map; all UI floats in overlay panels.
2. Detail views open as floating cards anchored at the map location, teal header, minimize/close.
3. Card body is a two-column label/value grid.
4. Dashed vs solid segments distinguish AIS-gap stretches from normal reporting; a distinct marker for last known position.
5. Icon convention: black = corroborated by AIS, red = uncorroborated or inferred. Use filled dots for AIS endpoints, hollow red for the inferred meeting point and projected paths.
6. "Vessels in the vicinity" nested list inside the card: flag, name, MMSI.
7. Event-history count on the card ("9 prior events").
8. Thumbs up/down plus comment box; this writes the `analyst_disposition` field the backend wants back.
9. Light, low-saturation basemap (CARTO Positron needs no key). Dark Matter is the alternative.
10. Semi-transparent polygons for areas of interest: EEZ and RFMO boundaries.

Palette approximations from Skylight: navy `#1B2A55`, teal `#2B98A0`, water `#AFE0E3`, land `#E8E8E8`, alert red `#EE4B5B`. Do not use the Skylight wordmark or imply affiliation.

## Stack findings
deck.gl + MapLibre with the CARTO basemap gave the best polish per hour in our survey; a single HTML file over CDN scripts and precomputed JSON is the most robust demo artifact. Leaflet with CARTO raster tiles is the safe fallback. GFW's open frontend is MIT but welded to their API config model; use it as a visual reference only.

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
