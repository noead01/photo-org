import { DEMO_SESSION_IDENTITY, resolveInitialSessionIdentity } from "./sessionIdentity";

describe("sessionIdentity", () => {
  const originalSessionBootstrap = window.__PHOTO_ORG_SESSION__;

  afterEach(() => {
    window.__PHOTO_ORG_SESSION__ = originalSessionBootstrap;
  });

  it("returns demo identity when bootstrap is not provided", () => {
    window.__PHOTO_ORG_SESSION__ = undefined;
    expect(resolveInitialSessionIdentity()).toEqual(DEMO_SESSION_IDENTITY);
  });

  it("accepts capabilities from bootstrap identity payload", () => {
    window.__PHOTO_ORG_SESSION__ = {
      userId: "operator-1",
      displayName: "Operator One",
      email: "op1@photo-org.local",
      capabilities: { addToAlbum: true, export: false }
    };

    expect(resolveInitialSessionIdentity()).toEqual({
      userId: "operator-1",
      displayName: "Operator One",
      email: "op1@photo-org.local",
      capabilities: { addToAlbum: true, export: false }
    });
  });

  it("treats malformed capabilities bootstrap as unavailable session", () => {
    window.__PHOTO_ORG_SESSION__ = {
      userId: "operator-1",
      displayName: "Operator One",
      email: "op1@photo-org.local",
      capabilities: { addToAlbum: "yes", export: false }
    };

    expect(resolveInitialSessionIdentity()).toBeNull();
  });
});
