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
    <p>Vessels can disable AIS—the system that broadcasts their location, speed, and heading.</p>
    <p class="muted">That blackout can hide sanctioned oil movements and ship-to-ship cargo transfers.</p>
  </div>
</div>

<div class="footer"><span>THE INVESTIGATOR SEES A GAP—NOT THE ACTIVITY INSIDE IT.</span><span>02</span></div>

---
layout: default
---

<div class="kicker">02 / THE SIZE OF THE BLIND SPOT</div>
<h2>Not a fringe problem.</h2>

<div class="stat-grid">
  <div class="stat"><strong>558</strong><span>average suspected<br>dark tankers</span></div>
  <div class="stat"><strong>~25%</strong><span>of the global crude<br>tanker fleet</span></div>
  <div class="stat accent"><strong>7.8M</strong><span>metric tons of crude<br>moved per month</span></div>
</div>

<div class="source-strip"><b>43%</b><span>of <em>officially recorded</em> global seaborne crude exports in the study comparison</span></div>
<div class="footer"><span>OXFORD / PENN RESEARCH · 2017–2023 ESTIMATES</span><span>03</span></div>

<!--
The 43% comparison is to officially recorded exports. The paper estimates potential volume using qualifying vessel capacity; present the figure as an estimate.
-->

---
layout: default
---

<div class="kicker">03 / WHY THE STATUS QUO BREAKS</div>
<h2>One signal is never<br>enough.</h2>

<div class="signals">
  <div><span class="icon">⌁</span><b>AIS gaps</b><small>When & where a vessel disappears</small></div>
  <div><span class="icon">⌖</span><b>Geography</b><small>Risky routes & sanctioned-port proximity</small></div>
  <div><span class="icon">↝</span><b>Behavior</b><small>Speed, heading & voyage anomalies</small></div>
  <div><span class="icon">⟷</span><b>Proximity</b><small>Potential ship-to-ship transfers</small></div>
</div>

<p class="claim"><span>KEY PRINCIPLE</span> An AIS gap is not proof. Context turns a gap into a lead.</p>
<div class="footer"><span>FRAGMENTED SIGNALS → EXPLAINABLE RISK</span><span>04</span></div>

---
layout: default
---

<div class="kicker"><span class="signal"></span> 04 / THE PRODUCT</div>
<h2>Wake AI finds the<br>signals worth waking up to.</h2>

<div class="pipeline">
  <div class="pipe-input"><span>AIS</span><span>VESSEL</span><span>ROUTE</span></div>
  <div class="pipe-line"></div>
  <div class="ai-core">WAKE<br><b>AI</b></div>
  <div class="pipe-line"></div>
  <div class="case-card"><small>PRIORITY CASE</small><b>Suspicious dark gap</b><span>Evidence · route · risk</span></div>
</div>

<div class="feature-row"><span>DETECT</span><span>CONNECT</span><span>EXPLAIN</span><span>PRIORITIZE</span></div>
<div class="footer"><span>FROM RAW SIGNALS TO INVESTIGATOR-READY CASES</span><span>05</span></div>

---
layout: default
---

<div class="kicker">05 / LIVE DEMO</div>
<h2>Watch a blackout<br>become a case.</h2>

<div class="demo-grid">
  <div class="demo-map"><div class="map-grid"></div><span class="vessel a">●</span><span class="vessel b">●</span><div class="blackout">AIS GAP<br><b>14h 22m</b></div></div>
  <div class="demo-steps">
    <div><b>01</b><span>Normal voyage begins</span></div>
    <div><b>02</b><span>AIS signal disappears</span></div>
    <div><b>03</b><span>Wake AI finds correlated risk signals</span></div>
    <div><b>04</b><span>Analyst receives the evidence-backed case</span></div>
  </div>
</div>
<div class="footer"><span>LIVE PRODUCT WALKTHROUGH</span><span>06</span></div>

---
layout: default
---

<div class="kicker">06 / ARCHITECTURE</div>
<h2>How Wake AI works.</h2>

<div class="architecture">
  <div><span>01</span><b>Data ingestion</b><small>AIS + vessel + geospatial data</small></div>
  <div><span>02</span><b>Event engine</b><small>Gaps, routes, and proximity</small></div>
  <div><span>03</span><b>Risk model</b><small>Signals become explainable scores</small></div>
  <div><span>04</span><b>Analyst workflow</b><small>Alerts, cases, and evidence</small></div>
</div>

<p class="architecture-note">DETAIL TO BE ADDED: data sources, model logic, and analyst interface.</p>
<div class="footer"><span>ARCHITECTURE BREAKDOWN</span><span>07</span></div>

---
layout: default
class: sources-slide
---

<div class="kicker">07 / RESEARCH SOURCES</div>
<h2>Read the research<br>behind Wake AI.</h2>

<div class="sources-list">
  <a class="source-card" href="https://ora.ox.ac.uk/bookmarks/uuid%3Af1ae5ac6-f011-415b-be03-fa2f210829a3">
    <span>01</span>
    <div><b>Charting the Uncharted</b><small>Fernández-Villaverde, Li, Xu &amp; Zanetti · Oxford Discussion Paper 1070 · 2025</small></div>
    <i>OPEN PAPER ↗</i>
  </a>
  <a class="source-card" href="https://pmc.ncbi.nlm.nih.gov/articles/PMC9629714/">
    <span>02</span>
    <div><b>Hot Spots of Unseen Fishing Vessels</b><small>Welch et al. · Science Advances 8, eabq2109 · 2022</small></div>
    <i>OPEN PAPER ↗</i>
  </a>
  <a class="source-card" href="https://doi.org/10.3389/fmars.2018.00240">
    <span>03</span>
    <div><b>Identifying Global Patterns of Transshipment Behavior</b><small>Miller et al. · Frontiers in Marine Science 5:240 · 2018</small></div>
    <i>OPEN PAPER ↗</i>
  </a>
</div>

<div class="footer"><span>DIRECT LINKS TO ORIGINAL PAPERS</span><span>08</span></div>

---
layout: center
class: closing
---

<div class="kicker"><span class="signal"></span> WAKE AI</div>
<h1>When ships go dark,<br><em>risk should not.</em></h1>
<p>Make maritime activity visible, explainable, and actionable.</p>
<div class="closing-line"></div>
<div class="research-credit">BUILT BY A PENN TEAM · INSPIRED BY DARK-SHIPPING RESEARCH COAUTHORED BY PENN PROFESSOR JESÚS FERNÁNDEZ-VILLAVERDE</div>

<!--
Research reference: Fernández-Villaverde, Li, Xu & Zanetti (2025), Charting the Uncharted: The (Un)Intended Consequences of Oil Sanctions and Dark Shipping. Oxford Department of Economics Discussion Paper 1070.
-->
