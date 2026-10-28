import { AnimatePresence, motion } from "motion/react";
import { type FormEvent, useState } from "react";

import type { Dossier, DraftResult, EnquiryResult } from "../../shared/api/types";
import { day, humanise, target } from "../../shared/format";
import { useAsk } from "../../shared/hooks/queries";
import { EmptyState, ErrorState } from "../../shared/ui/states";
import { motionTokens } from "../../theme/tokens";
import s from "./pov.module.css";

const EXAMPLE: Record<string, string> = {
  wohngeld: "Welche Unterlagen brauche ich für den Wohngeldantrag?",
  kleine_anfrage:
    "Kleine Anfrage zum Einsatz von KI\n1. Wie viele KI-Pilotprojekte gibt es in der Staatsverwaltung?\n2. Wie viele Sicherheitsvorfälle gab es 2026?",
};

const DECIDED: Record<string, string> = {
  rule: "Decided by a rule before any model call",
  agent: "Decided by the agent",
  guardrail: "Stopped by the output check",
};

function isEnquiry(r: EnquiryResult | DraftResult): r is EnquiryResult {
  return "action" in r;
}

export function PovTab({ d }: { d: Dossier }) {
  const ask = useAsk(d.useCase.id);
  const [text, setText] = useState(EXAMPLE[d.useCase.pov] ?? "");
  const a = d.approval;
  if (!d.useCase.pov || !a) {
    return (
      <EmptyState title="No proof of value yet">
        A proof of value runs once the customer approves its scope: target, data, tools, oversight and an expiry.
      </EmptyState>
    );
  }
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) ask.mutate(text.trim());
  };
  return (
    <div className={s.layout}>
      <section aria-labelledby="scope-h" className={s.scope}>
        <h2 id="scope-h" className={s.h2}>
          What the approval allows
        </h2>
        <p className={s.small}>
          {a.id}, version {a.version}, approved by {a.approved_by.join(", ")}, valid until {day(a.valid_until)}.
        </p>
        <dl className={s.kv}>
          <div>
            <dt>Target</dt>
            <dd>{target(a.target)}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{a.model}</dd>
          </div>
          <div>
            <dt>Tools</dt>
            <dd>{a.tools.join(", ")}</dd>
          </div>
          <div>
            <dt>Highest document class</dt>
            <dd>{humanise(a.document_ceiling)}</dd>
          </div>
          <div>
            <dt>Oversight</dt>
            <dd>{humanise(a.oversight)}</dd>
          </div>
        </dl>
        {a.problems.length > 0 ? (
          <div className={s.problems} role="alert">
            <p>The agent will not run:</p>
            <ul>
              {a.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className={s.ok}>The approval covers this use case as it is classified today.</p>
        )}
      </section>
      <section aria-labelledby="ask-h">
        <h2 id="ask-h" className={s.h2}>
          Ask it
        </h2>
        <form onSubmit={submit} className={s.form}>
          <label htmlFor="ask" className={s.label}>
            {d.useCase.pov === "wohngeld" ? "A citizen's question" : "A Kleine Anfrage with numbered questions"}
          </label>
          <textarea id="ask" rows={4} value={text} onChange={(e) => setText(e.target.value)} className={s.input} />
          <button type="submit" className={s.send} disabled={ask.isPending || a.problems.length > 0}>
            {ask.isPending ? "Running…" : "Run through the approval"}
          </button>
        </form>
        {ask.isError && <ErrorState error={ask.error} onRetry={() => text.trim() && ask.mutate(text.trim())} />}
        <AnimatePresence mode="wait">
          {ask.data && (
            <motion.div
              key={JSON.stringify(ask.data).length}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={motionTokens.reveal}
              className={s.result}
              aria-live="polite"
            >
              {isEnquiry(ask.data) ? <Enquiry r={ask.data} /> : <Draft r={ask.data} />}
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </div>
  );
}

function Enquiry({ r }: { r: EnquiryResult }) {
  return (
    <>
      <p className={r.action === "answer" ? s.verdictAnswer : s.verdictHandover}>
        {r.action === "answer" ? "Answered" : `Handed over${r.ticket ? ` (${r.ticket})` : ""}`}
        <span>{DECIDED[r.decidedBy]}</span>
      </p>
      {r.statements.length > 0 ? (
        <ol className={s.statements}>
          {r.statements.map((x) => (
            <li key={x.text}>
              {x.text} <span className={s.cite}>{x.citations.join(", ")}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p>{r.text.split("\n\n").slice(-1)[0]}</p>
      )}
      <p className={s.small}>
        Identifiers seen by the model: {r.identifiersSeenByModel}. Tools called: {r.toolsCalled.join(", ") || "none"}.
        {r.reason ? ` Reason: ${humanise(r.reason)}.` : ""}
      </p>
    </>
  );
}

function Draft({ r }: { r: DraftResult }) {
  return (
    <>
      <p className={s.small}>{r.disclosure}</p>
      <ol className={s.statements}>
        {r.answers.map((a) => (
          <li key={a.question}>
            <strong>
              {a.question}. {humanise(a.status)}
            </strong>{" "}
            {a.statements.map((x) => (
              <span key={x.text}>
                {x.text} <span className={s.cite}>{x.citations.join(", ")}</span>{" "}
              </span>
            ))}
          </li>
        ))}
      </ol>
      <p className={s.small}>
        Co-sign: {r.coSignUnits.join("; ") || "nobody yet"}. Classified documents withheld: {r.withheldDocuments}.
        Classified passages that reached the model: {r.ceilingBreaches.length}.
      </p>
    </>
  );
}
