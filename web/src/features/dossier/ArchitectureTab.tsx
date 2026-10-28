import type { Dossier } from "../../shared/api/types";
import { EmptyState } from "../../shared/ui/states";
import s from "./dossier.module.css";

const LAYER: Record<string, string> = {
  channel: "Channel",
  model: "Model and hosting",
  data: "Data and integration",
  identity: "Identity",
  security: "Security",
  privacy: "Privacy",
  governance: "Governance",
  evaluation: "Evaluation",
  operations: "Operations",
};

export function ArchitectureTab({ d }: { d: Dossier }) {
  const a = d.architecture;
  if (!a) {
    return <EmptyState title="No architecture for a stopped use case">Resolve the stop first.</EmptyState>;
  }
  return (
    <div className={s.two}>
      <section aria-labelledby="layers-h">
        <h2 id="layers-h" className={s.h2}>
          One choice per layer
        </h2>
        <dl className={s.layers}>
          {a.components.map((c, i) => (
            <div key={`${c.layer}-${i}`} className={s.layer}>
              <dt>{LAYER[c.layer] ?? c.layer}</dt>
              <dd>
                <strong>{c.choice}</strong>
                <span>{c.why}</span>
                {c.rejected && <span className={s.rejected}>Not: {c.rejected}</span>}
              </dd>
            </div>
          ))}
        </dl>
      </section>
      <section aria-labelledby="decisions-h">
        <h2 id="decisions-h" className={s.h2}>
          Decisions with a trade-off
        </h2>
        {a.decisions.length === 0 ? (
          <p className={s.lead}>No decision here carries a trade-off worth a workshop.</p>
        ) : (
          a.decisions.map((x) => (
            <article key={x.question} className={s.decision}>
              <h3 className={s.h3}>{x.question}</h3>
              <p>
                <strong>{x.choice}.</strong> {x.tradeOff}
              </p>
            </article>
          ))
        )}
        <details className={s.mermaid}>
          <summary>Diagram source (Mermaid)</summary>
          <pre>{a.mermaid}</pre>
        </details>
      </section>
    </div>
  );
}
