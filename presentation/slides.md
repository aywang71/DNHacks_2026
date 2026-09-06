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

<div class="footer"><span>SEPT 2026</span><span></span></div>

---
layout: default
class: unified-type
---

<div class="kicker">01 / THE PROBLEM</div>
<h2>When a vessel goes dark,<br>the trail goes cold.</h2>

<div class="problem-layout">
  <div class="route-card">
    <div class="route-label">NORMAL AIS TRACK</div>
    <div class="route-line"><b></b><b></b><b class="gap"></b><b class="gap"></b><b class="gap"></b><b class="gap"></b><b class="gap"></b><b class="gap"></b><b></b><b></b></div>
    <div class="route-times"><span>01:20</span><strong>AIS OFF</strong><span>16:45</span></div>
  </div>
  <div class="problem-copy" style="font-size:20px;line-height:1.15">
    <p style="margin:0 0 14px">Automatic Identification System (AIS) tracks a vessel's location, speed, and bearing to avoid collisions.</p>
    <p style="margin:0 0 14px">However, AIS can be faulty in poor conditions or when a vessel disables it.</p>
    <p class="muted" style="margin:0">These AIS blackouts can hide ship-to-ship transfers, illegal fishing, and sanctions evasion.</p>
  </div>
</div>

<div class="citation">Research context: <a href="https://ora.ox.ac.uk/bookmarks/uuid%3Af1ae5ac6-f011-415b-be03-fa2f210829a3">Fernandez-Villaverde et al. (2025), "Charting the Uncharted," Oxford Discussion Paper 1070.</a></div>
<div class="footer"><span></span><span>02</span></div>

---
layout: default
class: unified-type
---

<div class="kicker">A massive Blind Spot</div>
<h2>Left in the wake.</h2>

<div class="stat-grid quad-stats">
  <div class="stat accent"><strong>43%</strong><span>est. global seaborne crude exports,<br>'17-'23</span></div>
  <div class="stat"><strong>558</strong><span>avg. suspected dark tankers/year,<br>~25% of global fleet</span></div>
  <div class="stat"><strong>7.8M</strong><span>metric tons crude/month,<br>'17-'23</span></div>
  <div class="stat"><strong>93.6M</strong><span>est. metric tons crude/year,<br>'17-'23</span></div>
</div>

<div class="source-strip impact-strip"><span>This 'dark shipping' drives deflationary growth, allowing adversaries to leverage discounted oil and boost industrial output.</span></div>
<div class="citation">Source: <a href="https://ora.ox.ac.uk/bookmarks/uuid%3Af1ae5ac6-f011-415b-be03-fa2f210829a3">Fernandez-Villaverde, Li, Xu &amp; Zanetti (2025), "Charting the Uncharted," Oxford Discussion Paper 1070.</a></div>
<div class="footer"><span></span><span>03</span></div>

---
layout: default
class: unified-type
---

<div class="kicker">03 / WHY THE STATUS QUO BREAKS</div>
<h2>An ensemble of factors.</h2>

<div class="signals">
  <div><span class="icon">01</span><b>AIS gaps</b><small>When and where a vessel disappears</small></div>
  <div><span class="icon">02</span><b>Geography</b><small>Risky routes and sanctioned-port proximity</small></div>
  <div><span class="icon">03</span><b>Behavior</b><small>Speed, heading and voyage anomalies</small></div>
  <div><span class="icon">04</span><b>Proximity</b><small>Potential ship-to-ship transfers</small></div>
</div>

<p class="claim">AIS gaps alone are not sufficient. Composite factors provide differentiated reporting.</p>
<div class="citation">Research context: <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC9629714/">Welch et al. (2022), "Hot Spots of Unseen Fishing Vessels"</a>; <a href="https://doi.org/10.3389/fmars.2018.00240">Miller et al. (2018), "Identifying Global Patterns of Transshipment Behavior."</a></div>
<div class="footer"><span></span><span>04</span></div>

---
layout: default
---

<h2>Multi-method detection.</h2>

