import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { customerView, portfolio } from "../../test/fixtures";
import { mockFetch, renderWithClient } from "../../test/render";
import { renderPlan } from "./AccountPlan";
import { PortfolioPage } from "./PortfolioPage";

describe("portfolio", () => {
  it("shows a skeleton, then the board with the path and levers", async () => {
    mockFetch({ "/api/portfolio": portfolio() });
    renderWithClient(<PortfolioPage customer={null} go={() => {}} />);
    expect(screen.getByRole("status", { name: "Loading the portfolio" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Landesamt (fictional)" })).toBeInTheDocument();
    expect(screen.getByText("Go-live 15 Mar 2027")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Critical path: Legal basis, DPIA, Pilot, Go-live/ })).toBeInTheDocument();
    expect(screen.getByText("−4 wk")).toBeInTheDocument();
  });

  it("opens a use case from the board", async () => {
    mockFetch({ "/api/portfolio": portfolio() });
    const go = vi.fn();
    renderWithClient(<PortfolioPage customer="lws" go={go} />);
    await userEvent.click(await screen.findByRole("button", { name: "Wohngeld enquiry assistant" }));
    expect(go).toHaveBeenCalledWith("/use-cases/uc-1");
  });

  it("explains a missing token instead of failing silently", async () => {
    mockFetch({ "/api/portfolio": { detail: "token carries no desk role" } }, { "/api/portfolio": 401 });
    renderWithClient(<PortfolioPage customer={null} go={() => {}} />);
    expect(await screen.findByText("Your session has no valid token.")).toBeInTheDocument();
  });

  it("offers a retry when the API is down", async () => {
    let calls = 0;
    globalThis.fetch = vi.fn(async () => {
      calls += 1;
      if (calls === 1) throw new TypeError("network");
      return new Response(JSON.stringify(portfolio()), { headers: { "content-type": "application/json" } });
    }) as typeof fetch;
    renderWithClient(<PortfolioPage customer={null} go={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Landesamt (fictional)" })).toBeInTheDocument();
  });

  it("says what to do when the portfolio is empty", async () => {
    mockFetch({ "/api/portfolio": { customers: [], today: "2026-10-28", role: "architect" } });
    renderWithClient(<PortfolioPage customer={null} go={() => {}} />);
    expect(await screen.findByText("No customers in your portfolio")).toBeInTheDocument();
  });

  it("says when a customer has no use cases yet", async () => {
    mockFetch({ "/api/portfolio": { ...portfolio(), customers: [customerView({ useCases: [] })] } });
    renderWithClient(<PortfolioPage customer={null} go={() => {}} />);
    expect(await screen.findByText("No use cases yet")).toBeInTheDocument();
  });

  it("renders the account plan's tables and emphasis", () => {
    const { container } = renderWithClientless(renderPlan("# Plan\n\n| a | b |\n|---|---|\n| 1 | 2 |\n- **x** y"));
    expect(container.querySelector("table td")?.textContent).toBe("1");
    expect(container.querySelector("strong")?.textContent).toBe("x");
  });
});

import { render } from "@testing-library/react";
function renderWithClientless(nodes: React.ReactElement[]) {
  return render(<div>{nodes}</div>);
}
