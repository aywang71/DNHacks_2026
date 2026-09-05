# DNHacks 2026 — Company Dossiers

What each sponsoring/attending organization actually does, and what that implies about what they'd be keen on. Sourced from company sites and open-source research on 5 Sep 2026.

**Industry partners listed on dnhacks.org:** Second Front · Deterrence · Clearview AI · DTX Ventures · Aslan Protects · Craft Ventures · Guardian RF · Torus Systems · Statecraft · Dirac · Even Platforms · Roman AI · Oncovera · Narion.

---

## Track sponsors

### Second Front Systems — *Defense track*
Public-benefit, venture-backed company that compresses the timeline for getting commercial software authorized onto government networks. Traditional authorization runs 12+ months; they claim ~90–120 days by letting vendors **inherit** an existing accreditation rather than build their own.

**The 2F Suite:**
- **2F Game Warden** — fully accredited hosting platform; the fast-track authorization path.
- **2F Workshop** — DevSecOps toolkit that bakes in security/compliance controls from the start, reducing compliance debt before authorization begins.
- **2F Frontier** — edge deployment for disconnected/remote environments: drones, devices, vehicles.

**Frameworks they live in:** DoD ATO, FedRAMP (incl. High), GovRAMP, **IL6** (classified), CMMC, SOC 2, NIST, plus UK/European equivalents. Proof points they cite: Integrate reaching IL6 in under 12 months vs. a typical 2–3 years; Sustainment accredited in 58 days.

**What they're keen on:** anything that reduces friction between commercial software and government networks. Compliance automation, audit trails, control inheritance, day-2 operations on accredited systems, one codebase deploying across classified/unclassified/coalition networks, and **edge/disconnected operation**. Their named track problem is **agent trust** — verifying an autonomous agent behaves as intended and can't be compromised.
**If we demo to them:** know where our system would need an ATO, what data classification it touches, and whether it can run disconnected.

### Deterrence — *Energy & Industrialization track*
> "Deterrence creates autonomous manufacturing systems that learn, adapt, and scale in real time across the U.S. defense industrial base."

An "intelligent autonomy layer for the defense industrial base" — sensors + robotics + AI on the factory floor. Five capabilities: **line instrumentation** (real-time sensor collection), **task automation** (robotics for repetitive/hazardous work), **inline verification** (machine-vision QC), **adaptive perception** (live awareness for robotic cells), **distributed production** (sharing improvements across facilities). Core thesis: capture "decades of operator knowledge" — production methods, legacy tooling, undocumented know-how — and turn it into software. Founders come from Tesla, Rivian, SpaceX, and defense.
**What they're keen on:** turning tacit industrial knowledge into structured data; per-shift measurable improvement; anything on a real production line.

### Clearview AI — *Health & Public Service track*
Facial recognition for law enforcement, federal agencies, military, and the IC. Products: **Clearview AI 2.0** and **Clearview GovCloud** (FedRAMP-certified). Claims a 70B+ image database and 99%+ accuracy across demographic groups. Use cases: suspect/witness/victim identification, cold cases, border and national security screening, counter-terrorism.
**What they're keen on:** large-scale computer vision and biometrics, identity resolution, investigative tooling, model accuracy across subgroups. Wesley Robbins (Head of ML) is attending.
**Worth knowing:** Clearview is a genuinely controversial company on privacy grounds. It sponsors the *Health and Public Service* track, which is the one track whose stated rubric is taxpayer cost and citizen experience. We don't need to engage the controversy — just don't be caught flat-footed by the pairing, and don't build a pitch whose core argument is an attack on their business model.

### DTX Ventures — *Open Category*
Venture fund positioning publicly around **"Protecting American Sovereignty."** Their site is thin — the substance lives in a "2026 Letter" hosted on Notion. Trent Gahm (Principal) is attending.
**What they're keen on:** ambitious cross-cutting technology; per the Open Category rubric — strength of idea, quality of execution, real-world impact at scale.

---

## Industry partners

### Aslan (aslanprotects.com)
AI that maps hidden adversary networks across the digital domain — surfacing undetected actors, infrastructure, and intelligence that human analysts can't reach at scale. Case studies: cross-border smuggling networks, technology-transfer pathways to foreign entities, cyber-fraud marketplaces, foreign recruitment operations targeting US professionals. Customers: defense & intel, homeland security, law enforcement. A federal partner described findings arriving "almost on a platter"; another called it "like having informants inside the networks."
**Most relevant partner to our maritime dark-rendezvous work.** Founder/CEO Chase Ried is a "Building to Defend" panelist.

### Guardian RF
Passive RF sensors for **drone detection and pilot geolocation**. 40 MHz–6 GHz, 360° coverage, no emissions, edge processing, 60-second deployment. Three platforms: **Scout** (portable), **Scout-X** (fixed site), **Full Spectrum** (wideband SDR for improvised systems). Founded by Georgetown physicists; fielded with Air Force bases, DIU, DOE, utilities, police, universities, stadiums.
**Keen on:** low-altitude airspace awareness, counter-UAS, passive sensing, edge inference on RF.

