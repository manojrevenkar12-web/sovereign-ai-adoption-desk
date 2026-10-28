import type { CustomerView } from "../../shared/api/types";
import s from "./portfolio.module.css";

const BAND: Record<string, string> = { healthy: "Healthy", watch: "Watch", at_risk: "At risk" };

export function CustomerRail({
  customers,
  selected,
  onSelect,
}: {
  customers: CustomerView[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <nav className={s.rail} aria-label="Customers">
      {customers.map((c) => {
        const open = c.useCases.filter((u) => !u.stops.length && !["production", "adopted", "not_pursued"].includes(u.stage));
        const noUsage = c.health.activation === null;
        return (
          <button
            key={c.customer.id}
            type="button"
            className={`${s.railItem} ${selected === c.customer.id ? s.railActive : ""}`}
            aria-current={selected === c.customer.id ? "page" : undefined}
            onClick={() => onSelect(c.customer.id)}
          >
            <span className={s.railName}>{c.customer.name.replace(" (fictional)", "")}</span>
            <span className={s.railFacts}>
              <span data-band={c.health.band} className={s.band}>
                {c.health.score} {noUsage ? "· no usage yet" : `· ${BAND[c.health.band]}`}
              </span>
              <span>{open.length} open</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
