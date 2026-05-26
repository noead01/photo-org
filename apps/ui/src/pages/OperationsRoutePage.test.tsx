import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OperationsRoutePage } from "./OperationsRoutePage";
import type { SessionIdentity } from "../session/sessionIdentity";

const ADMIN_SESSION: SessionIdentity = {
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

describe("OperationsRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("blocks non-admin sessions from role management", () => {
    render(
      <OperationsRoutePage
        sessionIdentity={{
          ...ADMIN_SESSION,
          roles: ["viewer"],
          capabilities: {
            ...ADMIN_SESSION.capabilities,
            manageRoles: false,
            manageSources: false,
            reviewFaces: false
          }
        }}
      />
    );

    expect(screen.getByRole("heading", { name: "Admin access required", level: 2 })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("loads users and saves updated role assignments", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/admin/users" && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => [
            {
              user_id: "viewer-user",
              auth_provider: "cloudflare_access",
              auth_subject: "viewer@example.com",
              email: "viewer@example.com",
              display_name: null,
              roles: ["viewer"],
              created_ts: "2026-05-25T12:00:00Z",
              updated_ts: "2026-05-25T12:00:00Z"
            }
          ]
        } as Response;
      }
      if (url === "/api/v1/admin/users/viewer-user/roles" && init?.method === "PUT") {
        expect(JSON.parse(String(init.body))).toEqual({ roles: ["viewer", "contributor"] });
        return {
          ok: true,
          json: async () => ({
            user_id: "viewer-user",
            auth_provider: "cloudflare_access",
            auth_subject: "viewer@example.com",
            email: "viewer@example.com",
            display_name: null,
            roles: ["viewer", "contributor"],
            created_ts: "2026-05-25T12:00:00Z",
            updated_ts: "2026-05-25T12:01:00Z"
          })
        } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<OperationsRoutePage sessionIdentity={ADMIN_SESSION} />);

    expect(await screen.findByRole("heading", { name: "Users and roles", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Contributor" })).not.toBeChecked();

    await user.click(screen.getByRole("checkbox", { name: "Contributor" }));
    await user.click(screen.getByRole("button", { name: "Save roles for viewer@example.com" }));

    await waitFor(() => {
      expect(screen.getByRole("checkbox", { name: "Contributor" })).toBeChecked();
    });
  });
});