### Dirac (diracinc.com)
**BuildOS** — AI that converts CAD designs into manufacturing documentation: work instructions, MBOM, bill of process, from one source of truth. Proposes build sequences from CAD, generates 3D animated assembly steps, centralizes torque specs/fixtures/procedures, gives operators step-by-step guidance at the station, integrates with Siemens/PTC/SAP. Customers include **Anduril, Blue Origin, Mitsubishi Electric, Grimme**. Claims 87.5% reduction in work-instruction authoring time at Anduril; build planning from 3 days to 2 hours at Ancra Aircraft.
**Keen on:** eliminating tribal knowledge and version drift in manufacturing; versioned, auditable, executable process.

### Even Platforms
Autonomous machine shops. Hermle C400 5-axis machining centers, Hexagon CMM metrology, and **EvenOS** orchestrating quoting → scheduling → CNC → robotic material handling → quality verification. Factory-as-a-Service; lights-out 24/7 unmanned production. Full 5-axis across aerospace alloys. ITAR registered, pursuing AS9100.
> "America's machine shops are disappearing and the skilled workforce is aging out, exactly when defense, reshoring, and hardware companies need more precision manufacturing capacity."
Mission: "100x US manufacturing capacity, at a tenth the cost." Founder John Malloy is a panelist.

### Roman AI
LLM **inference infrastructure**, optimizing cost per token. Thesis: inference is two workloads with opposite hardware appetites — **prefill** is compute-heavy and parallel (suits H100/H200 GPUs), **decode** is memory-bound and sequential (suits dataflow silicon / RDUs). Most operators buy one chip type and run both on it. They benchmark ~800 tok/s decode (MiniMax M2.7 on dataflow silicon) vs. ~110 tok/s typical GPU-cloud baseline.
> "Inference is not one workload. It is two, with opposite hardware appetites — and almost everyone buys one kind of chip and runs both on it."
Notes this matters most for **agentic workflows** with dozens of sequential model calls, where decode speed multiplies end-to-end latency. Co-founder Gurpreet Chandhoke attending.

### Statecraft (statecraft.ai) — "AI Workers for Government"
AI-native federal services startup. Launched **Workforce**, deploying AI agents for federal back-office work: acquisition support, finance, grants, case management, reporting. Estimates contractors currently take up to **$100B/year** for this work; claims pilots showing up to 90% time savings and 95% cost savings. Aimed at GSA's "Million Hour Challenge." Co-founded by Alex Cohen (previously co-founded GovPro AI, exited to Unanet) and Priansh Shah (ex-Palantir technical program lead).
**Directly relevant to the Health & Public Service track's taxpayer-cost rubric**, and to our federal procurement idea.

### Oncovera
Precision oncology "operating system," prostate-cancer focused. Three pieces: **Oncovera Intelligence** (AI consolidating pathology, imaging, genomics, treatment history into one patient journey with decision support), **Oncovera Precision Sciences** (multi-omic analysis, liquid biopsy, spatial biology, biomarker discovery), **Oncovera Centers** (navigation, survivorship, exercise oncology, nutrition). Thesis: cancer care generates enormous disconnected data and lacks "connected intelligence." CEO Jonathan Merril attending.

### Narion Technologies
Autonomous aerial systems with **manipulator arms** — drones that physically service equipment on industrial facilities. Backed by Entrepreneurs First. Founder Arthur Garzon has demoed "Havoc" autonomy at the US Army's Operation Jailbreak. Public site is essentially a landing page; detail is thin.

### Torus Systems (torus.systems) — **unidentified**
Listed as an industry partner. Site is a JS-rendered shell exposing only the name and a product reference, **"TruTrac."** Web search returns several unrelated companies named Torus (a Utah energy-storage startup, an Australian key-management firm, a UK measurement company) and none match. **Treat as unknown**; ask on-site rather than guessing. Do not assume it is any of the other Toruses.

### Craft Ventures
Venture fund (founded by David Sacks), SaaS and marketplace roots with growing defense/industrial exposure. Partner & COO Brian Murray is a panelist.

---

## Other organizations represented

- **OpenAI** — AI sponsor; 4 staff + keynote; 2,500 Codex credits per participant. See `03-guests-and-judges.md`.
- **a16z** — American Dynamism program; Matt Cronin attending on national security law/policy.
- **Sequoia Capital** — Liam Corrigan, Partner.
- **Blumberg Capital** — mentorship prize attached to the Defense category.
- **Forterra** — autonomous ground vehicles (Lancer; Marine Corps ROGUE-Fires/NMESIS) and **Tensor**, modular electromagnetic spectrum operations for contested EM environments.
- **Neuralink** — Lorenzo Rizzotti.
- **Delve (delvedc.com)** — DC competitive intelligence and risk advisory for heavily regulated sectors. *Not* delve.co the compliance startup.
- **DEALSAGE** — AI platform delivering "decision-grade" legal, geopolitical, and risk insight for institutional M&A and investment; founded by Mario Mancuso (ex-Kirkland & Ellis CFIUS practice founder).
- **KAIROS** — Nick Lanham, co-founder of DoD CDAO's **Advana** platform.
- **Foundation for American Innovation (FAI)** — tech policy think tank; Joshua Levine (Technology & Statecraft) and Max Dauber (Non-Resident Fellow).
- **Station DC** — venue; non-profit connecting innovators, investors, and government/military leaders.
- **The David Network** — host organization.
