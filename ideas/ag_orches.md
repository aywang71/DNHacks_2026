
# Investigation Brief 04 — Agricultural Data Orchestration

**DNHacks 2026 · Energy & Industrialization · assessed 23 Aug 2026**

Full formatted version: https://claude.ai/code/artifact/0d134e83-4054-4001-ae61-89a08e533e2b

## 1. Verdict — BUILD REDUCED

The hosted, no-raster satellite path exists and is better than the brief assumed. Google Earth Engine's free Community tier hosts Sentinel-2, a one-line cloud mask (Cloud Score+), the USDA Cropland Data Layer, **and** USDA's own field-boundary polygons as feature collections — all reachable from Python calls that return numbers, not tiles. Access is enabled immediately on registration; no approval cycle. Nobody touches a projection or a cloud mask all weekend.

The reduction is about the claim, not the data. "Holistic operational picture" loses to Climate FieldView in the first 30 seconds of Q&A; "predict county yield from NDVI" is one of the most saturated categories on GitHub (dozens of repos, CropNet at KDD 2024, a formal sub-national benchmark). Narrow to a **mid-season anomaly triage queue with a stated false-positive budget**, where the synthetic equipment layer explains *why* a field flagged rather than *whether* it flagged.

## 2. The friction finding

**Yes — a hosted, no-raster path exists. Three of them.**

- **Recommended: Google Earth Engine, Community tier.** Registration creates a Cloud project, enables the EE API, runs a noncommercial eligibility questionnaire; Google's docs state access is enabled *immediately after registration*, no billing account. 150 EECU-hours/month, resetting on the 1st; exceeding it degrades performance rather than cutting access. `reduceRegion`/`getRegion` over a field polygon return numbers straight into a dataframe. Cloud masking is a join against `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` and a threshold — three lines, not a Saturday. Same catalog carries `USDA/NASS/CDL` and the CSB field polygons (`projects/nass-csb/assets/csb1623/…`, community mirror `projects/sat-io/open-datasets/USDA/CSB_1623`). Imagery, crop label, and geometry never leave one system.
- **Backup: Sentinel Hub Statistical API via Copernicus Data Space.** Pure REST — post a geometry and date range, get JSON stats per interval. Free registered users: 10,000 processing units and 10,000 requests/month, 300 req/min.
- **Do not use: Microsoft Planetary Computer.** STAC API is live and anonymous (verified today), but it hands you cloud-optimized GeoTIFFs. That *is* the raster path.

**Latency: unverified.** Could not benchmark from here. Treat the demo as cache-first regardless — precompute to Parquet in prep, keep one live query behind a button.

## 3. Verified data access

