import { AnimatePresence, motion } from "motion/react";
import { type ReactElement, useEffect, useRef } from "react";

import { useAccountPlan } from "../../shared/hooks/queries";
import { ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/tokens";
import s from "./portfolio.module.css";

/** Minimal Markdown for the plan the API renders: headings, lists, tables, emphasis. */
export function renderPlan(md: string): ReactElement[] {
  const out: ReactElement[] = [];
  const lines = md.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    const inline = (t: string) =>
      t.split(/(\*\*[^*]+\*\*)/g).map((p, j) => (p.startsWith("**") ? <strong key={j}>{p.slice(2, -2)}</strong> : p));
    if (l.startsWith("# ")) out.push(<h2 key={i}>{l.slice(2)}</h2>);
    else if (l.startsWith("## ")) out.push(<h3 key={i}>{l.slice(3)}</h3>);
    else if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[-| ]+\|$/.test(lines[i])) rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      i--;
      out.push(
        <div key={i} className={s.tableWrap}>
          <table>
            <thead>
              <tr>{rows[0].map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {rows.slice(1).map((r, k) => (
                <tr key={k}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else if (l.startsWith("- ") || /^\d+\. /.test(l)) out.push(<p key={i} className={s.bullet}>{inline(l.replace(/^(- |\d+\. )/, ""))}</p>);
    else if (l.startsWith("_") && l.endsWith("_")) out.push(<p key={i} className={s.muted}>{l.slice(1, -1)}</p>);
    else if (l.trim()) out.push(<p key={i}>{inline(l)}</p>);
  }
  return out;
}

export function AccountPlan({ customer, open, onClose }: { customer: string; open: boolean; onClose: () => void }) {
  const q = useAccountPlan(customer, open);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          className={s.drawer}
          role="dialog"
          aria-modal="true"
          aria-label="Technical account plan"
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={motionTokens.page}
        >
          <button ref={closeRef} type="button" className={s.close} onClick={onClose}>
            Close
          </button>
          {q.isPending ? (
            <Skeleton lines={10} label="Loading the account plan" />
          ) : q.isError ? (
            <ErrorState error={q.error} onRetry={() => q.refetch()} />
          ) : (
            <div className={s.plan}>{renderPlan(q.data)}</div>
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
