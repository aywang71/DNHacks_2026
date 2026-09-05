# DNHacks 2026 — Featured Guests, Panels, and What They'll Ask

The site lists these as **"Featured Guests"** — it does not publish a judge roster. The prizes page says *"Each category and special award will have its own set of judges. Plan to be judged by three groups of judges during project demos."* So this list is a **sample of the pool**, not a confirmed judging panel. Titles are verbatim from dnhacks.org; background detail is from open-source research and is flagged where uncertain.

**Composition at a glance:** 4 sitting government officials · 4 OpenAI staff · 5 VCs/investors · ~11 founders/operators of defense & industrial startups · 3 policy/think-tank people. This is an **operator and buyer audience, not an academic one.** Almost nobody in this room is scored by novelty. They are scored by whether things ship, get bought, and get accredited.

---

## Opening keynote

### Joseph Larson — VP & Head of Government, OpenAI
Leads OpenAI's public-sector engagement in the US and internationally; in the role since roughly July 2025. Won a 2026 Wash100 award for advancing federal AI adoption. Context around him: OpenAI launched ChatGPT Gov and "OpenAI for Government," and struck a GSA arrangement putting ChatGPT Enterprise in front of the federal executive branch. Also named lead independent board director at Arkenstone Defense.
**Cares about:** federal AI adoption actually landing in production; procurement and infrastructure as the bottleneck rather than model capability.

---

## Government officials

### Justin Fanelli — CTO, US Navy *(also panelist, "Move Fast and Fix Things")*
The most operationally specific government guest, and the one whose stated priorities most directly map onto buildable projects. His published DON CTO priority technology areas: **AI and autonomy; quantum; transport/connectivity; C5ISR/naval space; cyberspace operations/zero trust.** He runs the Navy's **Innovation Adoption Kit (IAK)**, explicitly aimed at the acquisition "valley of death," and has pushed to prioritize *measurable mission impact over technology demonstrations* on the way to an "AI-first maritime force." 2026 Wash100 winner.
**Will ask:** who is the actual user? what does this replace? how does it get through accreditation? what's the measurable mission effect, not the demo? — Note the Defense track explicitly names "naval warfare systems," and our maritime idea sits directly in his lane.

### Andrew McCarthy — CTO, White House Office of Anti-Fraud Initiatives
Previously Chief of Staff at CISA (Oct 2025 – Mar 2026) and a senior advisor at DHS. As CTO of the White House Task Force to Eliminate Fraud, works on using emerging tech to cut **improper payments** and strengthen program integrity; the task force has been working with OPM on health-benefits oversight.
*(Disambiguation: not the National Review columnist of the same name, who also comments on this task force.)*
**Cares about:** improper payments, fraud detection at federal scale, program integrity, entity resolution across disjoint government datasets, false-positive cost.

### Tim Booher — Advisor, Department of War
Former DARPA program manager (from Feb 2014) covering high-fidelity models, electronic warfare, and cyber. Previously deputy technical director for the Air Force Red Team at the AF Rapid Capabilities Office, and deputy director for technical policy integration for special programs at OUSD(Policy). Has advised the Secretary of Defense; serves on two National Academy of Sciences panels.
**Cares about:** technical rigor and red-team thinking. This is a person who will ask how the system fails and how an adversary defeats it. Expect the hardest adversarial question in the room from him.

### Jake Fischer — Assistant Secretary of the Army for Financial Management
Title as listed on dnhacks.org; **we could not independently verify this appointment in open sources** (public ASA(FM&C) leadership listings name others), so treat the exact title with mild caution while treating the domain as real. Domain context: ASA(FM&C) owns Army budget execution and the **Army audit** — the Army has a long, well-documented history of failing to achieve a clean audit opinion, and financial-system data quality is a live, expensive problem.
**Cares about:** auditability, financial data lineage, funds traceability, cost avoidance.

---

## OpenAI contingent

Four OpenAI staff plus the keynote plus 2,500 Codex credits per participant. **Assume OpenAI people judge "Best Use of AI."**

- **Lee Dunn** — Government Adoption at OpenAI. Focus: getting agencies to actually deploy.
- **Natalie Staudacher** — Model Behavior at OpenAI. Focus: alignment, refusal behavior, evals, how models act under adversarial or ambiguous input.
- **Yiren Lu** — Applied AI Engineer, OpenAI. The most technically hands-on AI person listed; will recognize a thin wrapper instantly.

