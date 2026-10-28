import type { CustomerView, UseCaseSummary } from "../../shared/api/types";
import { STAGE_LABEL, day } from "../../shared/format";
import { ClassMark } from "../../shared/ui/ClassMark";
import { EmptyState } from "../../shared/ui/states";
import { layout } from "../../theme/tokens";
import { horizonFor, monthTicks } from "./geometry";
import { PathStrip } from "./PathStrip";
import s from "./portfolio.module.css";

const PX = layout.weekRem * 16;
const FINISHED = new Set(["production", "adopted"]);

function order(useCases: UseCaseSummary[]): UseCaseSummary[] {
  const rank = (u: UseCaseSummary) => (u.stops.length ? 3 : FINISHED.has(u.stage) ? 2 : u.stage === "not_pursued" ? 3 : 1);
  return [...useCases].sort((a, b) => rank(a) - rank(b) || (a.rank ?? 999) - (b.rank ?? 999));
}

function when(u: UseCaseSummary): string {
  if (u.stops.length) return `Stopped: ${u.stops.map((x) => x.stop).join(", ")}`;
  if (FINISHED.has(u.stage)) return "In production";
  if (u.stage === "not_pursued") return "Not pursued";
  if (u.goLive) return `Go-live ${day(u.goLive)}`;
  if (u.waitingFor) return `Ready ${day(u.readyBy)}, then waits for ${u.waitingFor}`;
  return "Not planned";
}

export function PathBoard({ view, onOpen }: { view: CustomerView; onOpen: (id: string) => void }) {
  if (!view.useCases.length) {
    return (
      <EmptyState title="No use cases yet">
        Run discovery with the customer's mission owners and add the first use case to the portfolio file.
      </EmptyState>
    );
  }
  const rows = order(view.useCases);
  const horizon = horizonFor(rows);
  const ticks = monthTicks(view.planStart, horizon);
  return (
    <div className={s.boardScroll} tabIndex={0} aria-label="Path to production, scrolls sideways">
      <div className={s.board} style={{ ["--horizon" as string]: `${horizon * PX}px` }}>
        <div className={s.axisRow} aria-hidden="true">
          <div className={s.metaHead}>Use case, by priority</div>
          <div className={s.axis}>
            {ticks.map((t) => (
              <span key={t.week} style={{ left: `${t.week * PX}px` }}>
                {t.label}
              </span>
            ))}
          </div>
        </div>
        {rows.map((u, i) => {
          const planned = u.gates.length > 0;
          return (
            <div key={u.id} className={s.row} data-testid={`row-${u.id}`}>
              <div className={s.meta}>
                <span className={s.rank}>{u.rank ?? "–"}</span>
                <div>
                  <button type="button" className={s.title} onClick={() => onOpen(u.id)}>
                    {u.title}
                  </button>
                  <div className={s.sub}>
                    <ClassMark klass={u.aiActClass} stopped={u.stops.length > 0} />
                    <span>{STAGE_LABEL[u.stage] ?? u.stage}</span>
                    <span className={u.waitingFor ? s.waiting : ""}>{when(u)}</span>
                  </div>
                </div>
              </div>
              <div className={s.cell}>{planned && <PathStrip u={u} horizon={horizon} index={i} />}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
