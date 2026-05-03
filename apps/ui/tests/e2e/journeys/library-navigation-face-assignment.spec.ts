import { expect, test } from "@playwright/test";

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
          thumbnail: {
            mime_type: "image/jpeg",
            width: 100,
            height: 100,
            data_base64: "dGh1bWI="
          },
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

function buildPhotoDetailPayload(photoId: string) {
  return {
    photo_id: photoId,
    path: `/library/${photoId}.jpg`,
    ext: "jpg",
    camera_make: "Apple",
    orientation: "Rotate 90 CW",
    shot_ts: "2026-03-28T19:30:00Z",
    filesize: 4096,
    tags: ["vacation"],
    people: [],
    faces: [
      {
        face_id: "face-1",
        person_id: null,
        bbox_x: 10,
        bbox_y: 20,
        bbox_w: 30,
        bbox_h: 40,
        bbox_space_width: null,
        bbox_space_height: null,
        label_source: null,
        confidence: null,
        model_version: null,
        provenance: null,
        label_recorded_ts: null
      }
    ],
    thumbnail: {
      mime_type: "image/jpeg",
      width: 100,
      height: 100,
      data_base64: "dGh1bWI="
    },
    original: {
      is_available: true,
      availability_state: "active",
      last_failure_reason: null
    },
    metadata: {
      sha256: "sha-1",
      phash: "phash-1",
      shot_ts_source: "exif_ifd:DateTimeOriginal",
      camera_model: "iPhone 15 Pro",
      software: "18.1",
      gps_latitude: 12.3456,
      gps_longitude: -45.6789,
      gps_altitude: 123.4,
      exif_attributes: {
        "exif.DateTime": "2026:03:28 19:30:00",
        "exif_ifd.DateTimeOriginal": "2026:03:28 19:30:00"
      },
      created_ts: "2026-03-28T19:30:00Z",
      updated_ts: "2026-03-28T19:30:00Z",
      modified_ts: "2026-03-28T19:30:00Z",
      deleted_ts: null,
      faces_count: 1,
      faces_detected_ts: "2026-03-28T19:30:00Z"
    }
  };
}

test("JRN-P4-library-navigation-state-persists-through-detail @journey", async ({ page }) => {
  await page.route("**/api/v1/operations/activity", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ingest_queue: {
          summary: {
            processing_count: 0
          }
        }
      })
    });
  });

  await page.route("**/api/v1/people", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([])
    });
  });

  await page.route("**/api/v1/search", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildSearchPayload("photo-1"))
    });
  });

  await page.route("**/api/v1/photos/photo-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildPhotoDetailPayload("photo-1"))
    });
  });
  await page.route("**/api/v1/photos/*/original", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "text/plain",
      body: "not found"
    });
  });

  await page.goto("/library");
  await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "View details", exact: true }).click();

  await expect(page).toHaveURL(/\/library\/photo-1$/);
  await expect(page.getByRole("heading", { name: "Photo detail", level: 1 })).toBeVisible();

  const backLink = page.getByRole("link", { name: "Back to library" });
  await expect(backLink).toHaveAttribute("href", /\/library(?:\?.*)?$/);
  await backLink.click();

  await expect(page).toHaveURL(/\/library(?:\?.*)?$/);
  await expect(page.getByRole("heading", { name: "Library", level: 1 })).toBeVisible();
});

test("JRN-P4-detail-face-assignment-from-suggestions @journey", async ({ page }) => {
  let assignmentRequestBody: unknown = null;
  let assignmentRoleHeader: string | undefined;

  await page.route("**/api/v1/operations/activity", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ingest_queue: {
          summary: {
            processing_count: 0
          }
        }
      })
    });
  });

  await page.route("**/api/v1/people", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          person_id: "person-1",
          display_name: "Inez",
          created_ts: "2026-03-28T19:30:00Z",
          updated_ts: "2026-03-28T19:30:00Z"
        }
      ])
    });
  });

  await page.route("**/api/v1/search", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildSearchPayload("photo-1"))
    });
  });

  await page.route("**/api/v1/photos/photo-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildPhotoDetailPayload("photo-1"))
    });
  });
  await page.route("**/api/v1/photos/*/original", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "text/plain",
      body: "not found"
    });
  });

  await page.route("**/api/v1/faces/face-1/candidates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        face_id: "face-1",
        candidates: [
          {
            person_id: "person-1",
            display_name: "Inez",
            matched_face_id: "face-7",
            distance: 0.09,
            confidence: 0.87
          }
        ]
      })
    });
  });

  await page.route("**/api/v1/faces/face-1/assignments", async (route) => {
    assignmentRequestBody = route.request().postDataJSON();
    assignmentRoleHeader = route.request().headers()["x-face-validation-role"];
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        face_id: "face-1",
        photo_id: "photo-1",
        person_id: "person-1"
      })
    });
  });

  await page.goto("/library");
  await page.getByRole("link", { name: "View details", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Photo detail", level: 1 })).toBeVisible();
  const assignmentTrigger = page.getByRole("button", {
    name: "Open face assignment for face region 1"
  });
  await expect(assignmentTrigger).toHaveText("?");

  await assignmentTrigger.click();
  await expect(page.getByRole("dialog", { name: "Face assignment" })).toBeVisible();
  await page.getByRole("button", { name: "Inez (87.0%)" }).click();
  await page.getByRole("button", { name: "Save and close" }).click();

  await expect(page.getByRole("dialog", { name: "Face assignment" })).not.toBeVisible();
  await expect(assignmentTrigger).toHaveText("IN");
  expect(assignmentRoleHeader).toBe("contributor");
  expect(assignmentRequestBody).toEqual({ person_id: "person-1" });
});
