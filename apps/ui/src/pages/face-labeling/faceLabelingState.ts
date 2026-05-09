type FaceLabelSource = "human_confirmed" | "machine_suggested" | null;

type FaceLabelingRecord = {
  face_id: string;
  person_id: string | null;
  label_source?: FaceLabelSource;
  confidence?: number | null;
  model_version?: string | null;
  provenance?: Record<string, unknown> | null;
  label_recorded_ts?: string | null;
};

type FaceCollection<TFace extends FaceLabelingRecord> = {
  faces: TFace[];
  faces_count?: number;
};

export function applyFaceAssignment<
  TFace extends FaceLabelingRecord,
  TCollection extends FaceCollection<TFace>,
>(payload: TCollection, faceId: string, personId: string): TCollection {
  return {
    ...payload,
    faces: payload.faces.map((face) =>
      face.face_id === faceId
        ? ({
            ...face,
            person_id: personId,
            label_source: null,
            confidence: null,
            model_version: null,
            provenance: null,
            label_recorded_ts: null,
          } as TFace)
        : face
    ),
  };
}

export function applyFaceDismissal<
  TFace extends FaceLabelingRecord,
  TCollection extends FaceCollection<TFace>,
>(payload: TCollection, faceId: string): TCollection {
  const nextFaces = payload.faces.filter((face) => face.face_id !== faceId);
  const removedCount = payload.faces.length - nextFaces.length;
  const nextFacesCount =
    typeof payload.faces_count === "number"
      ? Math.max(0, payload.faces_count - removedCount)
      : payload.faces_count;

  return {
    ...payload,
    faces: nextFaces,
    ...(typeof nextFacesCount === "number" ? { faces_count: nextFacesCount } : {}),
  };
}

type ApplyFaceConfirmationOptions = {
  personId?: string;
  provenance?: Record<string, unknown> | null;
  recordedTs?: string;
};

export function applyFaceConfirmation<
  TFace extends FaceLabelingRecord,
  TCollection extends FaceCollection<TFace>,
>(
  payload: TCollection,
  faceId: string,
  options: ApplyFaceConfirmationOptions = {}
): TCollection {
  return {
    ...payload,
    faces: payload.faces.map((face) =>
      face.face_id === faceId
        ? ({
            ...face,
            person_id: options.personId ?? face.person_id,
            label_source: "human_confirmed",
            provenance: face.provenance ?? options.provenance ?? null,
            label_recorded_ts: face.label_recorded_ts ?? options.recordedTs ?? null,
          } as TFace)
        : face
    ),
  };
}
