import { describe, expect, it } from "vitest";
import {
  adaptLibraryPhoto,
  adaptPhotoDetail,
  adaptSuggestionPhoto,
} from "./photoInteractionAdapters";

describe("photo interaction adapters", () => {
  it("adapts a library photo into a thumbnail-first shared summary", () => {
    const summary = adaptLibraryPhoto({
      photo_id: "photo-1",
      path: "/storage-sources/source-1/family/lake.jpg",
      ext: ".jpg",
      shot_ts: "2026-05-01T12:00:00Z",
      filesize: 12345,
      people: ["person-1"],
      faces: [
        {
          person_id: null,
          label_source: null,
          confidence: null,
          suggestions: [],
        },
      ],
      thumbnail: {
        mime_type: "image/jpeg",
        width: 200,
        height: 100,
        data_base64: "abc",
      },
      original: {
        is_available: true,
        availability_state: "available",
        last_failure_reason: null,
      },
    });

    expect(summary.photoId).toBe("photo-1");
    expect(summary.media.thumbnail?.width).toBe(200);
    expect(summary.media.originalIntent).toBe("detail-only");
    expect(summary.faces).toHaveLength(1);
    expect(summary.faces[0]).toMatchObject({
      faceId: "photo-1-face-1",
      personId: null,
      bbox: {
        x: null,
        y: null,
        width: null,
        height: null,
        spaceWidth: null,
        spaceHeight: null,
      },
    });
  });

  it("adapts a suggestion photo with face-review suggestions preserved", () => {
    const summary = adaptSuggestionPhoto({
      photo_id: "photo-2",
      path: "/storage-sources/source-1/family/birthday.jpg",
      thumbnail: {
        mime_type: "image/jpeg",
        width: 160,
        height: 120,
        data_base64: "def",
      },
      faces: [
        {
          face_id: "face-2",
          bbox_x: 1,
          bbox_y: 2,
          bbox_w: 3,
          bbox_h: 4,
          bbox_space_width: 160,
          bbox_space_height: 120,
          top_suggestion: {
            person_id: "person-2",
            display_name: "Ada",
            confidence: 0.91,
          },
          suggestions: [
            {
              person_id: "person-2",
              display_name: "Ada",
              rank: 1,
              confidence: 0.91,
            },
          ],
        },
      ],
    });

    expect(summary.defaultFaceBoxesVisible).toBe(true);
    expect(summary.faces[0].bbox).toMatchObject({
      x: 1,
      y: 2,
      width: 3,
      height: 4,
      spaceWidth: 160,
      spaceHeight: 120,
    });
    expect(summary.faces[0].suggestions[0]).toMatchObject({
      personId: "person-2",
      displayName: "Ada",
      confidence: 0.91,
      modelVersion: null,
      provenance: null,
    });
  });

  it("adapts photo detail with original image intent enabled", () => {
    const summary = adaptPhotoDetail({
      photo_id: "photo-3",
      path: "/photos/original.jpg",
      ext: ".jpg",
      shot_ts: null,
      filesize: 999,
      camera_make: null,
      orientation: null,
      tags: [],
      people: [],
      thumbnail: null,
      original: {
        is_available: true,
        availability_state: "available",
        last_failure_reason: null,
      },
      metadata: {
        sha256: "hash",
        phash: null,
        shot_ts_source: null,
        camera_model: null,
        software: null,
        gps_latitude: null,
        gps_longitude: null,
        gps_altitude: null,
        faces_count: 0,
        faces_detected_ts: null,
        created_ts: "2026-05-01T00:00:00Z",
        updated_ts: "2026-05-01T00:00:00Z",
        modified_ts: null,
        deleted_ts: null,
        exif_attributes: null,
      },
      faces: [],
    });

    expect(summary.media.originalIntent).toBe("auto-load");
  });
});
