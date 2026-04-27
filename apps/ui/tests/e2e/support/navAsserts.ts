import { expect, type Page } from "@playwright/test";

export async function expectPrimaryLinkActive(page: Page, label: string): Promise<void> {
  await expect(page.getByRole("link", { name: label, exact: true })).toHaveAttribute(
    "aria-current",
    "page"
  );
}
