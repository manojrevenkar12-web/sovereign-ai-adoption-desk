import type { GateBar, UseCaseSummary } from "../../shared/api/types";
import { addWeeks, month } from "../../shared/format";

export interface Bar {
  gate: string;
  x: number;
  width: number;
  critical: boolean;
  done: boolean;
  waitX: number | null; // where a capacity or session wait began, if any
}

export interface StripGeometry {
  bars: Bar[];
  thread: { x1: number; x2: number } | null; // the critical path, start to go-live
  end: number | null; // week the use case is ready for go-live
  width: number;
}

/** Positions of one use case's gates, in weeks from the plan's start. */
export function strip(u: UseCaseSummary, horizon: number): StripGeometry {
  const crit = new Set(u.critical);
  const bars: Bar[] = u.gates
    .filter((g: GateBar) => g.gate !== "go_live")
    .map((g) => ({
      gate: g.gate,
      x: Math.min(g.startWeek, horizon),
      width: Math.max(0, Math.min(g.endWeek, horizon) - Math.min(g.startWeek, horizon)),
      critical: crit.has(g.gate),
      done: g.done,
      waitX: g.waitedWeeks > 0 ? Math.max(0, g.startWeek - g.waitedWeeks) : null,
    }));
  const go = u.gates.find((g) => g.gate === "go_live");
  const end = go ? Math.min(go.endWeek, horizon) : null;
  const critBars = bars.filter((b) => b.critical);
  const thread = critBars.length && end !== null ? { x1: Math.min(...critBars.map((b) => b.x)), x2: end } : null;
  return { bars, thread, end, width: horizon };
}

/** How many weeks the board shows: everything that will be ready, plus a margin. */
export function horizonFor(useCases: UseCaseSummary[], min = 40, max = 120): number {
  const ends = useCases.flatMap((u) => u.gates.map((g) => g.endWeek));
  return Math.max(min, Math.min(max, (ends.length ? Math.max(...ends) : 0) + 4));
}

/** Month labels for the axis: the first week of each month after the plan start. */
export function monthTicks(planStart: string, horizon: number): { week: number; label: string }[] {
  const out: { week: number; label: string }[] = [];
  let last = "";
  for (let w = 0; w < horizon; w++) {
    const iso = addWeeks(planStart, w);
    const m = iso.slice(0, 7);
    if (m !== last) {
      out.push({ week: w, label: month(iso) });
      last = m;
    }
  }
  return out;
}
