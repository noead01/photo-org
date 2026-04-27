import { expect, test } from "@playwright/test";

import { expectPrimaryLinkActive } from "../support/navAsserts";

test("technical: deep-link query state renders expected route shell @technical", async ({ page }) => {
  await page.goto("/search?query=lake");

  await expect(page).toHaveURL(/\/search\?query=lake$/);
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", "search");
  await expectPrimaryLinkActive(page, "Search");
});

test(
  "technical: browser back and forward keep shell mounted with route-local content @technical",
  async ({ page }) => {
    await page.goto("/browse");

    const banner = page.getByRole("banner");
    const primaryNav = page.getByRole("navigation", { name: "Primary" });

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Browse", level: 1 })).toBeVisible();

    await page.getByRole("link", { name: "Operations", exact: true }).click();

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Operations", level: 1 })).toBeVisible();

    await page.goBack();

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Browse", level: 1 })).toBeVisible();

    await page.goForward();

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Operations", level: 1 })).toBeVisible();
  }
);
