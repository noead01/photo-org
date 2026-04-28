export interface SessionIdentity {
  userId: string;
  displayName: string;
  email: string;
}

export const DEMO_SESSION_IDENTITY: SessionIdentity = {
  userId: "demo-operator",
  displayName: "Demo Operator",
  email: "operator@photo-org.local"
};

interface SessionIdentityBootstrapShape {
  userId?: unknown;
  displayName?: unknown;
  email?: unknown;
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
    candidate.email.length > 0
  );
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
