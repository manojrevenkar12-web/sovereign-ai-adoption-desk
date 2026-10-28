import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const tokens = () => JSON.parse(readFileSync("e2e/.tokens.json", "utf8")) as Record<string, string>;
const open = (page: Page, path: string, who = "architect") =>
  page.goto(`${path}${path.includes("?") ? "&" : "?"}token=${tokens()[who]}`);

test("the portfolio shows each customer's path to production", async ({ page }) => {
  await open(page, "/customers/lws");
  await expect(page.getByRole("heading", { name: /Landesamt für Wohnen und Soziales/ })).toBeVisible();
  await expect(page.getByTestId("row-lws-wohngeld-auskunft")).toContainText("Go-live");
  await expect(page.getByTestId("row-lws-wohngeld-vorpruefung")).toContainText("OpenAI for Germany");
  await expect(page.getByText("Where the plan loses time")).toBeVisible();
  await page.getByRole("button", { name: /Bundesamt für Fördermittel/ }).click();
  await expect(page.getByTestId("row-bafm-hotline-stimmung")).toContainText("Stopped: prohibited");
});

test("a dossier explains the classification and the gates", async ({ page }) => {
  await open(page, "/use-cases/lws-wohngeld-vorpruefung");
  await expect(page.getByText(/High-risk under Annex III\(5\)\(a\)/)).toBeVisible();
  await expect(page.getByText("Art. 27", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Gates and dates" }).click();
  await expect(page.getByText("Fundamental rights impact assessment")).toBeVisible();
  await page.getByRole("tab", { name: "Architecture" }).click();
  await expect(page.getByText(/competent caseworker decides every case/).first()).toBeVisible();
});

test("the proof of value answers general questions and hands over the person's own case", async ({ page }) => {
  await open(page, "/use-cases/lws-wohngeld-auskunft?tab=pov");
  await expect(page.getByText("The approval covers this use case as it is classified today.")).toBeVisible();
  const box = page.getByLabel("A citizen's question");
  await box.fill("Wann ist die Servicestelle telefonisch erreichbar?");
  await page.getByRole("button", { name: "Run through the approval" }).click();
  await expect(page.getByText("Answered")).toBeVisible();
  await expect(page.getByText("WG-12#1")).toBeVisible();
  await box.fill("Habe ich mit 1400 Euro Rente Anspruch auf Wohngeld?");
  await page.getByRole("button", { name: "Run through the approval" }).click();
  await expect(page.getByText(/Handed over \(HO-/)).toBeVisible();
  await expect(page.getByText("Decided by a rule before any model call")).toBeVisible();
});

test("the Kleine Anfrage draft withholds classified records", async ({ page }) => {
  await open(page, "/use-cases/stmv-kleine-anfragen?tab=pov");
  await page.getByRole("button", { name: "Run through the approval" }).click();
  await expect(page.getByText(/1\. answered/)).toBeVisible();
  await expect(page.getByText(/2\. withheld/)).toBeVisible();
  await expect(page.getByText(/Classified passages that reached the model: 0/)).toBeVisible();
});

test("account health names the team for each intervention", async ({ page }) => {
  await open(page, "/customers/bafm/health");
  await expect(page.getByText("Watch")).toBeVisible();
  await expect(page.getByText("Prüfung has no named champion (21% active).")).toBeVisible();
  await expect(page.getByText(/Account Director, by/)).toBeVisible();
});

test("the account plan opens and closes with Escape", async ({ page }) => {
  await open(page, "/customers/stmv");
  await page.getByRole("button", { name: "Account plan" }).click();
  const plan = page.getByRole("dialog", { name: "Technical account plan" });
  await expect(plan.getByText("Decisions needed from the customer")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(plan).toBeHidden();
});

test("a customer sees only itself and cannot change the plan", async ({ page }) => {
  await open(page, "/", "customer");
  await expect(page.getByRole("heading", { name: /Landesamt für Wohnen und Soziales/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Bundesamt für Fördermittel/ })).toHaveCount(0);
  await page.goto("/use-cases/lws-wohngeld-auskunft?tab=path");
  await expect(page.getByText("Gates, in the order they start")).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark passed" })).toHaveCount(0);
  await page.goto("/use-cases/stmv-kleine-anfragen");
  await expect(page.getByText("This is not in your portfolio.")).toBeVisible();
});
