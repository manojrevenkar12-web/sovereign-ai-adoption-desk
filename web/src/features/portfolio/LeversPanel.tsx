import type { CustomerView } from "../../shared/api/types";
import { ROLE_LABEL } from "../../shared/format";
import s from "./portfolio.module.css";

/** Where the plan loses time, and what each lever would buy: computed by replanning, not estimated. */
export function LeversPanel({ view }: { view: CustomerView }) {
  const own = view.bottlenecks.filter((b) => b.customer !== "portfolio");
  const shared = view.bottlenecks.filter((b) => b.customer === "portfolio");
  return (
    <section className={s.panel} aria-labelledby="levers-h">
      <h2 id="levers-h" className={s.panelTitle}>
        Where the plan loses time
      </h2>
      {own.length + shared.length === 0 ? (
        <p className={s.muted}>No reviewer holds up a critical path.</p>
      ) : (
        <ul className={s.bottlenecks}>
          {[...own, ...shared].map((b) => (
            <li key={`${b.customer}-${b.role}`}>
              <span>{ROLE_LABEL[b.role] ?? b.role}</span>
              <strong>{b.waitedWeeks} wk</strong>
            </li>
          ))}
        </ul>
      )}
      {view.levers.length > 0 && (
        <>
          <h3 className={s.panelSub}>Levers, priced by replanning</h3>
          <ol className={s.levers}>
            {view.levers.slice(0, 4).map((l) => (
              <li key={l.lever}>
                <span>{l.lever.replace(/ \(fictional\)/g, "")}</span>
                <strong>−{l.weeksSaved} wk</strong>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
