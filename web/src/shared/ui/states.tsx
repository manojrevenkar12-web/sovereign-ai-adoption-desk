import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import s from "./ui.module.css";

export function Skeleton({ lines = 3, label = "Loading" }: { lines?: number; label?: string }) {
  return (
    <div className={s.skeleton} role="status" aria-label={label} aria-busy="true">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={s.skeletonLine} style={{ width: `${92 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  const title =
    e?.status === 401
      ? "Your session has no valid token."
      : e?.status === 0
        ? "The desk API cannot be reached."
        : e?.status === 404
          ? "This is not in your portfolio."
          : "The desk could not load this view.";
  const hint =
    e?.status === 401
      ? "Open the console with ?token=… from your identity provider, or run `desk token` in development."
      : e?.message;
  return (
    <div className={s.error} role="alert">
      <p className={s.errorTitle}>{title}</p>
      {hint && <p className={s.muted}>{hint}</p>}
      {e?.reasons.length ? (
        <ul className={s.reasons}>
          {e.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : null}
      {onRetry && (
        <button type="button" className={s.button} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className={s.empty}>
      <p className={s.emptyTitle}>{title}</p>
      {children && <div className={s.muted}>{children}</div>}
    </div>
  );
}
