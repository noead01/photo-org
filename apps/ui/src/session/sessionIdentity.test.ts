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
      roles: ["viewer", "contributor"],
      capabilities: {
        addToAlbum: true,
        export: false,
        reviewFaces: true,
        manageRoles: false,
        manageSources: false
      }
    };

    expect(resolveInitialSessionIdentity()).toEqual({
      userId: "operator-1",
      displayName: "Operator One",
      email: "op1@photo-org.local",
      roles: ["viewer", "contributor"],
      capabilities: {
        addToAlbum: true,
        export: false,
        reviewFaces: true,
        manageRoles: false,
        manageSources: false
      }
    });
  });

  it("treats malformed capabilities bootstrap as unavailable session", () => {
    window.__PHOTO_ORG_SESSION__ = {
      userId: "operator-1",
      displayName: "Operator One",
      email: "op1@photo-org.local",
      roles: ["viewer"],
      capabilities: {
        addToAlbum: "yes",
        export: false,
        reviewFaces: false,
        manageRoles: false,
        manageSources: false
      }
    };

    expect(resolveInitialSessionIdentity()).toBeNull();
  });
});
