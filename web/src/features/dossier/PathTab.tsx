import { motion } from "motion/react";

import type { Dossier } from "../../shared/api/types";
import { GATE_SHORT, ROLE_LABEL, day } from "../../shared/format";
import { useGateChange, usePortfolio } from "../../shared/hooks/queries";
import { EmptyState, ErrorState } from "../../shared/ui/states";
import { motionTokens } from "../../theme/tokens";
import s from "./dossier.module.css";

export function PathTab({ d }: { d: Dossier }) {
  const change = useGateChange(d.useCase.id);
  const me = usePortfolio();
  const canWrite = me.data?.role === "architect";
  if (!d.path) {
    return (
      <EmptyState title="No path to plan">
        {d.classification.stops.length
          ? "The use case is stopped, so no gate is planned."
          : "It is already in production or was not pursued."}
      </EmptyState>
    );
  }
  const critical = new Set(d.path.critical);
  const gates = [...d.path.gates].sort((a, b) => a.startWeek - b.startWeek || a.endWeek - b.endWeek);
  return (
    <section aria-labelledby="gates-h">
      <h2 id="gates-h" className={s.h2}>
        Gates, in the order they start
      </h2>
      <p className={s.lead}>
        Ready for go-live on <strong>{day(d.path.readyBy)}</strong>
        {d.path.waitingFor ? `, then waits for ${d.path.waitingFor}` : ""}. Marked gates are on the critical path: any
        week they slip moves the go-live.
      </p>
      {change.isError && <ErrorState error={change.error} />}
      <ol className={s.gates}>
        {gates.map((g, i) => (
          <motion.li
            key={g.gate}
            className={`${s.gate} ${critical.has(g.gate) ? s.gateCritical : ""} ${g.done ? s.gateDone : ""}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ ...motionTokens.reveal, delay: i * motionTokens.gateStagger }}
          >
            <div className={s.gateMain}>
              <span className={s.gateName}>{GATE_SHORT[g.gate] ?? g.gate}</span>
              <span className={s.gateTitle}>{g.title}</span>
              {g.source && <span className={s.article}>{g.source}</span>}
            </div>
            <div className={s.gateWhen}>
              {g.done ? (
                <span className={s.passed}>Passed</span>
              ) : (
                <>
                  <span>
                    {day(g.start)}
                    {g.endWeek > g.startWeek ? ` to ${day(g.end)}` : ""}
                  </span>
                  <span className={s.role}>{ROLE_LABEL[g.role] ?? g.role}</span>
                  {g.waitedWeeks > 0 && (
                    <span className={s.waitNote}>
                      waits {g.waitedWeeks} wk for {g.wait === "session" ? "the next session" : "a free reviewer"}
                    </span>
                  )}
                </>
              )}
            </div>
            {canWrite && !["go_live", "pov"].includes(g.gate) && (
              <button
                type="button"
                className={s.gateButton}
                disabled={change.isPending}
                onClick={() => change.mutate({ gate: g.gate, done: !g.done })}
              >
                {g.done ? "Reopen" : "Mark passed"}
              </button>
            )}
          </motion.li>
        ))}
      </ol>
    </section>
  );
}
