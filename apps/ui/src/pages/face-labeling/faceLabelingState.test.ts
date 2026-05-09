import {
  applyFaceAssignment,
  applyFaceConfirmation,
  applyFaceDismissal,
} from "./faceLabelingState";

describe("faceLabelingState", () => {
  it("applies assignment and clears machine label provenance fields", () => {
    const payload = {
      photo_id: "photo-1",
      faces: [
        {
          face_id: "face-1",
          person_id: null,
          label_source: "machine_suggested" as const,
          confidence: 0.83,
          model_version: "v1",
          provenance: { source: "model" },
          label_recorded_ts: "2026-05-01T00:00:00Z",
        },
      ],
    };

    const next = applyFaceAssignment(payload, "face-1", "person-3");
    expect(next.faces[0]).toMatchObject({
      face_id: "face-1",
      person_id: "person-3",
      label_source: null,
      confidence: null,
      model_version: null,
      provenance: null,
      label_recorded_ts: null,
    });
  });

  it("applies dismissal and decrements optional faces_count", () => {
    const payload = {
      photo_id: "photo-1",
      faces_count: 2,
      faces: [
        { face_id: "face-1", person_id: null },
        { face_id: "face-2", person_id: "person-1" },
      ],
    };

    const next = applyFaceDismissal(payload, "face-1");
    expect(next.faces).toEqual([{ face_id: "face-2", person_id: "person-1" }]);
    expect(next.faces_count).toBe(1);
  });

  it("applies confirmation with fallback provenance and timestamp", () => {
    const payload = {
      photo_id: "photo-1",
      faces: [
        {
          face_id: "face-1",
          person_id: "person-1",
          label_source: "machine_suggested" as const,
          provenance: null,
          label_recorded_ts: null,
        },
      ],
    };

    const next = applyFaceConfirmation(payload, "face-1", {
      provenance: { action: "confirmation" },
      recordedTs: "2026-05-09T12:00:00Z",
    });
    expect(next.faces[0]).toMatchObject({
      face_id: "face-1",
      person_id: "person-1",
      label_source: "human_confirmed",
      provenance: { action: "confirmation" },
      label_recorded_ts: "2026-05-09T12:00:00Z",
    });
  });
});
