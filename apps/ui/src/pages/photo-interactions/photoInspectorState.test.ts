import {
  DEFAULT_PHOTO_INSPECTOR_STATE,
  photoInspectorReducer,
} from "./photoInspectorState";

describe("photoInspectorState", () => {
  it("retargets metadata without changing face assignment target", () => {
    const withFace = photoInspectorReducer(DEFAULT_PHOTO_INSPECTOR_STATE, {
      type: "openFaceAssignment",
      photoId: "photo-1",
      faceId: "face-1",
      sourceSurfaceId: "surface-photo-1",
    });

    const retargeted = photoInspectorReducer(withFace, {
      type: "openMetadata",
      photoId: "photo-2",
      sourceSurfaceId: "surface-photo-2",
    });

    expect(retargeted.activeMetadataPhotoId).toBe("photo-2");
    expect(retargeted.activeMetadataSourceSurfaceId).toBe("surface-photo-2");
    expect(retargeted.activeFaceAssignment).toEqual({
      photoId: "photo-1",
      faceId: "face-1",
      sourceSurfaceId: "surface-photo-1",
    });
  });

  it("closes stale metadata target when requested", () => {
    const opened = photoInspectorReducer(DEFAULT_PHOTO_INSPECTOR_STATE, {
      type: "openMetadata",
      photoId: "photo-1",
      sourceSurfaceId: "surface-photo-1",
    });

    const closed = photoInspectorReducer(opened, {
      type: "closeMetadataIfTargetMissing",
      visiblePhotoIds: new Set(["photo-2"]),
    });

    expect(closed.activeMetadataPhotoId).toBeNull();
    expect(closed.activeMetadataSourceSurfaceId).toBeNull();
  });

  it("applies screen face-box defaults", () => {
    const suggestions = photoInspectorReducer(DEFAULT_PHOTO_INSPECTOR_STATE, {
      type: "setFaceBoxesVisible",
      visible: true,
    });

    expect(suggestions.areFaceBoxesVisible).toBe(true);
  });
});
