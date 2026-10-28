// Shapes of the desk API (src/desk/api.py, src/desk/store.py).

export type AiActClass = "prohibited" | "high_risk" | "not_high_risk" | "transparency" | "minimal";

export interface GateBar {
  gate: string;
  startWeek: number;
  endWeek: number;
  done: boolean;
  wait: "capacity" | "session" | null;
  waitedWeeks: number;
}

export interface UseCaseSummary {
  id: string;
  title: string;
  stage: string;
  pattern: string;
  aiActClass: AiActClass;
  stops: { stop: string; reason: string }[];
  rank: number | null;
  priority: { score: number; hoursSavedPerYear: number; valueBasis: "projected" | "measured" } | null;
  goLive: string | null;
  readyBy: string | null;
  waitingFor: string | null;
  blockers: number;
  gates: GateBar[];
  critical: string[];
}

export interface Alert {
  kind: string;
  severity: "high" | "medium" | "low";
  handoff: string;
  due: string;
  text: string;
  department?: string;
  useCase?: string;
}

export interface Health {
  customer: string;
  score: number;
  band: "healthy" | "watch" | "at_risk";
  components: Record<string, number | null>;
  activation: number | null;
  momentum: number | null;
  departments: {
    department: string;
    seats: number;
    activation: number;
    momentum: number | null;
    messagesPerActive: number;
    champion: string | null;
  }[];
  trend: { week: string; activation: number | null }[];
  alerts: Alert[];
}

export interface Lever {
  lever: string;
  weeksSaved: number;
  useCases: Record<string, number>;
}

export interface CustomerInfo {
  id: string;
  name: string;
  level: string;
  land: string;
  mission_priorities: string[];
  seats: number;
}

export interface CustomerView {
  customer: CustomerInfo;
  health: Health;
  bottlenecks: { customer: string; role: string; waitedWeeks: number }[];
  levers: Lever[];
  planStart: string;
  computedAt: string;
  useCases: UseCaseSummary[];
}

export interface Portfolio {
  customers: CustomerView[];
  today: string;
  role: string;
}

export interface Duty {
  kind: string;
  article: string;
  text: string;
  appliesFrom: string | null;
}

export interface GateSlot {
  gate: string;
  title: string;
  role: string;
  start: string;
  end: string;
  startWeek: number;
  endWeek: number;
  waitedWeeks: number;
  wait: "capacity" | "session" | null;
  deps: string[];
  done: boolean;
  source: string | null;
}

export interface Dossier {
  useCase: {
    id: string;
    customer: string;
    title: string;
    mission: string;
    stage: string;
    owner: string;
    pattern: string;
    users: string;
    data: string[];
    pov: string;
    done: string[];
    decision_criteria: string[];
    success_measures: string[];
    blockers: { text: string; since: string; owner: string }[];
  };
  classification: {
    aiAct: { class: AiActClass; basis: string; roles: string[]; derogation: string | null; transparency: string[] };
    gdpr: { dpiaRequired: boolean; dpiaCriteria: string[]; dpiaMandatory: string[] };
    friaRequired: boolean;
    staffCouncil: string | null;
    accessibility: string | null;
    procurementRoute: string | null;
    hosting: { allowed: string[]; chosen: string | null; status: string | null; underContract: boolean };
    stops: { stop: string; reason: string }[];
    duties: Duty[];
    reasons: string[];
  };
  priority: UseCaseSummary["priority"];
  rank: number | null;
  path: {
    goLive: string | null;
    readyBy: string;
    waitingFor: string | null;
    critical: string[];
    gates: GateSlot[];
  } | null;
  architecture: {
    oversight: string;
    components: { layer: string; choice: string; why: string; rejected: string | null }[];
    decisions: { question: string; choice: string; tradeOff: string }[];
    mermaid: string;
  } | null;
  approval: {
    id: string;
    version: number;
    valid_until: string;
    target: string;
    model: string;
    tools: string[];
    document_ceiling: string;
    request_classes: string[];
    oversight: string;
    approved_by: string[];
    problems: string[];
  } | null;
  povRuns: { at: string; kind: string; action: string; result: Record<string, unknown> }[];
}

export interface EnquiryResult {
  action: "answer" | "handover";
  text: string;
  statements: { text: string; citations: string[] }[];
  reason: string | null;
  decidedBy: "rule" | "agent" | "guardrail";
  ticket: string | null;
  toolsCalled: string[];
  retrieved: string[];
  violations: string[];
  identifiersSeenByModel: number;
}

export interface DraftResult {
  disclosure: string;
  answers: { question: number; status: string; statements: { text: string; citations: string[] }[] }[];
  coSignUnits: string[];
  needsReview: { question: number; text: string; why: string }[];
  withheldDocuments: number;
  toolsCalled: string[];
  ceilingBreaches: string[];
}