| Source                                    | Status                                   | Access & granularity                                                                                                                                                                                                                                                                                                                                                                                                    | Difficulty                                                          |
| ----------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Sentinel-2 via Earth Engine               | Confirmed                                | Free noncommercial Community tier, 150 EECU-h/mo, immediate. Cloud project + questionnaire. 10 m, ~5-day revisit, 2015–present.                                                                                                                                                                                                                                                                                        | Easy once auth clears                                               |
| Cloud Score+ mask                         | Confirmed                                | Per-pixel cloud/shadow band joined by image ID. Removes cloud masking as a risk.                                                                                                                                                                                                                                                                                                                                        | Easy                                                                |
| USDA Cropland Data Layer                  | Confirmed —**query API exists**   | CropScape exposes`GetCDLStat`, `GetCDLValue`, `GetCDLComp` by FIPS/bbox/polygon/point; live call for FIPS 17019 / 2023 returned a cached JSON URL. Also a GEE image collection. 30 m, 2008–present at that resolution.                                                                                                                                                                                           | Easy                                                                |
| Crop Sequence Boundaries (field polygons) | Confirmed                                | **Answers the boundary question — no manual drawing.** ~16.4M CONUS polygons, 8-year rolling windows, latest 2018–2025 released 27 Mar 2026, public domain. Attributes: `CSBID`, `CSBACRES`, `CDL2017`–`CDL2024`, state/county FIPS, ASD. Three routes: GDB download, ArcGIS FeatureServer with spatial query + GeoJSON export (verified responding, maxRecordCount 2000), or GEE feature collections. | Easy                                                                |
| NASS Quick Stats                          | Confirmed, with caveat                   | Free key, JSON/CSV/XML, 50,000-record cap/query, county yields with decades of history.**Caveat:** county estimates discontinued in the 2024 budget squeeze, reinstated by FY2025 appropriations Mar 2025; 2024 county corn/soy yields did not publish until May 2025.                                                                                                                                            | Easy                                                                |
| SSURGO via Soil Data Access               | Confirmed                                | No auth. POST SQL → JSON, 100,000-row cap, spatial queries by point/polygon in WKT/GeoJSON. Map-unit resolution.                                                                                                                                                                                                                                                                                                       | Moderate — the mapunit/component/horizon join is ugly. Precompute. |
| Weather (historical)                      | Confirmed                                | Open-Meteo archive (ERA5/ERA5-Land, hourly 1940–present, no key non-commercial) is fastest to GDD/precip. Daymet Single Pixel (1 km daily CONUS CSV) and NASA POWER equivalent.                                                                                                                                                                                                                                        | Easy                                                                |
| NOAA/NWS api.weather.gov                  | Confirmed, wrong tool                    | Free, no key — but forecasts and current observations only.**No historical time-series endpoint.**                                                                                                                                                                                                                                                                                                               | Easy                                                                |
| OpenET                                    | Free, approval time unknown              | Key required, free. Field-boundary/multipolygon timeseries. Monthly ET 2000–present, daily 2016–present; provisional monthly lands 5th–6th of following month. Limits: 50,000 acres/request, 50 polygons/shapefile query, 100 field IDs/query.                                                                                                                                                                       | Moderate — register in prep                                        |
| RMA Cause of Loss / Summary of Business   | Confirmed                                | Public bulk files by state/county/crop/cause with indemnity dollars. No API but small and static.                                                                                                                                                                                                                                                                                                                       | Easy                                                                |
| ORNL MODIS/VIIRS subsets REST             | **Unverified — 500 errors today** | Documented as no-key REST returning JSON/CSV NDVI/EVI subsets. Both live calls today returned HTTP 500. Retest before relying on it.                                                                                                                                                                                                                                                                                    | n/a                                                                 |

## 4. Synthetic layer assessment — credible

**ADAPT is real and open.** `github.com/ADAPT`: ADAPT Standard (MIT, updated Jan 2026), ISOv4Plugin for ISOXML (EPL-1.0, Jun 2026), StandardPlugin (MIT, Jun 2026), ADAPT-Visualizer. The public wiki documents the object model: `Document`/`WorkOrder` with grower/farm/field IDs, `LoggedData`, `OperationData`, `SpatialRecord`, `Representation`, `ContextItem`, `TimeScope`.

**ISOBUS is real and granular.** ISO 11783-11 data dictionary at isobus.net, complete text export (snapshot 2026050501), each entry carrying DDI number, name, definition, unit, resolution, CAN bus range, display range, typical device classes. DDI 1 = Setpoint Volume Per Area Application Rate [mm³/m²] at 0.01 resolution; DDI 51 = setpoint tillage depth [mm].

**Two constraints.** The ADAPT toolkit is C#/.NET — do not try to run it in a Python demo; use the schema and DDI export as a *specification* and generate the data yourself. The ISO standard document is paywalled; the DDI dictionary is not — cite the dictionary.

**Verdict:** a practitioner will accept DDI-keyed as-applied logs with correct units, provided they are labelled synthetic on screen and the demo's conclusion does not rest on them.

## 5. Recommended framing

**"Is this field in trouble, or is my equipment lying to me?"**

For every field polygon in *one county*, pull a Sentinel-2 vegetation-index time series through Earth Engine with Cloud Score+ masking, and score each field against three baselines: its own prior seasons, same-crop neighbours this season, and what its soil capability class and accumulated GDD would predict. Output a ranked queue with an **explicit alert budget** — "we surface the top N fields per week, tuned to a stated false-positive rate." That budget is the part almost no commercial ag dashboard states honestly, and it is exactly Person A's wheelhouse.

