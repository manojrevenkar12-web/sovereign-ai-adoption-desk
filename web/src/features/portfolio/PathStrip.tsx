import { motion, useReducedMotion } from "motion/react";

import type { UseCaseSummary } from "../../shared/api/types";
import { GATE_SHORT, day } from "../../shared/format";
import { layout, motionTokens } from "../../theme/tokens";
import { strip } from "./geometry";
import s from "./portfolio.module.css";

const PX = layout.weekRem * 16;
const H = 28;

/**
 * One file's path to production: every gate as a bar on the week axis. The critical path is
 * drawn as one thread in sealing-wax red; a dotted lead-in shows weeks spent waiting for a
 * reviewer or a staff council session. Drawn once, left to right, when the board loads.
 */
export function PathStrip({ u, horizon, index }: { u: UseCaseSummary; horizon: number; index: number }) {
  const reduce = useReducedMotion();
  const g = strip(u, horizon);
  const delay = index * motionTokens.rowStagger;
  const label = u.goLive
    ? `Go-live ${day(u.goLive)}`
    : u.waitingFor
      ? `Ready ${day(u.readyBy)}, waits for ${u.waitingFor}`
      : "Not planned";
  return (
    <svg
      className={s.strip}
      width={g.width * PX}
      height={H}
      viewBox={`0 0 ${g.width * PX} ${H}`}
      role="img"
      aria-label={`${u.title}: ${label}. Critical path: ${u.critical.map((c) => GATE_SHORT[c] ?? c).join(", ")}.`}
    >
      {g.thread && (
        <motion.line
          x1={g.thread.x1 * PX}
          x2={g.thread.x2 * PX}
          y1={H / 2}
          y2={H / 2}
          className={s.thread}
          initial={reduce ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ ...motionTokens.stripDraw, delay }}
        />
      )}
      {g.bars.map((b, i) => (
        <g key={b.gate}>
          {b.waitX !== null && b.critical && (
            <line x1={b.waitX * PX} x2={b.x * PX} y1={H / 2} y2={H / 2} className={s.wait} />
          )}
          <motion.rect
            x={b.x * PX}
            y={b.critical ? H / 2 - 5 : H / 2 + 6}
            width={Math.max(b.width * PX - 1, b.done ? 3 : 2)}
            height={b.critical ? 10 : 3}
            className={b.done ? s.barDone : b.critical ? s.barCritical : s.bar}
            initial={reduce ? false : { opacity: 0, scaleX: 0 }}
            animate={{ opacity: 1, scaleX: 1 }}
            style={{ transformOrigin: `${b.x * PX}px 50%` }}
            transition={{ ...motionTokens.reveal, delay: delay + i * motionTokens.gateStagger }}
          >
            <title>{GATE_SHORT[b.gate] ?? b.gate}</title>
          </motion.rect>
        </g>
      ))}
      {g.end !== null && (
        <g className={u.waitingFor ? s.endOpen : s.end} transform={`translate(${g.end * PX} ${H / 2})`}>
          <rect x={-5} y={-5} width={10} height={10} transform="rotate(45)" />
        </g>
      )}
    </svg>
  );
}
