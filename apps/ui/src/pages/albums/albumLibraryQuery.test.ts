import { describe, expect, it } from "vitest";
import type { AlbumRecord } from "../library/libraryRouteApi";
import {
  buildLibraryQueryForAlbum,
  parseSavedFilterDraft,
  serializeSavedFilter
} from "./albumLibraryQuery";

function buildAlbum(overrides: Partial<AlbumRecord>): AlbumRecord {
  return {
    album_id: "album-1",
    name: "Album One",
    owner_user_id: "demo-user",
    kind: "saved_filter",
    created_ts: "2026-05-08T12:00:00Z",
    updated_ts: "2026-05-08T12:00:00Z",
    item_count: 0,
    saved_filter: null,
    ...overrides
  };
}

describe("albumLibraryQuery", () => {
  it("builds editable album query from album id only", () => {
    const query = buildLibraryQueryForAlbum(
      buildAlbum({ album_id: "album-editable", kind: "editable", saved_filter: null })
    );

    expect(query).toBe("album=album-editable");
  });

  it("maps saved filter fields to library query params", () => {
    const query = buildLibraryQueryForAlbum(
      buildAlbum({
        saved_filter: {
          person_names: ["Inez Rivera", " Tom ", "Inez Rivera", "", 42],
          album_ids: ["fav", " fav ", "other"],
          person_certainty_mode: "include_suggestions",
          suggestion_confidence_min: 0.91,
          date: { from: "2025-01-02", to: "2025-03-04" },
          location_radius: { latitude: 40.7, longitude: -73.9, radius_km: 5.5 },
          has_faces: false,
          path_hints: ["/raw", " /raw ", "/exports", null]
        }
      })
    );

    expect(query).toBe(
      "from=2025-01-02&to=2025-03-04&person=Inez+Rivera&person=Tom&album=fav&album=other&personCertainty=include_suggestions&suggestionMin=0.91&lat=40.7&lng=-73.9&radiusKm=5.5&hasFaces=false&pathHint=%2Fraw&pathHint=%2Fexports"
    );
  });

  it("falls back to defaults when saved filter fields are invalid", () => {
    const query = buildLibraryQueryForAlbum(
      buildAlbum({
        saved_filter: {
          person_names: "not-an-array",
          album_ids: ["album-a", 12],
          person_certainty_mode: "unexpected",
          suggestion_confidence_min: "0.42",
          date: { from: 100, to: true },
          location_radius: { latitude: "bad", longitude: -73.9, radius_km: 5.5 },
          has_faces: "yes",
          path_hints: [null, "  "]
        }
      })
    );

    expect(query).toBe("album=album-a");
  });

  it("throws for invalid saved filter draft JSON shapes", () => {
    expect(() => parseSavedFilterDraft("[]")).toThrowError("Saved filter JSON must be an object.");
    expect(() => parseSavedFilterDraft('"abc"')).toThrowError("Saved filter JSON must be an object.");
  });

  it("serializes non-object saved filters to an empty object", () => {
    expect(serializeSavedFilter(null)).toBe("{}");
    expect(serializeSavedFilter(["nope"] as unknown as Record<string, unknown>)).toBe("{}");
    expect(serializeSavedFilter({ person_names: ["Inez"] })).toBe('{\n  "person_names": [\n    "Inez"\n  ]\n}');
  });
});
