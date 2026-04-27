import { expect, test, type Page } from "@playwright/test";

async function expectShellRoute(page: Page, route: string) {
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", route);
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
