import { expect, test } from "@playwright/test";

import { expectPrimaryLinkActive } from "../support/navAsserts";

test("technical: deep-link query state renders expected route shell @technical", async ({ page }) => {
  await page.goto("/library?query=lake");

  await expect(page).toHaveURL(/\/library\?query=lake$/);
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", "library");
  await expectPrimaryLinkActive(page, "Library");
});

test(
  "technical: browser back and forward keep shell mounted with route-local content @technical",
  async ({ page }) => {
    await page.goto("/library");

    const banner = page.getByRole("banner");
    const primaryNav = page.getByRole("navigation", { name: "Primary" });

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();

    await page.getByRole("link", { name: "Operations", exact: true }).click();

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Operations", level: 1 })).toBeVisible();

    await page.goBack();

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();

    await page.goForward();

    await expect(banner).toBeVisible();
    await expect(primaryNav).toBeVisible();
    await expect(page.getByRole("heading", { name: "Operations", level: 1 })).toBeVisible();
  }
);

test(
  "technical: account actions are keyboard-accessible and sign-out reaches fallback state @technical",
  async ({ page }) => {
    await page.goto("/library");

    const accountButton = page.getByRole("button", { name: "Account actions" });

    await expect(accountButton).toBeVisible();
    await accountButton.focus();
    await page.keyboard.press("Enter");

    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await page.getByRole("button", { name: "Sign out" }).click();

    await expect(page.getByText("Session unavailable")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Account actions unavailable" })
    ).toBeDisabled();
  }
);
