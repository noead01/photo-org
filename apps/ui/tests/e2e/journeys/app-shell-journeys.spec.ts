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
  await page.goto("/library");

  const banner = page.getByRole("banner");
  const primaryNav = page.getByRole("navigation", { name: "Primary" });

  await expect(banner).toBeVisible();
  await expect(primaryNav).toBeVisible();
  await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();
  await expectShellRoute(page, "library");

  await page.getByRole("link", { name: "Labeling", exact: true }).click();

  await expect(banner).toBeVisible();
  await expect(primaryNav).toBeVisible();
  await expect(page.getByRole("heading", { name: "Labeling", level: 1 })).toBeVisible();
  await expectShellRoute(page, "labeling");
});

test("JRN-P2-not-found-recovery @journey @smoke", async ({ page }) => {
  await page.goto("/unknown-route");

  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Page Not Found", level: 1 })).toBeVisible();
  await expectShellRoute(page, "library");

  await page.getByRole("link", { name: "Library", exact: true }).click();

  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();
  await expectShellRoute(page, "library");
});

test("JRN-P3-search-route-deep-link @journey @smoke", async ({ page }) => {
  await page.goto("/library");

  const libraryLink = page.getByRole("link", { name: "Library", exact: true });

  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();
  await expect(libraryLink).toHaveAttribute("aria-current", "page");
  await expectShellRoute(page, "library");
});

test("JRN-P2-shared-feedback-surfaces @journey @smoke", async ({ page }) => {
  let phase: "loading" | "error" | "success" = "loading";
  let releaseFirstPeopleResponse: (() => void) | null = null;
  const firstPeopleResponseGate = new Promise<void>((resolve) => {
    releaseFirstPeopleResponse = resolve;
  });

  await page.route("**/api/v1/people", async (route) => {
    if (phase === "loading") {
      await firstPeopleResponseGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([])
      });
      return;
    }

    if (phase === "error") {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Service unavailable" })
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          person_id: "person-1",
          display_name: "Ana Gomez",
          created_ts: "2026-04-20T12:00:00Z",
          updated_ts: "2026-04-20T12:00:00Z"
        }
      ])
    });
  });

  await page.goto("/labeling");
  await expect(page.getByRole("status")).toContainText(/Loading people directory/i);
  releaseFirstPeopleResponse?.();
  await expect(
    page.getByText("No people yet. Create the first person to start labeling.")
  ).toBeVisible();

  phase = "error";
  await page.goto("/labeling");
  await expect(
    page.getByRole("heading", { name: "Could not load people directory", level: 2 })
  ).toBeVisible();

  const retryButton = page.getByRole("button", { name: "Retry" });
  await expect(retryButton).toBeVisible();

  phase = "success";
  await retryButton.click();

  await expect(page.getByText("Ana Gomez")).toBeVisible();
  await expectShellRoute(page, "labeling");
  await expect(page).toHaveURL(/\/labeling(?:\?|$)/);
});

test("JRN-P2-responsive-shell-layout @journey @smoke", async ({ page }) => {
  await page.goto("/library");

  for (const viewport of RESPONSIVE_VIEWPORTS) {
    await test.step(`shell remains usable at ${viewport.label}`, async () => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await expectShellControlsReachable(page);
      await expectResponsiveNavLayout(
        page,
        viewport.expectedNavDirection,
        viewport.expectedPlacement
      );
      await expect(page).toHaveURL(/\/library$/);
      await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();
      await expectShellRoute(page, "library");
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
