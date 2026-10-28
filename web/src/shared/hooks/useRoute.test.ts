import { parse } from "./useRoute";

describe("routes", () => {
  it("parses the three screens", () => {
    expect(parse("/")).toEqual({ name: "portfolio", customer: null });
    expect(parse("/customers/lws")).toEqual({ name: "portfolio", customer: "lws" });
    expect(parse("/customers/lws/health")).toEqual({ name: "health", customer: "lws" });
    expect(parse("/use-cases/lws-wohngeld-auskunft", "?tab=pov")).toEqual({ name: "useCase", id: "lws-wohngeld-auskunft", tab: "pov" });
    expect(parse("/use-cases/x")).toMatchObject({ tab: "why" });
  });
});
