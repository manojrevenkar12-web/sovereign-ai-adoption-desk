import type { Dossier } from "../../shared/api/types";
import { day, humanise, target } from "../../shared/format";
import s from "./dossier.module.css";

const KIND: Record<string, string> = {
  ai_act: "AI Act",
  gdpr: "Data protection",
  secrecy: "Secrecy",
  staff: "Staff council",
  accessibility: "Accessibility",
  procurement: "Procurement",
};

export function WhyTab({ d }: { d: Dossier }) {
  const cl = d.classification;
  const groups = Object.entries(
    cl.duties.reduce<Record<string, typeof cl.duties>>((acc, x) => {
      (acc[x.kind] ??= []).push(x);
      return acc;
    }, {}),
  );
  return (
    <div className={s.two}>
      <section aria-labelledby="reasons-h">
        <h2 id="reasons-h" className={s.h2}>
          The reasoning, in order
        </h2>
        {cl.stops.length > 0 && (
          <div className={s.stop} role="note">
            {cl.stops.map((x) => (
              <p key={x.stop}>{x.reason}</p>
            ))}
          </div>
        )}
        <ol className={s.reasons}>
          {cl.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ol>
        <dl className={s.kv}>
          <div>
            <dt>Hosting</dt>
            <dd>
              {target(cl.hosting.chosen)}
              {cl.hosting.status && cl.hosting.status !== "available" ? ` (${cl.hosting.status})` : ""}
              {cl.hosting.underContract ? ", under contract" : ""}
            </dd>
          </div>
          <div>
            <dt>Procurement</dt>
            <dd>{cl.procurementRoute ? humanise(cl.procurementRoute) : "not needed"}</dd>
          </div>
          <div>
            <dt>DPIA</dt>
            <dd>{cl.gdpr.dpiaRequired ? `needed: ${cl.gdpr.dpiaCriteria.map(humanise).join(", ")}` : "not needed"}</dd>
          </div>
        </dl>
      </section>
      <section aria-labelledby="duties-h">
        <h2 id="duties-h" className={s.h2}>
          Duties and when they apply
        </h2>
        {groups.map(([kind, items]) => (
          <div key={kind} className={s.dutyGroup}>
            <h3 className={s.h3}>{KIND[kind] ?? kind}</h3>
            <ul className={s.duties}>
              {items.map((x) => (
                <li key={`${x.article}-${x.text}`}>
                  <span className={s.article}>{x.article}</span>
                  <span>{x.text}</span>
                  {x.appliesFrom && <span className={s.from}>from {day(x.appliesFrom)}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}