<div class="methods-grid">
  <section class="method-card" style="min-height:205px">
    <div class="method-heading"><span>01 / BEHAVIORAL BASELINE</span><b>Detect deviations from a vessel's own pattern.</b></div>
    <svg class="method-graphic" viewBox="0 0 500 120" aria-label="Two vessel tracks diverge around a flagged anomaly" role="img">
      <path class="track track-faint" d="M28 27 C105 30 129 56 205 54 S345 89 474 82" />
      <path class="track track-active" d="M28 86 C110 89 137 83 205 92 S348 91 474 114" />
      <path class="vessel-shape vessel-faint" d="M32 15 l17 12 -17 12 -9 -12 z" />
      <path class="vessel-shape vessel-active" d="M34 74 l20 12 -20 12 -10 -12 z" />
      <circle class="anomaly-ring" cx="205" cy="73" r="18" />
      <path class="anomaly-mark" d="M205 62 v14 M205 81 v2" />
    </svg>
    <p>Use a Taylor approximation of known rendezvous behavior to estimate likely dark-rendezvous paths.</p>
  </section>
  <section class="method-card" style="min-height:205px">
    <div class="method-heading"><span>02 / PROXIMITY CLUSTERING</span><b>Surface unusual vessel-to-vessel proximity.</b></div>
    <svg class="method-graphic cluster-graphic" viewBox="0 0 500 120" aria-label="Cluster model visualizing vessel proximity" role="img">
      <ellipse class="cluster-halo halo-a" cx="126" cy="68" rx="82" ry="38" />
      <ellipse class="cluster-halo halo-b" cx="284" cy="43" rx="76" ry="32" />
      <ellipse class="cluster-halo halo-c" cx="385" cy="82" rx="66" ry="28" />
      <path class="cluster-link" d="M126 68 L284 43 L385 82" />
      <g class="cluster-points cluster-a"><circle cx="86" cy="58" r="5" /><circle cx="111" cy="80" r="5" /><circle cx="133" cy="51" r="5" /><circle cx="156" cy="73" r="5" /><circle cx="142" cy="92" r="5" /><circle cx="103" cy="43" r="5" /></g>
      <g class="cluster-points cluster-b"><circle cx="245" cy="34" r="5" /><circle cx="269" cy="55" r="5" /><circle cx="294" cy="28" r="5" /><circle cx="318" cy="48" r="5" /><circle cx="289" cy="71" r="5" /><circle cx="330" cy="25" r="5" /></g>
      <g class="cluster-points cluster-c"><circle cx="348" cy="74" r="5" /><circle cx="371" cy="91" r="5" /><circle cx="396" cy="67" r="5" /><circle cx="420" cy="87" r="5" /><circle cx="390" cy="100" r="5" /><circle cx="439" cy="65" r="5" /></g>
    </svg>
    <p>Cluster nearby vessels to reveal repeated, close-range interactions that merit review for coordinated activity.</p>
  </section>
</div>

<div class="composite-bridge" style="position:absolute;left:72px;right:72px;bottom:48px;margin:0;padding:7px 16px"><span>BEHAVIOR</span><i>+</i><span>PROXIMITY</span><i>=</i><b>COMPOSITE RISK SIGNAL</b></div>
<div class="footer"><span>COMPOSITE SIGNALS TO PRIORITIZED LEADS</span><span>05</span></div>

---
layout: default
---

<div class="kicker">06 / INVESTIGATION WORKFLOW</div>
<h2>From signal to review-ready lead.</h2>

<div class="funnel-flow">
  <section class="factor-funnel">
    <span>FACTOR ENSEMBLE</span>
    <div class="factor-tags"><i>AIS gaps</i><i>Geography</i><i>Behavior</i><i>Proximity</i></div>
    <small>Multiple weak signals converge into a focused lead.</small>
  </section>
  <section class="multimodal-node">
    <span>COMPOSITE</span>
    <b>Multimodal<br>signal</b>
    <i></i><i></i><i></i>
  </section>
  <section class="priority-box">
    <span>PRIORITIZE</span>
    <b>Review-ready<br>case</b>
    <small>Evidence + route + risk</small>
  </section>
  <section class="interdiction-stage">
    <div class="interdiction-arrow"></div>
    <span>INTERDICTION</span>
  </section>
</div>

<p class="workflow-body">Our system enables analysts, maritime-security teams, and enforcement partners to proactively identify high-risk activity and strengthen maritime domain awareness before it becomes an incident.</p>
<div class="footer"><span></span><span>06</span></div>

---
layout: center
class: closing
---

<div class="kicker"><span class="signal"></span> WAKE AI</div>
<h1>When ships go dark<br><em class="closing-emphasis">intelligence should not.</em></h1>
<div class="closing-tagline"><p>Making dark shipping visible.</p></div>
