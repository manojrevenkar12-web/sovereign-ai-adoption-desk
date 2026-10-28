import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { dossier, portfolio } from "../../test/fixtures";
import { mockFetch, renderWithClient } from "../../test/render";
import { UseCasePage } from "./UseCasePage";

describe("use case dossier", () => {
  it("explains the classification with its articles and dates", async () => {
    mockFetch({ "/api/use-cases/uc-1": dossier(), "/api/portfolio": portfolio() });
    renderWithClient(<UseCasePage id="uc-1" tab="why" go={() => {}} />);
    expect(await screen.findByRole("heading", { name: "Wohngeld enquiry assistant" })).toBeInTheDocument();
    expect(screen.getByText(/Citizens talk to it directly/)).toBeInTheDocument();
    expect(screen.getByText("from 2 Aug 2026")).toBeInTheDocument();
    expect(screen.getByText("OpenAI API, EU data residency, under contract")).toBeInTheDocument();
  });

  it("lets the architect pass a gate, which replans", async () => {
    const d = dossier();
    const passed = structuredClone(d);
    passed.useCase.done = ["pov", "legal_basis"];
    passed.path!.gates[0].done = true;
    const calls = mockFetch({
      "/api/use-cases/uc-1/gates/legal_basis": passed,
      "/api/use-cases/uc-1": d,
      "/api/portfolio": portfolio(),
    });
    renderWithClient(<UseCasePage id="uc-1" tab="path" go={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Mark passed" }));
    expect(await screen.findByText("Passed")).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/gates/legal_basis") && c.init?.method === "POST")).toBe(true);
  });

  it("runs the proof of value through the approval and shows who decided", async () => {
    mockFetch({
      "/api/use-cases/uc-1/pov": {
        action: "handover", text: "…", statements: [], reason: "individual_eligibility", decidedBy: "rule",
        ticket: "HO-00001", toolsCalled: [], retrieved: [], violations: [], identifiersSeenByModel: 0,
      },
      "/api/use-cases/uc-1": dossier(),
      "/api/portfolio": portfolio(),
    });
    renderWithClient(<UseCasePage id="uc-1" tab="pov" go={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Run through the approval" }));
    expect(await screen.findByText(/Handed over \(HO-00001\)/)).toBeInTheDocument();
    expect(screen.getByText("Decided by a rule before any model call")).toBeInTheDocument();
  });

  it("refuses to run when the approval no longer covers the use case", async () => {
    const d = dossier();
    d.approval!.problems = ["approval APR-1 expired on 2027-04-30"];
    mockFetch({ "/api/use-cases/uc-1": d, "/api/portfolio": portfolio() });
    renderWithClient(<UseCasePage id="uc-1" tab="pov" go={() => {}} />);
    expect(await screen.findByText("The agent will not run:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run through the approval" })).toBeDisabled();
  });

  it("shows a not-found state for a use case outside the portfolio", async () => {
    mockFetch({ "/api/portfolio": portfolio() });
    renderWithClient(<UseCasePage id="other" tab="why" go={() => {}} />);
    expect(await screen.findByText("This is not in your portfolio.")).toBeInTheDocument();
  });
});
