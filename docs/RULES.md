# The rules the desk applies, in plain words

This is what decides a use case's path to production. It is written for the customer's counsel,
data protection officer and staff council, and it is also the only document a person writing a
blind test case may read. The desk is not legal advice: it makes the questions visible early,
with their sources, so the people who decide can decide in time.

Dates: today the AI Act's prohibitions and AI-literacy duty apply (since 2 February 2025), the
transparency duties apply (since 2 August 2026), and the high-risk duties for Annex III systems
apply from **2 December 2027** (moved from 2 August 2026 by the Digital Omnibus on AI, Regulation
(EU) 2026/1744, in force since 27 July 2026). The desk plans as if a system must meet the duties
from its go-live; the transitional rules of Art. 111 are not modelled.

## 1. AI Act class

Work through these in order; the first that applies decides.

1. **Prohibited** if the use case involves any Art. 5 practice. The ones a public body meets:
   social scoring (Art. 5(1)(c)), predicting crime from profiling alone (5(1)(d)), untargeted
   scraping of faces (5(1)(e)), inferring emotions of staff at the workplace or of pupils (5(1)(f)),
   biometric categorisation by sensitive traits (5(1)(g)), manipulation (5(1)(a)).
   A prohibited use case is stopped.
2. If the use case falls in an **Annex III area** — biometrics, critical infrastructure,
   education, employment and workers, public benefits (eligibility for, granting, reducing,
   revoking or reclaiming essential public assistance), emergency call triage, law enforcement,
   migration and asylum, justice, elections — look at the system's role:
   - **It only informs** (answers general questions, explains, summarises published texts) and
     does not evaluate, decide or steer an outcome for a person: its intended purpose is outside
     the area. Exception: in the biometrics and elections areas an informing system stays inside.
   - **Its role is one of the four in Art. 6(3)** — a narrow procedural task (a), improving the
     result of work a person already completed (b), detecting patterns or deviations from earlier
     patterns without replacing the human assessment (c), or a preparatory task to an assessment
     (d) — and it does **not profile** natural persons: it is **not high-risk** under Art. 6(3).
     The authority must document that assessment (Art. 6(4)) and register the system (Art. 49(2)).
   - Otherwise (its output **materially influences** or **decides** the outcome, or it profiles
     people): **high-risk**. Profiling rules out every Art. 6(3) derogation.
3. **Transparency** if the system is not prohibited or high-risk and either
   - citizens interact with it directly (Art. 50(1)): they must be told it is an AI system; or
   - it generates text that is published to inform the public on matters of public interest
     without a person reviewing it and holding editorial responsibility (Art. 50(4)). If a person
     reviews it and is editorially responsible, there is no disclosure duty.
   High-risk systems that citizens use directly carry the Art. 50(1) duty as well.
4. Otherwise **minimal**.

**Provider or deployer.** If the authority builds the system on the API and puts it into service
under its own name, it is the **provider** of that system (Art. 3(3)). If it uses the ChatGPT
Enterprise assistant for an Annex III purpose, it changes the assistant's intended purpose and
becomes the provider of a high-risk system (Art. 25(1)(c)). It is always the deployer. A high-risk
provider owes risk management, data governance, documentation, logging, oversight design,
accuracy and robustness, a quality management system, a conformity assessment, registration and
post-market monitoring. A high-risk deployer owes human oversight by competent staff, keeping logs
for six months, informing workers' representatives, registering its use, informing affected
people, and a **fundamental rights impact assessment (FRIA, Art. 27)** before first use. Every
public body deploying a high-risk system needs a FRIA, except for critical infrastructure.

## 2. Data protection (GDPR)

Personal data are any of: ordinary personal data, special categories (Art. 9), social data
(§ 35 SGB I), data under tax secrecy (§ 30 AO).

- **Legal basis:** a public body relies on Art. 6(1)(e) with a basis in law (federal: § 3 BDSG;
  Bavaria: Art. 4 BayDSG). Needed whenever personal data are processed.
- **DPIA (Art. 35):** count the criteria of the EDPB-endorsed WP 248 guidance that apply. Two or
  more means a DPIA. The criteria, as the desk applies them (only when personal data are involved):
  1. evaluation or scoring — the system profiles people, or its role is to materially influence,
     decide, or detect patterns about cases;
  2. automated decision with legal effect — the system decides without a person;
  3. systematic monitoring of data subjects;
  4. sensitive data — special categories, social data, or tax secrecy;
  5. large scale;
  6. matching or combining datasets;
  7. vulnerable data subjects (benefit claimants, children, asylum seekers…);
  8. innovative technology — the German supervisory authorities count AI used with personal data,
     so this criterion applies to **every** use case with personal data;
  9. preventing people from exercising a right (not used by the desk).
  A DPIA is also needed regardless of the count when Art. 35(3) names the case: automated decisions
  with profiling, or large-scale processing of special categories.
- **Fully automated decisions:** a decision without a person is allowed only where a legal
  provision permits it and the authority has no discretion (Art. 22 GDPR, § 35a VwVfG). The desk
  adds a gate to find that provision whenever the system would decide on its own, or when the role
  is "decides" and personal data are involved.

## 3. Secrecy and classification

- **Social data:** a contractor processing social data for the authority must be notified to the
  supervisory authority before the contract is awarded (§ 80 SGB X).
- **Tax secrecy:** a legal review of the disclosure ground (§ 30(4) AO) before any external processing.
- **Classified information** (VS-NUR FÜR DEN DIENSTGEBRAUCH and above): none of the hosting targets
  is approved for it. A use case that needs classified data is **stopped**.

## 4. Staff council

If staff use the tool and their use is logged per person (the default for staff tools), the tool is
objectively able to monitor behaviour or performance, which gives the staff council
co-determination: § 80 Abs. 1 Nr. 21 BPersVG for federal bodies, Art. 75a Abs. 1 Nr. 1 BayPVG in
Bavaria (BVerwG, 4 May 2023, 5 P 16.21: objective suitability is enough). Citizen-only tools need
no staff council agreement. Where an AI framework agreement (Dienstvereinbarung) already covers new
tools, a short notification replaces the full procedure.

## 5. Accessibility

A channel citizens use must meet EN 301 549 through BITV 2.0 (federal) or BayBITV (Bavaria).

## 6. Hosting

| Target | Accepts | Status |
|---|---|---|
| OpenAI API, EU data residency project (`openai_api_eu`) | public, internal, personal | available |
| ChatGPT Enterprise workspace, EU data residency (`chatgpt_enterprise_eu`) | public, internal, personal | available |
| OpenAI for Germany on SAP Delos Cloud (`openai_for_germany`) | also special categories, social data, tax secrecy | planned (announced September 2025 for 2026) |

The data classes each target accepts are an **example hosting policy** a customer confirms; a
customer may narrow it further for a data class. Each target also suits only some channels:
the API project suits API applications, agent workflows and citizen channels; the ChatGPT
Enterprise workspace suits the staff assistant and Codex; OpenAI for Germany suits all but Codex.
Which channel a use case has follows from its pattern (see docs/DISCOVERY.md).

The desk chooses, among the targets that suit the channel and accept every data class: the
customer's stated preference first, then a target that is available today, then one already under
contract. If the only possible target is planned, go-live waits for it. If none fits, the use case
is stopped.

## 7. Procurement

No procurement is needed when the chosen target is already under contract. Otherwise: a call-off if
the customer has a framework agreement for AI services; else an EU-wide procedure if the estimated
contract value reaches the EU threshold (from 1 January 2026: **€140,000** for supplies and
services of central government authorities, **€216,000** for all others); else a national procedure.
