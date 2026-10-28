import { motion } from "motion/react";

import { day, pct } from "../../shared/format";
import { useCustomer } from "../../shared/hooks/queries";
import { EmptyState, ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/tokens";
import s from "./health.module.css";
import { Trend } from "./Trend";

const COMPONENT: Record<string, string> = {
  activation: "Activation",
  momentum: "Momentum",
  breadth: "Breadth across departments",
  depth: "Depth of use",
  delivery: "Delivery on plan",
};
const BAND: Record<string, string> = { healthy: "Healthy", watch: "Watch", at_risk: "At risk" };
const ACTIVATION_TARGET = 0.55;

export function HealthPage({ customer, go }: { customer: string; go: (to: string) => void }) {
  const q = useCustomer(customer);
  if (q.isPending) {
    return (
      <div className={s.page}>
        <Skeleton lines={8} label="Loading account health" />
      </div>
    );
  }
  if (q.isError) {
    return (
      <div className={s.page}>
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  }
  const h = q.data.health;
  const name = q.data.customer.name;
  return (
    <div className={s.page}>
      <button type="button" className={s.back} onClick={() => go(`/customers/${customer}`)}>
        Back to the portfolio
      </button>
      <header className={s.head}>
        <h1 className={s.title}>{name}: account health</h1>
        <p className={s.score} data-band={h.band}>
          <strong>{h.score}</strong> {BAND[h.band]}
        </p>
      </header>
      <div className={s.grid}>
        <section aria-labelledby="usage-h">
          <h2 id="usage-h" className={s.h2}>
            Use of the workspace
          </h2>
          {h.activation === null ? (
            <EmptyState title="No usage yet">
              The customer has no workspace in use. Health comes from delivery on the plan until seats are active.
            </EmptyState>
          ) : (
            <>
              <p className={s.lead}>
                {pct(h.activation)} of seats active in the last four weeks,{" "}
                {h.momentum !== null && h.momentum < 0 ? "down" : "up"} {pct(Math.abs(h.momentum ?? 0))} on the four
                weeks before.
              </p>
              <Trend trend={h.trend} target={ACTIVATION_TARGET} />
              <table className={s.table}>
                <caption className={s.caption}>Departments, last four weeks</caption>
                <thead>
                  <tr>
                    <th scope="col">Department</th>
                    <th scope="col">Active</th>
                    <th scope="col">Change</th>
                    <th scope="col">Champion</th>
                  </tr>
                </thead>
                <tbody>
                  {h.departments.map((d) => (
                    <tr key={d.department}>
                      <th scope="row">{d.department}</th>
                      <td>
                        <span className={s.meter} style={{ ["--v" as string]: `${Math.round(d.activation * 100)}%` }} />
                        {pct(d.activation)}
                      </td>
                      <td className={d.momentum !== null && d.momentum < 0 ? s.down : undefined}>
                        {d.momentum === null ? "—" : `${d.momentum > 0 ? "+" : ""}${Math.round(d.momentum * 100)}%`}
                      </td>
                      <td className={d.champion ? undefined : s.missing}>{d.champion ?? "none named"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          <h2 className={s.h2}>What the score is made of</h2>
          <dl className={s.components}>
            {Object.entries(h.components).map(([k, v]) => (
              <div key={k}>
                <dt>{COMPONENT[k] ?? k}</dt>
                <dd>
                  {v === null ? (
                    "no data"
                  ) : (
                    <span className={s.meter} style={{ ["--v" as string]: `${Math.round(v * 100)}%` }} />
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <section aria-labelledby="alerts-h">
          <h2 id="alerts-h" className={s.h2}>
            What happens this week
          </h2>
          {h.alerts.length === 0 ? (
            <EmptyState title="Nothing needs an intervention">Keep the monthly review with the sponsor.</EmptyState>
          ) : (
            <ol className={s.alerts}>
              {h.alerts.map((a, i) => (
                <motion.li
                  key={`${a.kind}-${i}`}
                  data-severity={a.severity}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ ...motionTokens.reveal, delay: i * motionTokens.rowStagger }}
                >
                  <p>{a.text}</p>
                  <p className={s.handoff}>
                    {a.handoff}, by {day(a.due)}
                  </p>
                </motion.li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
