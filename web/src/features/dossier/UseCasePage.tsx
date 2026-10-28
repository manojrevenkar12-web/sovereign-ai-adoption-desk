import { AnimatePresence, motion } from "motion/react";

import { STAGE_LABEL, day } from "../../shared/format";
import { useDossier } from "../../shared/hooks/queries";
import { ClassMark } from "../../shared/ui/ClassMark";
import { ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/tokens";
import { PovTab } from "../pov/PovTab";
import { ArchitectureTab } from "./ArchitectureTab";
import s from "./dossier.module.css";
import { PathTab } from "./PathTab";
import { WhyTab } from "./WhyTab";

const TABS = [
  { id: "why", label: "Why this path" },
  { id: "path", label: "Gates and dates" },
  { id: "architecture", label: "Architecture" },
  { id: "pov", label: "Proof of value" },
] as const;

export function UseCasePage({ id, tab, go }: { id: string; tab: string; go: (to: string) => void }) {
  const q = useDossier(id);
  if (q.isPending) {
    return (
      <div className={s.page}>
        <Skeleton lines={10} label="Loading the use case" />
      </div>
    );
  }
  if (q.isError) {
    return (
      <div className={s.page}>
        <button type="button" className={s.back} onClick={() => go("/")}>
          Back to the portfolio
        </button>
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  }
  const d = q.data;
  const u = d.useCase;
  const cl = d.classification;
  const active = TABS.some((t) => t.id === tab) ? tab : "why";
  const when = cl.stops.length
    ? "Stopped"
    : d.path?.goLive
      ? `Go-live ${day(d.path.goLive)}`
      : d.path?.waitingFor
        ? `Ready ${day(d.path.readyBy)}, then waits for ${d.path.waitingFor}`
        : STAGE_LABEL[u.stage];
  return (
    <div className={s.page}>
      <button type="button" className={s.back} onClick={() => go(`/customers/${u.customer}`)}>
        Back to the portfolio
      </button>
      <header className={s.head}>
        <ClassMark klass={cl.aiAct.class} stopped={cl.stops.length > 0} />
        <h1 className={s.title}>{u.title}</h1>
        <p className={s.mission}>{u.mission}</p>
        <dl className={s.facts}>
          <div>
            <dt>Stage</dt>
            <dd>{STAGE_LABEL[u.stage] ?? u.stage}</dd>
          </div>
          <div>
            <dt>Owner</dt>
            <dd>{u.owner}</dd>
          </div>
          <div>
            <dt>Path</dt>
            <dd>{when}</dd>
          </div>
          <div>
            <dt>Value</dt>
            <dd>
              {d.priority
                ? `${d.priority.hoursSavedPerYear.toLocaleString("en-GB")} h a year, ${d.priority.valueBasis}`
                : "—"}
            </dd>
          </div>
        </dl>
      </header>
      <div className={s.tabs} role="tablist" aria-label="Use case">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={active === t.id}
            aria-controls={`panel-${t.id}`}
            className={active === t.id ? s.tabActive : s.tab}
            onClick={() => go(`/use-cases/${id}?tab=${t.id}`)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={active}
          role="tabpanel"
          id={`panel-${active}`}
          aria-labelledby={`tab-${active}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={motionTokens.reveal}
          className={s.panel}
        >
          {active === "why" && <WhyTab d={d} />}
          {active === "path" && <PathTab d={d} />}
          {active === "architecture" && <ArchitectureTab d={d} />}
          {active === "pov" && <PovTab d={d} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
