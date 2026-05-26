import type { Page } from "@playwright/test";

const ADMIN_SESSION_PAYLOAD = {
  userId: "admin-user",
  displayName: "Admin User",
  email: "admin@example.com",
  roles: ["admin"],
  capabilities: {
    addToAlbum: true,
    export: true,
    reviewFaces: true,
    manageRoles: true,
    manageSources: true
  }
};

const ADMIN_SESSION_API_RESPONSE = {
  user_id: "admin-user",
  display_name: "Admin User",
  email: "admin@example.com",
  roles: ["admin"],
  capabilities: {
    add_to_album: true,
    export: true,
    review_faces: true,
    manage_roles: true,
    manage_sources: true
  }
};

export async function bootstrapAdminSession(page: Page) {
  await page.addInitScript((payload) => {
    window.__PHOTO_ORG_SESSION__ = payload;
  }, ADMIN_SESSION_PAYLOAD);

  await page.route("**/api/v1/admin/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ADMIN_SESSION_API_RESPONSE)
    });
  });
}