**Implication for "Best Use of AI":** a Model Behavior person on the panel means the award is unlikely to go to "we called the API a lot." Things that read well to this group: real evals with numbers, measured failure modes, agent trust/verification, calibration and abstention, sensible human-in-the-loop design, and honest reporting of where the model is wrong. Using **Codex** visibly and well is a cheap alignment with the sponsor.

---

## Investors

### Brian Murray — Partner & COO, Craft Ventures *(panelist, "Startups and Modern American Industry")*
Craft Ventures is the David Sacks-founded fund; SaaS/marketplace roots with growing defense and industrial exposure.
### Liam Corrigan — Partner, Sequoia Capital
### Trent Gahm — Principal, DTX Ventures — presenting sponsor of the Open Category; DTX positions publicly around "Protecting American Sovereignty."
### Matt Cronin — Senior National Security Advisor, a16z
Works across a16z on national-security legal and policy issues and helps portfolio companies navigate regulation. Formerly Chief Investigative Counsel & Deputy General Counsel of the congressional **China Select Committee**, Director of National Cybersecurity at the White House, and a federal prosecutor on cybercrime and transnational crime. Active in a16z's **American Dynamism** program; has spoken publicly on drone warfare.
**Cares about:** China competition, export controls, tech transfer, drones, the legal/regulatory surface of defense tech.
### Blumberg Capital *(not on the guest list, but attached to the Defense prize)*
Defense 1st place and runner-up get live feedback and mentorship from a Blumberg investor.

**Implication:** five investors in the room means the *market* question will be asked repeatedly — who buys this, how big is it, why hasn't an incumbent done it. Have a one-sentence answer for "why doesn't Palantir/Anduril/the incumbent already do this."

---

## Founders and operators

### Second Front Systems — three people on the list
- **Tyler Sweatt**, CEO & Chairman *(panelist, "Building to Defend")* — West Point grad, former Army officer, ex-Deloitte, formerly Head of National Security at CalypsoAI, founded and sold Future Tense, led emerging tech & security at Toffler Associates; partner at the non-profit Silicon Valley Defense Group.
- **Josh Bosquez**, CTO
- **Nicole Utt**, Director of Product

The Defense track sponsor has its CEO, CTO, *and* product lead present. Their whole business is compressing government software accreditation (see `04-companies.md`). **They will ask deployment and accreditation questions about a hackathon project.** Knowing the words ATO, FedRAMP, IL5/IL6, CMMC, and being able to say where our project would sit, is disproportionately valuable in front of them.

### Chase Ried — Founder & CEO, Aslan *(panelist, "Building to Defend")*
Aslan does AI-driven adversary network mapping for defense/intel/law enforcement — smuggling networks, tech-transfer pathways, cyber-fraud marketplaces. **Closest company on the list to our maritime dark-rendezvous idea.** He is the single guest most likely to have a strong prior on that problem space, in both directions: he'll grasp it instantly, and he'll know what's hard about it.

### Josh Siegel — Founder, F-ADA *(panelist, "Building to Defend")*
Sparse public footprint for the company; a Josh Siegel, Ph.D. appears in HDIAC (DoD Homeland Defense & Security Information Analysis Center) circles. Panel topic is shipping to classified environments and accreditation.

### John Malloy — Founder, Even Platforms *(panelist, "Startups and Modern American Industry")*
Autonomous machine shops; "100x US manufacturing capacity, at a tenth the cost."

### Arthur Garzon — Founder & CEO, Narion Technologies
Autonomous aerial systems with manipulator arms — drones that physically service industrial equipment. Backed by Entrepreneurs First; has demoed "Havoc" autonomy capabilities at the US Army's Operation Jailbreak.

### Gurpreet Chandhoke — Co-Founder, Roman AI
LLM inference infrastructure; splits prefill (GPU) from decode (dataflow silicon/RDUs) to cut cost per token. **The one person on the list who will care about inference economics and latency as a first-class topic.**

### Jonathan Merril — CEO, Oncovera
Precision oncology platform — AI over fragmented pathology/imaging/genomics data, molecular diagnostics, patient navigation centers. Relevant to our hospital ideas (`../ideas/hospital.md`, `../ideas/idea-04-hospital-drug-shortages.md`).

