import { expect, test, type Page } from "@playwright/test";

interface ShellViewport {
  label: string;
  width: number;
  height: number;
  expectedNavDirection: "column" | "row";
  expectedPlacement: "sidebar" | "stacked";
}

const RESPONSIVE_VIEWPORTS: ShellViewport[] = [
  {
    label: "desktop",
    width: 1366,
    height: 900,
    expectedNavDirection: "column",
    expectedPlacement: "sidebar"
  },
  {
    label: "tablet",
    width: 834,
    height: 1112,
    expectedNavDirection: "row",
    expectedPlacement: "stacked"
  },
  {
    label: "mobile",
    width: 390,
    height: 844,
    expectedNavDirection: "row",
    expectedPlacement: "stacked"
  }
];

async function expectShellRoute(page: Page, route: string) {
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", route);
}

async function expectShellControlsReachable(page: Page) {
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();

  const operationsLink = page.getByRole("link", { name: "Operations", exact: true });
  await operationsLink.scrollIntoViewIfNeeded();
  await expect(operationsLink).toBeVisible();
}

async function expectResponsiveNavLayout(
  page: Page,
  expectedDirection: "column" | "row",
  expectedPlacement: "sidebar" | "stacked"
) {
  await expect(page.locator(".shell-nav ul")).toHaveCSS("flex-direction", expectedDirection);

  const navBox = await page.getByRole("navigation", { name: "Primary" }).boundingBox();
  const mainBox = await page.getByRole("main").boundingBox();

  expect(navBox).not.toBeNull();
  expect(mainBox).not.toBeNull();

  if (!navBox || !mainBox) {
    return;
  }

  if (expectedPlacement === "sidebar") {
    expect(navBox.x + navBox.width).toBeLessThanOrEqual(mainBox.x + 2);
    return;
  }

  expect(navBox.y + navBox.height).toBeLessThanOrEqual(mainBox.y + 2);
}

test("JRN-P2-shell-navigation-continuity @journey @smoke", async ({ page }) => {
  await page.goto("/browse");

  const banner = page.getByRole("banner");
  const primaryNav = page.getByRole("navigation", { name: "Primary" });

  await expect(banner).toBeVisible();
  await expect(primaryNav).toBeVisible();
  await expect(page.getByRole("heading", { name: "Browse", level: 1 })).toBeVisible();
  await expectShellRoute(page, "browse");

  await page.getByRole("link", { name: "Search", exact: true }).click();

  await expect(banner).toBeVisible();
  await expect(primaryNav).toBeVisible();
  await expect(page.getByRole("heading", { name: "Search", level: 1 })).toBeVisible();
  await expectShellRoute(page, "search");
});

test("JRN-P2-not-found-recovery @journey @smoke", async ({ page }) => {
  await page.goto("/unknown-route");

  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Page Not Found", level: 1 })).toBeVisible();
  await expectShellRoute(page, "browse");

  await page.getByRole("link", { name: "Browse", exact: true }).click();

  await expect(page).toHaveURL(/\/browse$/);
  await expect(page.getByRole("heading", { name: "Browse", level: 1 })).toBeVisible();
  await expectShellRoute(page, "browse");
});

test("JRN-P3-search-route-deep-link @journey @smoke", async ({ page }) => {
  await page.goto("/search");

  const searchLink = page.getByRole("link", { name: "Search", exact: true });

  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Search", level: 1 })).toBeVisible();
  await expect(searchLink).toHaveAttribute("aria-current", "page");
  await expectShellRoute(page, "search");
});

test("JRN-P2-shared-feedback-surfaces @journey @smoke", async ({ page }) => {
  await page.goto("/labeling?demoState=loading");

  await expect(page.getByRole("status")).toContainText(/Loading labeling workflow/i);

  await page.goto("/labeling?demoState=error");

  const retryButton = page.getByRole("button", { name: "Retry" });
  await expect(retryButton).toBeVisible();

  await retryButton.click();

  await expect(page.getByRole("heading", { name: "Labeling", level: 1 })).toBeVisible();
  await expect(page.getByText("Labeling is ready.")).toBeVisible();
  await expectShellRoute(page, "labeling");
  await expect(page).toHaveURL(/\/labeling(?:\?|$)/);
});

test("JRN-P2-responsive-shell-layout @journey @smoke", async ({ page }) => {
  await page.goto("/search");

  for (const viewport of RESPONSIVE_VIEWPORTS) {
    await test.step(`shell remains usable at ${viewport.label}`, async () => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await expectShellControlsReachable(page);
      await expectResponsiveNavLayout(
        page,
        viewport.expectedNavDirection,
        viewport.expectedPlacement
      );
      await expect(page).toHaveURL(/\/search$/);
      await expect(page.getByRole("heading", { name: "Search", level: 1 })).toBeVisible();
      await expectShellRoute(page, "search");
    });
  }

  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Operations", level: 1 })).toBeVisible();
  await expectShellRoute(page, "operations");

  await page.setViewportSize({ width: 390, height: 844 });
  await expectShellControlsReachable(page);
  await expect(page).toHaveURL(/\/operations$/);
  await expectShellRoute(page, "operations");
});
