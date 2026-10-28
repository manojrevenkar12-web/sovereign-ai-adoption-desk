import { motion } from "motion/react";
import { useState } from "react";

import { day } from "../../shared/format";
import { usePortfolio } from "../../shared/hooks/queries";
import { EmptyState, ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/tokens";
import { AccountPlan } from "./AccountPlan";
import { CustomerRail } from "./CustomerRail";
import { LeversPanel } from "./LeversPanel";
import { PathBoard } from "./PathBoard";
import s from "./portfolio.module.css";

export function PortfolioPage({ customer, go }: { customer: string | null; go: (to: string) => void }) {
  const q = usePortfolio();
  const [planOpen, setPlanOpen] = useState(false);
  if (q.isPending) {
    return (
      <div className={s.page}>
        <Skeleton lines={8} label="Loading the portfolio" />
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
  const customers = q.data.customers;
  if (!customers.length) {
    return (
      <div className={s.page}>
        <EmptyState title="No customers in your portfolio">
          Your token names no customer. Ask the Account Director to add you to the account team.
        </EmptyState>
      </div>
    );
  }
  const view = customers.find((c) => c.customer.id === customer) ?? customers[0];
  const c = view.customer;
  return (
    <div className={s.layout}>
      <CustomerRail customers={customers} selected={c.id} onSelect={(id) => go(`/customers/${id}`)} />
      <motion.main
        key={c.id}
        className={s.main}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={motionTokens.page}
      >
        <header className={s.head}>
          <div>
            <h1 className={s.name}>{c.name}</h1>
            <p className={s.context}>
              {c.level === "bund" ? "Federal authority" : c.level === "land" ? "State authority" : "Municipality"}, planned
              from {day(view.planStart)}
            </p>
            <ul className={s.missions}>
              {c.mission_priorities.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
          <div className={s.actions}>
            <button type="button" className={s.action} onClick={() => go(`/customers/${c.id}/health`)}>
              Account health {view.health.score}
            </button>
            <button type="button" className={s.actionPrimary} onClick={() => setPlanOpen(true)}>
              Account plan
            </button>
          </div>
        </header>
        <div className={s.grid}>
          <section aria-labelledby="board-h">
            <h2 id="board-h" className={s.boardTitle}>
              Path to production
            </h2>
            <p className={s.legend}>
              <span className={s.legendThread}>critical path</span>
              <span className={s.legendWait}>waiting for a reviewer or a session</span>
              <span className={s.legendDone}>passed</span>
            </p>
            <PathBoard view={view} onOpen={(id) => go(`/use-cases/${id}`)} />
          </section>
          <LeversPanel view={view} />
        </div>
      </motion.main>
      <AccountPlan customer={c.id} open={planOpen} onClose={() => setPlanOpen(false)} />
    </div>
  );
}
