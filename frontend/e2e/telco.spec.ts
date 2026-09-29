import { expect, test, type Page } from "@playwright/test";

// Full Telco flow: sample -> schema confirmation -> analysis -> every dashboard tab.
// The LLM is faked by scripts/e2e_server.py; everything else is the real pipeline.

async function openTab(page: Page, name: string) {
  await page.getByRole("tab", { name }).click();
  await expect(page.getByRole("tab", { name })).toHaveAttribute("aria-selected", "true");
}

test("Telco sample runs end to end and every tab renders", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  await page.goto("/");
  await expect(page.getByTestId("backend-status")).toContainText("online");
  await expect(page.getByText("Use anonymised or sample data only.")).toBeVisible();
  await page.getByRole("button", { name: "Try sample data" }).click();

  await expect(page).toHaveURL(/\/analysis\/[0-9a-f]{32}$/);
  await expect(page.getByRole("heading", { name: "Confirm the columns" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("combobox", { name: /Target \(churn\) column/ })).toHaveValue("Churn");
  await page.getByRole("button", { name: "Confirm and run the analysis" }).click();

  // Data Health appears as soon as cleaning finishes, before the dashboard.
  await expect(page.getByText("Health score", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("tablist", { name: "Dashboard" })).toBeVisible({ timeout: 150_000 });

  const panel = page.getByRole("tabpanel");

  await openTab(page, "Executive Overview");
  await expect(panel.getByText("7,000", { exact: true })).toBeVisible();
  await expect(panel.getByText("25.66%", { exact: true })).toBeVisible();
  await expect(panel.getByText("Month-to-month contracts churn most")).toBeVisible();
  await expect(panel.getByText(/2\/2 AI items verified/)).toBeVisible();

  await openTab(page, "Customer Insights");
  await expect(panel.getByRole("heading", { name: "Churn rate by category" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Customer segments" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Survival curves" })).toBeVisible();

  await openTab(page, "Churn Drivers");
  await expect(panel.getByRole("heading", { name: "Model performance" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "ROC curve" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Odds ratios" })).toBeVisible();

  await openTab(page, "Hypothesis Testing");
  await expect(panel.getByText(/of \d+ significant at α = 0.05/)).toBeVisible();
  await panel.getByRole("button", { name: /Contract/ }).first().click();
  await expect(panel.locator(".katex").first()).toBeVisible();

  await openTab(page, "Risk Predictions");
  await expect(panel.locator("tbody tr").first()).toBeVisible();
  await expect(panel.getByRole("link", { name: "Download CSV" })).toHaveAttribute("href", /\/predictions\/[0-9a-f]{32}\/csv$/);
  await panel.getByRole("button", { name: /^High/ }).click();
  await expect(panel.locator("tbody tr").first()).toContainText("High");
  // Next best offer: open the first customer's offer, see why, and write a message.
  await expect(panel.getByRole("columnheader", { name: "Next best offer" })).toBeVisible();
  await panel.locator("tbody tr").first().getByRole("button").click();
  await expect(panel.getByText("Why this offer")).toBeVisible();
  await expect(panel.locator(".katex").first()).toBeVisible();
  await panel.getByRole("button", { name: "Generate message" }).click();
  await expect(panel.getByText(/^SMS \(\d+\/160\)/)).toBeVisible();
  await expect(panel.getByText(/Standard wording/)).toBeVisible();

  await openTab(page, "Recommendations");
  await expect(panel.getByText("Offer month-to-month customers a discounted annual plan.")).toBeVisible();
  await expect(panel.getByText("153.7 fewer churners")).toBeVisible();
  await expect(panel.getByRole("heading", { name: /Offer performance/ })).toBeVisible();
  await expect(panel.getByText(/riskier to begin with/)).toBeVisible();

  await openTab(page, "Data Health");
  await expect(panel.getByText("Health score", { exact: true })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
