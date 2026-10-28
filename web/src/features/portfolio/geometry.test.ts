import { useCase } from "../../test/fixtures";
import { horizonFor, monthTicks, strip } from "./geometry";

describe("path strip geometry", () => {
  it("draws the critical path from its first gate to go-live", () => {
    const g = strip(useCase(), 40);
    expect(g.thread).toEqual({ x1: 0, x2: 18 });
    expect(g.end).toBe(18);
    expect(g.bars.find((b) => b.gate === "dpia")).toMatchObject({ x: 4, width: 6, critical: true, waitX: 2 });
    expect(g.bars.some((b) => b.gate === "go_live")).toBe(false);
  });

  it("clips everything to the horizon", () => {
    const g = strip(useCase(), 12);
    expect(g.bars.every((b) => b.x + b.width <= 12)).toBe(true);
    expect(g.end).toBe(12);
  });

  it("has no thread when nothing is planned", () => {
    expect(strip(useCase({ gates: [], critical: [] }), 40)).toMatchObject({ thread: null, end: null });
  });

  it("sizes the horizon to the latest gate plus a margin, within bounds", () => {
    expect(horizonFor([useCase()])).toBe(40);
    const long = useCase({ gates: [{ gate: "go_live", startWeek: 90, endWeek: 90, done: false, wait: null, waitedWeeks: 0 }] });
    expect(horizonFor([long])).toBe(94);
    expect(horizonFor([long], 40, 60)).toBe(60);
  });

  it("labels each month once", () => {
    const ticks = monthTicks("2026-11-02", 10);
    expect(ticks.map((t) => t.label)).toEqual(["Nov 26", "Dec 26", "Jan 27"]);
    expect(ticks[0].week).toBe(0);
  });
});
