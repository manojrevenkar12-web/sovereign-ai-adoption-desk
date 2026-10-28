import { motion, useReducedMotion } from "motion/react";

import type { Health } from "../../shared/api/types";
import { month, pct } from "../../shared/format";
import { motionTokens } from "../../theme/tokens";
import s from "./health.module.css";

const W = 560;
const H = 140;
const PAD = 24;

/** Share of seats active each week; the target is drawn so the gap is visible at a glance. */
export function Trend({ trend, target }: { trend: Health["trend"]; target: number }) {
  const reduce = useReducedMotion();
  const pts = trend.filter((t) => t.activation !== null) as { week: string; activation: number }[];
  if (pts.length < 2) return null;
  const max = Math.max(target, ...pts.map((p) => p.activation)) * 1.1;
  const x = (i: number) => PAD + (i * (W - 2 * PAD)) / (pts.length - 1);
  const y = (v: number) => H - PAD - (v / max) * (H - 2 * PAD);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.activation).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];
  return (
    <svg
      className={s.trend}
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Weekly activation from ${pct(pts[0].activation)} to ${pct(last.activation)}; target ${pct(target)}.`}
    >
      <line x1={PAD} x2={W - PAD} y1={y(target)} y2={y(target)} className={s.target} />
      <text x={W - PAD} y={y(target) - 6} textAnchor="end" className={s.axisText}>
        target {pct(target)}
      </text>
      <motion.path
        d={d}
        className={s.line}
        initial={reduce ? false : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={motionTokens.stripDraw}
      />
      <circle cx={x(pts.length - 1)} cy={y(last.activation)} r={4} className={s.dot} />
      <text x={PAD} y={H - 4} className={s.axisText}>
        {month(pts[0].week)}
      </text>
      <text x={W - PAD} y={H - 4} textAnchor="end" className={s.axisText}>
        {month(last.week)}
      </text>
    </svg>
  );
}
