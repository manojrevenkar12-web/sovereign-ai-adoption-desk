// Values the components need in code. Colours stay in CSS variables so both themes work.

export const motionTokens = {
  // the one orchestrated moment: path strips are drawn left to right, row after row
  stripDraw: { duration: 0.7, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
  rowStagger: 0.06,
  gateStagger: 0.035,
  page: { duration: 0.22, ease: [0.4, 0, 0.2, 1] as [number, number, number, number] },
  reveal: { duration: 0.28, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
} as const;

export const layout = {
  weekRem: 0.95,
  horizonWeeks: 70,
  maxRows: 40,
} as const;

export const folderVar: Record<string, string> = {
  high_risk: "var(--folder-high)",
  transparency: "var(--folder-transparency)",
  not_high_risk: "var(--folder-derogation)",
  minimal: "var(--folder-minimal)",
  prohibited: "var(--folder-prohibited)",
};