### Jeff Berkowitz — CEO, Delve
**Delve (delvedc.com)** — Washington competitive intelligence and risk advisory / opposition research firm serving heavily regulated sectors (energy, life sciences, financial services). Berkowitz was RNC Research Director across five election cycles and ran research/messaging for the George W. Bush White House, the Giuliani presidential campaign, and the State Department.
*(Disambiguation: **not** delve.co, the YC-affiliated SOC 2 compliance automation startup — different company, different founders. Do not conflate these in conversation.)*

### Mario Mancuso — Founder & CEO, DEALSAGE
Founded and led the **CFIUS and National Security practice at Kirkland & Ellis**. Senate-confirmed presidential appointee as Under Secretary of Commerce for Industry and Security; Deputy Assistant Secretary of Defense for Special Operations; National Intelligence Council Global Markets Board; combat veteran; author of *A Dealmaker's Guide to CFIUS*. DEALSAGE is an AI platform for legal/geopolitical risk in M&A and investment.
**Cares about:** foreign investment screening, export control, supply-chain and ownership risk, geopolitical risk as structured data.

### Charles Swannack — VP of Electromagnetic Spectrum Operations, Forterra
Forterra builds autonomous ground vehicles for defense (the **Lancer** platform; first deployment of self-driving systems for the Marine Corps' ROGUE-Fires under NMESIS) and **Tensor**, a modular electromagnetic spectrum operations system for distributed sensing and spectrum intelligence in contested EM environments.
**Cares about:** GPS-denied and comms-denied operation, RF/spectrum, autonomy in contested environments. **If our system assumes clean GPS/AIS/network, he is the person who will point out that the assumption fails in exactly the scenarios that matter.**

### Wesley Robbins — Head of ML, Clearview AI
Health & Public Service track sponsor. Large-scale facial recognition / biometric identification; the deep technical ML voice among sponsors. Expect real questions on model evaluation, dataset scale, and accuracy across subgroups.

### Nick Lanham — Senior Data & AI Analyst, KAIROS
**Co-founder of the DoD CDAO's Advana platform** — the Pentagon's enterprise data/analytics platform — and Deputy Program Manager for Advana, leading product for the Deputy Secretary of Defense executive analytics suite and Advana's Data-as-a-Service team. Previously at OUSD(Comptroller), Enterprise Data & Business Performance.
**Cares about:** DoD data plumbing, data acquisition and governance, enterprise analytics at department scale. Probably the deepest federal-data-reality expertise in the room.

### Lorenzo Rizzotti — Neuralink

---

## Policy / think tank

### Joshua Levine — Director of Technology & Statecraft, Foundation for American Innovation (FAI)
Works on digital competition and interoperability, online expression, emerging tech. Published *"The Data Crunch: Accelerating American AI through Government Data Access"* and argued for a **US Data Accelerator** — government making its data more accessible and AI-ready. Also co-authored *"The Mobile Trilemma."* Previously a technology and innovation policy analyst at the American Action Forum.
**Note:** a project built on making previously unusable government data useful maps almost exactly onto his published thesis.

### Max Dauber — Non-Resident Fellow, FAI *(panelist, "Move Fast and Fix Things")*

---

## Panel sessions (all Saturday — these run during our build time)

### 1:00 p.m. — **Building to Defend**
> "How does software actually get built, sold, and deployed inside the world's most demanding customer? A conversation on shipping to classified environments, navigating accreditation, and what it takes for small teams to move at startup speed inside the defense industrial base."
Panelists: Tyler Sweatt (Second Front), Josh Siegel (F-ADA), Chase Ried (Aslan).

### 2:00 p.m. — **Move Fast and Fix Things — Transforming Government Through Technology**
> "Federal systems touch hundreds of millions of Americans every day. Join our panelists to discuss what's broken, what's actually getting fixed, and how top engineers can have an outsized public impact early in their careers."
Panelists: Justin Fanelli (US Navy CTO), Max Dauber (FAI).

### 3:00 p.m. — **Startups and Modern American Industry**
> "American industry is being rebuilt from the ground up by startups, not incumbents. Join our panelists to discuss what it takes to succeed as a founder in manufacturing, defense, energy, and logistics today, and where the biggest opportunities lie for the next generation of American companies."
Panelists: Brian Murray (Craft Ventures), John Malloy (Even Platforms).

**Tactical note:** all three panels sit in the Saturday afternoon build window. They are also the cheapest available source of the vocabulary and framing these judges use, and a chance to be recognized before demos. Sending one team member to the panel most relevant to our track — while the rest build — is likely worth the hour.
