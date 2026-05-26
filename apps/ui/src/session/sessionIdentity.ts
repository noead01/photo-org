export interface SessionCapabilities {
  addToAlbum: boolean;
  export: boolean;
  reviewFaces: boolean;
  manageRoles: boolean;
  manageSources: boolean;
}

export interface SessionIdentity {
  userId: string;
  displayName: string;
  email: string;
  roles: string[];
  capabilities: SessionCapabilities;
}

export const DEMO_SESSION_IDENTITY: SessionIdentity = {
  userId: "demo-operator",
  displayName: "Demo Operator",
  email: "operator@photo-org.local",
  roles: ["admin"],
  capabilities: {
    addToAlbum: true,
    export: true,
    reviewFaces: true,
    manageRoles: true,
    manageSources: true
  }
};

interface SessionIdentityBootstrapShape {
  userId?: unknown;
  displayName?: unknown;
  email?: unknown;
  roles?: unknown;
  capabilities?: unknown;
}

declare global {
  interface Window {
    __PHOTO_ORG_SESSION__?: SessionIdentityBootstrapShape | null;
  }
}

function isSessionIdentity(value: unknown): value is SessionIdentity {
  if (value === null || typeof value !== "object") {
    return false;
  }

  const candidate = value as SessionIdentityBootstrapShape;

  return (
    typeof candidate.userId === "string" &&
    candidate.userId.length > 0 &&
    typeof candidate.displayName === "string" &&
    candidate.displayName.length > 0 &&
    typeof candidate.email === "string" &&
    candidate.email.length > 0 &&
    Array.isArray(candidate.roles) &&
    candidate.roles.every((role) => typeof role === "string") &&
    isSessionCapabilities(candidate.capabilities)
  );
}

function isSessionCapabilities(value: unknown): value is SessionCapabilities {
  if (value === null || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.addToAlbum === "boolean" &&
    typeof candidate.export === "boolean" &&
    typeof candidate.reviewFaces === "boolean" &&
    typeof candidate.manageRoles === "boolean" &&
    typeof candidate.manageSources === "boolean"
  );
}

function adaptSessionIdentityPayload(payload: {
  user_id: string;
  display_name: string | null;
  email: string;
  roles: string[];
  capabilities: {
    add_to_album: boolean;
    export: boolean;
    review_faces: boolean;
    manage_roles: boolean;
    manage_sources: boolean;
  };
}): SessionIdentity {
  return {
    userId: payload.user_id,
    displayName: payload.display_name ?? payload.email,
    email: payload.email,
    roles: payload.roles,
    capabilities: {
      addToAlbum: payload.capabilities.add_to_album,
      export: payload.capabilities.export,
      reviewFaces: payload.capabilities.review_faces,
      manageRoles: payload.capabilities.manage_roles,
      manageSources: payload.capabilities.manage_sources
    }
  };
}

export function resolveInitialSessionIdentity(): SessionIdentity | null {
  if (typeof window === "undefined") {
    return DEMO_SESSION_IDENTITY;
  }

  const bootstrappedIdentity = window.__PHOTO_ORG_SESSION__;

  if (bootstrappedIdentity === undefined) {
    return DEMO_SESSION_IDENTITY;
  }

  if (isSessionIdentity(bootstrappedIdentity)) {
    return bootstrappedIdentity;
  }

  return null;
}

export async function fetchCurrentSessionIdentity(signal?: AbortSignal): Promise<SessionIdentity | null> {
  const response = await fetch("/api/v1/admin/session", { signal });
  if (response.status === 401 || response.status === 403) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Session request failed (${response.status})`);
  }
  return adaptSessionIdentityPayload(
    (await response.json()) as {
      user_id: string;
      display_name: string | null;
      email: string;
      roles: string[];
      capabilities: {
        add_to_album: boolean;
        export: boolean;
        review_faces: boolean;
        manage_roles: boolean;
        manage_sources: boolean;
      };
    }
  );
}
