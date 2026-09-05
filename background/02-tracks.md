# DNHacks 2026 — The Four Categories

Category descriptions below are **verbatim from dnhacks.org**. The "reading" under each is our inference, marked as such.

An important structural note from the prizes page: *"Our industry partners will help define specific challenge prompts within this category, so teams will have the option to build toward well-scoped, real-world problems or explore open-ended innovation of their own."* — said of Defense, but expect partner-defined prompts to surface on-site across tracks. **Check for released challenge prompts at the opening, before locking scope.**

---

## 1. Defense — presented by **Second Front**

> Push the frontier of national security technology, from autonomous systems and edge compute to cybersecurity and command and control.

> This is one of the broadest and most ambitious categories at DNHacks. Students are invited to tackle national security challenges across the full stack: software, hardware, and everything in between. Project areas include cybersecurity, command and control systems, edge compute, drone technology, and naval warfare systems.

> One of the most pressing problems in modern cybersecurity is **agent trust**. As agentic AI systems take over more workflows, verifying that an AI agent is behaving as intended and cannot be compromised becomes critical. Projects might focus on designing testing frameworks, adversarial red-teaming systems, or trust verification protocols for autonomous cybersecurity agents.

**Named sub-areas:** cybersecurity · command and control · edge compute · drone technology · naval warfare systems · agent trust.

**Perk:** Defense 1st place and runner-up get a live feedback/mentorship session with an investor from **Blumberg Capital**.

**Reading:** The site calls out *agent trust* as a specific named problem — the only place in any category description where a single problem gets its own paragraph. That is as close to a stated challenge prompt as the site gets, and it is the one topic where the sponsor (Second Front, whose entire business is getting software accredited into classified environments) and the AI sponsor (OpenAI) overlap. "Naval warfare systems" is also conspicuous given the US Navy CTO is a featured guest and panelist.

---

## 2. Energy and Industrialization — presented by **Deterrence**

> Build the technology stack that powers American industrial strength, from critical minerals and smart energy to agricultural systems.

> America needs to industrialize at scale, and this category is where that work begins. Projects span the full range of industrial technology: satellite-based models for identifying optimal mining sites, hazard detection systems for industrial environments, analysis tools that make drilling cheaper and less environmentally damaging, and wearable sensing platforms for field workers.

> Energy infrastructure is another rich area. Participants might explore decentralized systems that allow energy producers, such as solar panel owners, to sell excess power back to local grids or directly to consumers, creating more resilient and efficient markets.

> Agriculture technology is also in scope here. From robotics that can perform precise field operations to satellite imagery models that forecast crop yields, there is enormous opportunity to modernize how America grows food and manages land at scale.

> This category is supported by partners who operate at the intersection of technology and physical industry, and projects here have the potential to reach production environments well beyond the hackathon weekend.

**Named sub-areas:** critical minerals · smart energy · agricultural systems · industrial tech · decentralized energy markets · satellite models for mining site selection · industrial hazard detection · drilling analysis · wearable field sensing · field robotics · satellite crop-yield forecasting.

**Reading:** This is the most *hardware-flavored* track, and the sponsors behind it (Deterrence, Dirac, Even Platforms) are all physical-manufacturing companies. A pure-software entry here is competing against the track's own gravity — it needs to be visibly about a physical process. Note the explicit call-out of **satellite imagery models that forecast crop yields**: that is a named example on the site, which cuts both ways — it is clearly in scope, and it is also the most obvious thing anyone will build. See `../ideas/idea-03-agricultural-orchestration.md` and `../ideas/ag_orches.md`, which already assessed that space as saturated.

---

## 3. Health and Public Service — presented by **Clearview AI**

> Modernize how government serves Americans, from healthcare access and .gov user experience to smarter public infrastructure.

> This category is focused on the interface between technology and public service. Government websites, healthcare systems, and federal workflows touch hundreds of millions of Americans every day, yet they often lag far behind the standards of modern software. DNHacks participants in this category will build tools that genuinely improve that experience.

> Example projects include: a telehealth platform designed for low-bandwidth rural connections, enabling patients to attend appointments from home without needing fast internet; a candidate screening tool for federal hiring that matches resumes to open roles and surfaces relevant qualifications like veteran status; and an AI assistant that helps everyday users navigate and complete complex government forms.

> Projects in this category are evaluated not just on technical quality, but on their **potential to reduce costs for taxpayers and improve the experience of interacting with government**. We are working with partners in the administration who are actively looking for talented engineers and designers to help modernize critical systems.

**Reading:** This is the only category with a stated *second* evaluation axis beyond technical quality — **taxpayer cost reduction**. If we enter here, a defensible dollar figure ("this addresses $X of Y") is not optional decoration; the category description asks for it. The guest list backs this up heavily: White House anti-fraud CTO, Army financial management, DoD Advana co-founder, and Statecraft (a partner whose entire pitch is automating ~$100B of federal back-office work). The three site examples (rural telehealth, federal hiring screening, form-filling assistant) should be treated as *taken* — they will be built by multiple teams.

---

## 4. Open Category — presented by **DTX Ventures**

> Have an idea that does not fit neatly into the other tracks? Build it here, backed by general-purpose investors who support bold, cross-cutting projects.

> Some of the most interesting projects defy easy categorization. The Open Category exists for teams with a strong idea that does not fit squarely into Defense, Energy, or Health. If your project sits at the intersection of multiple domains, or if you are exploring entirely new territory, this is the right home for it.

> Partners in this category include general-purpose venture funds and investors who are excited by ambitious, cross-cutting technology. Teams here are judged on **the strength of their idea, the quality of their execution, and the real-world impact their project could have at scale**.

**Reading:** Open states its rubric most explicitly — idea / execution / impact at scale. DTX Ventures' public positioning is "Protecting American Sovereignty," so "general-purpose" here still leans national. Open is the right home for a genuinely cross-domain project, but it is also where every team that couldn't decide will land, so the field may be both large and weak.

---

## Category selection logic

- You must **place in a category** to be eligible for the overall $25K/$10K. Category choice is therefore a competitive decision, not a labelling one: pick the track where our project is strongest *relative to the field*, not the one it fits most literally.
- **Best in Design** and **Best Use of AI** are event-wide and stack on top of a category placement. Two extra shots at the same project.
- A project with a real cross-track story can often be filed in whichever track is thinnest. Our maritime idea (`../ideas/idea-01-maritime-dark-rendezvous.md`) is explicitly noted as "Defense, or Open."
