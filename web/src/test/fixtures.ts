import type { CustomerView, Dossier, Portfolio, UseCaseSummary } from "../shared/api/types";

export const useCase = (over: Partial<UseCaseSummary> = {}): UseCaseSummary => ({
  id: "uc-1",
  title: "Wohngeld enquiry assistant",
  stage: "proof_of_value",
  pattern: "enquiry_answering",
  aiActClass: "transparency",
  stops: [],
  rank: 1,
  priority: { score: 0.7, hoursSavedPerYear: 9450, valueBasis: "projected" },
  goLive: "2027-03-15",
  readyBy: "2027-03-15",
  waitingFor: null,
  blockers: 0,
  gates: [
    { gate: "pov", startWeek: 0, endWeek: 0, done: true, wait: null, waitedWeeks: 0 },
    { gate: "legal_basis", startWeek: 0, endWeek: 2, done: false, wait: null, waitedWeeks: 0 },
    { gate: "dpia", startWeek: 4, endWeek: 10, done: false, wait: "capacity", waitedWeeks: 2 },
    { gate: "accessibility", startWeek: 0, endWeek: 3, done: false, wait: null, waitedWeeks: 0 },
    { gate: "pilot", startWeek: 10, endWeek: 18, done: false, wait: null, waitedWeeks: 0 },
    { gate: "go_live", startWeek: 18, endWeek: 18, done: false, wait: null, waitedWeeks: 0 },
  ],
  critical: ["legal_basis", "dpia", "pilot", "go_live"],
  ...over,
});

export const customerView = (over: Partial<CustomerView> = {}): CustomerView => ({
  customer: { id: "lws", name: "Landesamt (fictional)", level: "land", land: "by", mission_priorities: ["Faster decisions"], seats: 150 },
  health: {
    customer: "lws",
    score: 97,
    band: "healthy",
    components: { activation: 0.9, delivery: 1 },
    activation: 0.52,
    momentum: 0.12,
    departments: [],
    trend: [],
    alerts: [],
  },
  bottlenecks: [{ customer: "lws", role: "dsb", waitedWeeks: 4 }],
  levers: [{ lever: "One more Data protection officer (DSB) at Landesamt", weeksSaved: 4, useCases: { "uc-1": 4 } }],
  planStart: "2026-11-02",
  computedAt: "2026-10-28T10:00:00Z",
  useCases: [useCase()],
  ...over,
});

export const portfolio = (): Portfolio => ({ customers: [customerView()], today: "2026-10-28", role: "architect" });

export const dossier = (): Dossier => ({
  useCase: {
    id: "uc-1",
    customer: "lws",
    title: "Wohngeld enquiry assistant",
    mission: "Answer general questions.",
    stage: "proof_of_value",
    owner: "Bürgerservice",
    pattern: "enquiry_answering",
    users: "public",
    data: ["public", "personal"],
    pov: "wohngeld",
    done: ["pov"],
    decision_criteria: [],
    success_measures: [],
    blockers: [],
  },
  classification: {
    aiAct: { class: "transparency", basis: "Art. 50(1)", roles: ["provider_own_name", "deployer"], derogation: null, transparency: ["interacts_with_public"] },
    gdpr: { dpiaRequired: true, dpiaCriteria: ["large_scale", "innovative_technology"], dpiaMandatory: [] },
    friaRequired: false,
    staffCouncil: null,
    accessibility: "BayBITV (EN 301 549)",
    procurementRoute: null,
    hosting: { allowed: ["openai_api_eu"], chosen: "openai_api_eu", status: "available", underContract: true },
    stops: [],
    duties: [{ kind: "ai_act", article: "Art. 50(1)", text: "People are told they talk to an AI system.", appliesFrom: "2026-08-02" }],
    reasons: ["Citizens talk to it directly, so they must be told it is an AI system (Art. 50(1))."],
  },
  priority: { score: 0.7, hoursSavedPerYear: 9450, valueBasis: "projected" },
  rank: 1,
  path: {
    goLive: "2027-03-15",
    readyBy: "2027-03-15",
    waitingFor: null,
    critical: ["legal_basis", "go_live"],
    gates: [
      { gate: "legal_basis", title: "Legal basis documented", role: "legal", start: "2026-11-02", end: "2026-11-13", startWeek: 0, endWeek: 2, waitedWeeks: 0, wait: null, deps: [], done: false, source: "Art. 6(1)(e) GDPR" },
      { gate: "go_live", title: "Production go-live", role: "customer_pm", start: "2027-03-15", end: "2027-03-15", startWeek: 19, endWeek: 19, waitedWeeks: 0, wait: null, deps: ["legal_basis"], done: false, source: null },
    ],
  },
  architecture: { oversight: "Handover", components: [{ layer: "channel", choice: "Portal chat", why: "No account needed", rejected: null }], decisions: [], mermaid: "flowchart LR" },
  approval: {
    id: "APR-1", version: 2, valid_until: "2027-04-30", target: "openai_api_eu", model: "gpt-5-mini",
    tools: ["search_guidance", "create_handover"], document_ceiling: "public", request_classes: ["public", "personal"],
    oversight: "handover_on_individual_case", approved_by: ["Amtsleitung"], problems: [],
  },
  povRuns: [],
});
