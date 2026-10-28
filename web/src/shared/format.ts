import type { AiActClass } from "./api/types";

export const CLASS_LABEL: Record<AiActClass, string> = {
  prohibited: "Prohibited",
  high_risk: "High-risk",
  not_high_risk: "Art. 6(3)",
  transparency: "Transparency",
  minimal: "Minimal",
};

export const STAGE_LABEL: Record<string, string> = {
  discovery: "Discovery",
  qualified: "Qualified",
  evaluating: "Evaluating",
  proof_of_value: "Proof of value",
  production_readiness: "Production readiness",
  production: "Production",
  adopted: "Adopted",
  not_pursued: "Not pursued",
};

export const GATE_SHORT: Record<string, string> = {
  pov: "Proof of value",
  legal_basis: "Legal basis",
  dpia: "DPIA",
  fria: "FRIA",
  automated_decision_basis: "§ 35a basis",
  derogation_record: "Art. 6(4) record",
  social_data_notice: "§ 80 SGB X notice",
  tax_secrecy_review: "§ 30 AO review",
  staff_council: "Staff council",
  security_concept: "Security concept",
  procurement: "Procurement",
  accessibility: "Accessibility",
  conformity: "Conformity",
  eu_registration: "EU database",
  pilot: "Pilot",
  go_live: "Go-live",
};

export const ROLE_LABEL: Record<string, string> = {
  legal: "Legal counsel",
  dsb: "Data protection officer",
  isb: "Security officer",
  staff_council: "Staff council",
  procurement: "Procurement",
  accessibility: "Accessibility lab",
  customer_pm: "Customer project lead",
  provider_team: "Provider team",
  deployment_eng: "OpenAI Deployment Engineering",
};

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" });

export function day(iso: string | null | undefined): string {
  return iso ? dateFmt.format(new Date(`${iso}T12:00:00`)) : "—";
}

export function month(iso: string): string {
  return monthFmt.format(new Date(`${iso}T12:00:00`));
}

export function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`;
}

export function weeksBetween(fromIso: string, toIso: string): number {
  return Math.round((new Date(toIso).getTime() - new Date(fromIso).getTime()) / (7 * 24 * 3600 * 1000));
}

export function addWeeks(iso: string, weeks: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + weeks * 7);
  return d.toISOString().slice(0, 10);
}

export function humanise(key: string): string {
  return key.replace(/_/g, " ");
}

export const TARGET_LABEL: Record<string, string> = {
  openai_api_eu: "OpenAI API, EU data residency",
  chatgpt_enterprise_eu: "ChatGPT Enterprise, EU data residency",
  openai_for_germany: "OpenAI for Germany (SAP Delos Cloud)",
};

export function target(id: string | null | undefined): string {
  return id ? (TARGET_LABEL[id] ?? humanise(id)) : "none fits";
}
