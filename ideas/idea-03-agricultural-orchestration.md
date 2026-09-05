# Idea 03 — Agricultural Data Orchestration

**Verdict: DROP for this event. Good business, wrong format.**
**Track it would have targeted:** Energy & Industrialization.

---

## The idea

Fuse satellite imagery, soil data, weather, and farm equipment telemetry into a single operational picture of a farm — a mid-season anomaly triage queue that tells an agronomist which fields need attention this week.

The richer version, and the one that motivated the idea: a forward-deployed engineer goes on site, integrates a grower's existing equipment and sensor systems, and builds a comprehensive view they could not assemble themselves. That is the Palantir model pointed at agriculture, and it is a real business.

## The premise

The scarce resource in farming is **attention**. An agronomist covers thousands of acres and can physically scout a handful of fields a week. USDA county yield estimates for a season can land seven months after harvest — long after any intervention was possible. Satellite signal is available weekly, in season, while there is still time to act.

The sharpest framing we developed: *"Is this field in trouble, or is my equipment lying to me?"* Score every field against three baselines — its own prior seasons, same-crop neighbours this season, and what its soil class and accumulated growing degree days would predict. Output a ranked queue with an explicit alert budget: we surface the top N fields per week, tuned to a stated false-positive rate. Then overlay equipment telemetry to separate crop stress from machine failure — a skipped planter row, a boom section that never switched on, a plugged nozzle. From orbit these look identical to drought stress; on the ground they mean completely different actions.

## What we verified — the data is better than expected

**A hosted, no-raster satellite path exists.** Google Earth Engine's free Community tier hosts Sentinel-2, gives cloud masking as a three-line join against Cloud Score+, and returns numbers rather than image tiles. Access is enabled immediately on registration with no billing account and no approval cycle.

**Field boundaries are solved.** USDA's Crop Sequence Boundaries dataset provides roughly 16.4 million field polygons for the continental US, public domain, with crop history attributes attached. No manual boundary drawing.

**The synthetic equipment layer is credible.** The ADAPT framework is genuinely open source and MIT-licensed, and the ISOBUS data dictionary publishes every telemetry field with its units and resolution publicly. Synthetic telemetry conforming to a real published schema is defensible in a way invented fields are not.

**It passes the synthesis test.** If you synthesize the equipment data, you do *not* synthesize the answer — the anomaly flag comes from real imagery, real soil, real weather. The mock only routes the response.

So on the merits the investigation came back positive.

## Why we are dropping it anyway

**The no-precoding rule removes the load-bearing prep.**

The plan's viability rested on precomputing a per-field vegetation index cache — several hundred fields across three seasons, cloud-masked, composited, written to local storage before the event. Every credible version of this project assumed that cache existed on Saturday morning.

That is now prohibited. What remains for the weekend:

- cold Earth Engine authentication for two people
- hundreds of live field-season queries against a compute quota nobody has benchmarked
- writing a synthetic telemetry generator with several scripted failure archetypes
- building the anomaly scoring against three separate baselines
- the interface

For a team with **no geospatial experience**, in 26 hours, with no code written in advance. The strong data-science background helps considerably once data is in a dataframe and not at all with raster wrangling, projections, or quota management.

**There is also a structural mismatch.** In a forward-deployed integration business, the integration *is* the product — and integration is precisely the thing that cannot be demonstrated in a weekend. We would be showing the weakest possible proxy for the actual thesis: one county, synthetic equipment data, a dashboard. The moat in that business is OEM partnership access, not code, and John Deere and Climate FieldView already hold it.

**Prior art is mature.** "Predict county yield from satellite imagery" is one of the most saturated categories on GitHub. The holistic-operational-picture framing loses to Climate FieldView in the first thirty seconds of judge questioning.

## What would change the verdict

Allowing precomputation. If the cache could be built in advance, this becomes a genuinely strong Energy-track project with real data, a defensible synthetic layer, and a striking visual demo.

It cannot, so it does not.

**Keep the idea.** It is a better company than it is a hackathon project, and that is not a criticism of the idea.
