import { expect, test } from "@playwright/test";

type SearchRequestPayload = {
  q?: string;
};

function buildSearchPayload(photoId: string) {
  return {
    hits: {
      total: 1,
      cursor: null,
      items: [
        {
          photo_id: photoId,
          path: `/library/${photoId}.jpg`,
          ext: "jpg",
          camera_make: "Canon",
          orientation: "landscape",
          shot_ts: "2026-04-20T12:00:00Z",
          filesize: 1024,
          tags: [],
          people: [],
          faces: [],
          thumbnail: null,
          original: {
            is_available: true,
            availability_state: "available",
            last_failure_reason: null
          },
          relevance: null
        }
      ]
    },
    facets: {}
  };
}

test("JRN-P4-library-shared-request-lifecycle @journey", async ({ page }) => {
  let releaseGateResolver: (() => void) | null = null;
  const initialBrowseRequestGate = new Promise<void>((resolve) => {
    releaseGateResolver = resolve;
  });
  let initialRequestsReleased = false;
  let failNextBrowseRequest = false;

  await page.route("**/api/v1/search", async (route) => {
    const body = (route.request().postDataJSON() ?? {}) as SearchRequestPayload;
    if (typeof body.q === "string") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildSearchPayload("search-photo-ignored"))
      });
      return;
    }

    if (!initialRequestsReleased) {
      await initialBrowseRequestGate;
    }

    if (failNextBrowseRequest) {
      failNextBrowseRequest = false;
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
      body: JSON.stringify(buildSearchPayload("browse-photo-1"))
    });
  });

  await page.goto("/library");
  await expect(page.getByRole("status")).toContainText("Loading library workflow.");

  initialRequestsReleased = true;
  releaseGateResolver?.();
  await expect(page.getByRole("link", { name: "View details" })).toBeVisible();
  await expect(page.getByText("/library/browse-photo-1.jpg")).toBeVisible();

  failNextBrowseRequest = true;
  await page.selectOption('select[aria-label="Sort order"]', "asc");
  await expect(page.getByRole("heading", { name: "Could not load Library", level: 2 })).toBeVisible();

  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("link", { name: "View details" })).toBeVisible();
});

test("JRN-P4-library-invalid-page-reset @journey", async ({ page }) => {
  await page.route("**/api/v1/search", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildSearchPayload("browse-photo-2"))
    });
  });

  await page.goto("/library?page=3");

  await expect(
    page.getByText("Reset to page 1 because that page position is unavailable.")
  ).toBeVisible();
  await expect(page.locator(".browse-page-indicator")).toHaveText("Page 1");
  await expect(page).toHaveURL(/\/library$/);
});

test("JRN-P4-library-filtered-shared-request-lifecycle @journey", async ({ page }) => {
  let releaseFirstSearchResponse: (() => void) | null = null;
  const firstSearchResponseGate = new Promise<void>((resolve) => {
    releaseFirstSearchResponse = resolve;
  });
  let searchRequestCount = 0;

  await page.route("**/api/v1/people", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([])
    });
  });

  await page.route("**/api/v1/search", async (route) => {
    const body = (route.request().postDataJSON() ?? {}) as SearchRequestPayload;
    if (typeof body.q !== "string") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildSearchPayload("browse-photo-ignored"))
      });
      return;
    }

    searchRequestCount += 1;
    if (searchRequestCount === 1) {
      await firstSearchResponseGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildSearchPayload("search-photo-1"))
      });
      return;
    }

    if (searchRequestCount === 2) {
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
      body: JSON.stringify(buildSearchPayload("search-photo-1"))
    });
  });

  await page.goto("/library");

  await page.getByRole("textbox", { name: "Search query" }).fill("lake");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("Loading library workflow.");

  releaseFirstSearchResponse?.();
  await expect(page.getByRole("link", { name: "View details" })).toBeVisible();
  await expect(page.getByText("/library/search-photo-1.jpg")).toBeVisible();

  await page.getByRole("textbox", { name: "Search query" }).fill("coast");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Could not load Library", level: 2 })).toBeVisible();

  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("link", { name: "View details" })).toBeVisible();
});
