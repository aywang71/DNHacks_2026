---
theme: default
title: Wake AI — Making dark shipping visible
info: |
  ## Wake AI
  A Penn-built maritime risk intelligence presentation.
css: ./styles.css
fonts:
  sans: Hanken Grotesk
  mono: JetBrains Mono
transition: fade-out
colorSchema: dark
---

<div class="kicker"><span class="signal"></span> MARITIME RISK INTELLIGENCE</div>

<div class="hero-grid">
  <div>
    <div class="wake-mark"><i></i><i></i><i></i></div>
    <h1>Wake<br><em>AI</em></h1>
    <p class="hero-sub">Making dark shipping<br>visible.</p>
  </div>
  <div class="hero-side">
    <div class="grid-orb"></div>
    <p>From signal gaps<br>to actionable cases.</p>
  </div>
</div>

<div class="footer"><span>PENN BUILT</span><span>SEPT 2026</span></div>

<!--
Open with the simple promise. We make suspicious activity visible without claiming every AIS blackout is wrongdoing.
-->

---
layout: default
---

<div class="kicker">01 / THE PROBLEM</div>
<h2>When a vessel goes dark,<br>the trail goes cold.</h2>

<div class="problem-layout">
  <div class="route-card">
    <div class="route-label">NORMAL AIS TRACK</div>
    <div class="route-line"><b></b><b></b><b class="gap"></b><b class="gap"></b><b class="gap"></b><b></b><b></b></div>
    <div class="route-times"><span>01:20</span><strong>AIS OFF</strong><span>16:45</span></div>
  </div>
  <div class="problem-copy">
    <p>When AIS transmission stops, investigators lose the vessel’s reported position, speed, and heading.</p>
    <p class="muted">A gap is not proof. It is a lead that needs context, coverage, and transparent uncertainty.</p>
  </div>
</div>

<div class="footer"><span>THE INVESTIGATOR SEES A GAP—NOT THE ACTIVITY INSIDE IT.</span><span>02</span></div>

---
layout: default
---

<div class="kicker">02 / THE PROBLEM SPACE</div>
<h2>Dark shipping is<br>measurable at scale.</h2>

<div class="stat-grid">
  <div class="stat accent"><strong>≈&#36;4B</strong><span>gross monthly cargo value<br>at the 2017–23 avg. Brent price</span></div>
  <div class="stat"><strong>558</strong><span>tankers classified as dark,<br>on average each year</span></div>
  <div class="stat"><strong>43%</strong><span>of recorded global seaborne crude<br>exports in the UN Comtrade comparison</span></div>
</div>

<div class="source-strip"><b>7.8M t/mo</b><span>Crude attributed to dark-shipping flows from <em>Iran, Syria, Venezuela, and Russia</em>, 2017–2023.</span></div>
<div class="paper-citation">The dollar lens: 7.8M t/mo × 7.3 bbl/t × &#36;69.43/bbl average Brent = &#36;4.0B/mo (≈&#36;48B/yr). Sources: <a href="https://users.ox.ac.uk/~wadh4073/research_files/Dark_Shipping.pdf">Fernández-Villaverde et al. (2025)</a> · <a href="https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=a&amp;n=pet&amp;s=rbrte">U.S. EIA</a>.</div>
<div class="footer"><span>THE ECONOMIC SCALE OF THE BLIND SPOT</span><span>03</span></div>

---
layout: default
---

<div class="kicker"><span class="signal"></span> 03 / ARCHITECTURE</div>
<h2>Built for evidence,<br>not just alerts.</h2>

<div class="architecture">
  <div><span>01</span><b>Auditable ingestion</b><small>GFW and NOAA retrievals retain raw provenance before normalization.</small></div>
  <div><span>02</span><b>Million-point replay</b><small>Validated hourly Presence data becomes compact daily browser shards.</small></div>
  <div><span>03</span><b>Honest inference</b><small>Observed positions, coverage gaps, and estimated geometry stay distinct.</small></div>
  <div><span>04</span><b>Review-ready queue</b><small>Static scoring batches prioritize leads without fabricating a finding.</small></div>
</div>

<p class="architecture-note">BRONZE PROVENANCE → SILVER NORMALIZATION → STATIC MAP REPLAY → ANALYST REVIEW</p>
<div class="footer"><span>FAST IN THE BROWSER. TRACEABLE BACK TO THE SOURCE.</span><span>04</span></div>

---
layout: default
---

<div class="kicker">04 / LIVE DEMO</div>
<h2>Explore presence,<br>then inspect the queue.</h2>

<div class="demo-grid">
  <div class="demo-map"><div class="map-grid"></div><span class="vessel a">●</span><span class="vessel b">●</span><div class="blackout">AIS GAP<br><b>14h 22m</b></div></div>
  <div class="demo-steps">
    <div><b>01</b><span>Choose a covered day and replay hourly presence</span></div>
    <div><b>02</b><span>Search a vessel and inspect its observed history</span></div>
    <div><b>03</b><span>Open the scored investigation queue</span></div>
    <div><b>04</b><span>Use each result as a review lead—not a finding</span></div>
  </div>
</div>
<div class="footer"><span>LIVE PRODUCT WALKTHROUGH</span><span>05</span></div>