The synthetic ADAPT/ISOXML layer does one job: **explanation, not detection.** When a field flags, overlay as-applied planting rate, sprayer section control, and harvest logs to separate crop stress from machine failure — a skipped planter row, a boom section that never switched on, a plugged nozzle. From orbit these look identical to drought stress; on the ground they mean different actions. The decision is three-way: **scout it, fix the machine, or ignore it.**

This passes the brief's own test: if you synthesize the equipment data, you do *not* synthesize the answer. The flag comes from real imagery, real soil, real weather; the mock only routes the response.

**Stakes.** The scarce resource is attention — an agronomist covers thousands of acres and can scout a handful of fields a week. NASS county yields for 2024 did not publish until May 2025, roughly seven months after harvest; satellite signal is available weekly, in season, while intervention is still possible. RMA cause-of-loss files give the dollar frame by county and cause.

## 6. Kill criteria status

- **No hosted satellite path** — refuted. GEE Community tier + Cloud Score+; Sentinel Hub as second option.
- **Schemas not publicly documented** — refuted. ADAPT is MIT/EPL open source; ISOBUS DDI dictionary publishes units and resolutions publicly.
- **Mostly-synthetic dashboard** — *conditional.* Avoided only under the recommended framing. If the equipment mock ever becomes the thing that *detects* rather than explains, this trips and the project should be dropped mid-build.
- **No articulable decision** — refuted. Scout / repair / ignore, with a stated weekly alert budget.

## 7. Pre-hackathon prep list (in order)

1. **Register Earth Engine on personal Google accounts.** Cloud project, enable API, noncommercial questionnaire, then confirm `ee.Initialize()` runs from a clean virtualenv on both laptops. Personal accounts — an employer domain in the eligibility form is the one thing that could stall an otherwise immediate approval.
2. **Collect remaining credentials.** NASS Quick Stats key; Copernicus Data Space account with OAuth client ID/secret as imagery fallback; OpenET key if ET makes the cut. One successful test call against each.
3. **Pick the county and freeze the field set.** High-variance corn/soy county in IL or IA. Pull CSB polygons, filter to corn/soy above ~40 acres, cap at 200–500 fields. Freeze the list.
4. **Precompute the vegetation index cache.** Per-field NDVI (and NDRE if it earns its keep) for the current season plus 2–3 prior, Cloud Score+ masked, 10-day composites, written to Parquet. Measure EECU burn while doing it.
5. **Precompute soil and weather per field.** One SDA query per field; daily Open-Meteo history rolled to GDD and precip accumulations.
6. **Pull context and validation data.** NASS county yield history and RMA cause-of-loss for the chosen county.
7. **Write the synthetic telemetry generator.** Download the isobus.net DDI export, skim the ADAPT Standard schema, build the generator with 3–4 scripted failure archetypes — planter row skip, sprayer section drop-out, nozzle plug, harvest calibration drift — each producing a spatial signature a satellite anomaly could plausibly match.
8. **Build cache-first, demo-safe.** Every screen reads from local cache; no live API call on the critical path. Wire exactly one live GEE query behind a visible button.

## 8. Open risks

- **Earth Engine latency and quota burn** — no remote benchmark possible. 150 EECU-hours is generous but finite; a 300-field × 3-season pull is untested. Measure in prep.
- **ORNL MODIS/VIIRS REST returned 500 on both attempts today** — may be transient. Retest before treating as a fallback.
- **OpenET key approval time is undocumented.**
- **Statistical API on the free Copernicus tier** — quota page confirms free-user Sentinel Hub quotas generally and names only Batch Processing V2 as excluded, but no line explicitly confirms Statistical API inclusion. One test call settles it.
- **CSB polygons are derived, not authoritative** — inferred from CDL sequences, not FSA Common Land Unit records; sub-hectare polygons dropped. Say this in the demo before a judge does.
- **Current-season imagery gaps** — Midwest cloud cover plus Sentinel-2 revisit can leave holes in a masked composite this late in the season. Check the chosen county's coverage in prep.
- **2025 county yield publication status** for the chosen county not verified.
