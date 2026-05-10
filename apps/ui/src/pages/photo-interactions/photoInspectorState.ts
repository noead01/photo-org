export type ActiveFaceAssignmentTarget = {
  photoId: string;
  faceId: string;
  faceIndex: number | null;
  sourceSurfaceId: string;
};

export type PhotoInspectorState = {
  activeMetadataPhotoId: string | null;
  activeMetadataSourceSurfaceId: string | null;
  activeFaceAssignment: ActiveFaceAssignmentTarget | null;
  areFaceBoxesVisible: boolean;
};

export const DEFAULT_PHOTO_INSPECTOR_STATE: PhotoInspectorState = {
  activeMetadataPhotoId: null,
  activeMetadataSourceSurfaceId: null,
  activeFaceAssignment: null,
  areFaceBoxesVisible: false
};

export type PhotoInspectorAction =
  | { type: "openMetadata"; photoId: string; sourceSurfaceId: string }
  | { type: "closeMetadata" }
  | { type: "closeMetadataIfTargetMissing"; visiblePhotoIds: Set<string> }
  | {
      type: "openFaceAssignment";
      photoId: string;
      faceId: string;
      faceIndex?: number | null;
      sourceSurfaceId: string;
    }
  | { type: "closeFaceAssignment" }
  | { type: "setFaceBoxesVisible"; visible: boolean };

export function photoInspectorReducer(
  state: PhotoInspectorState,
  action: PhotoInspectorAction
): PhotoInspectorState {
  if (action.type === "openMetadata") {
    return {
      ...state,
      activeMetadataPhotoId: action.photoId,
      activeMetadataSourceSurfaceId: action.sourceSurfaceId
    };
  }

  if (action.type === "closeMetadata") {
    return {
      ...state,
      activeMetadataPhotoId: null,
      activeMetadataSourceSurfaceId: null
    };
  }

  if (action.type === "closeMetadataIfTargetMissing") {
    if (!state.activeMetadataPhotoId || action.visiblePhotoIds.has(state.activeMetadataPhotoId)) {
      return state;
    }

    return {
      ...state,
      activeMetadataPhotoId: null,
      activeMetadataSourceSurfaceId: null
    };
  }

  if (action.type === "openFaceAssignment") {
    return {
      ...state,
      activeFaceAssignment: {
        photoId: action.photoId,
        faceId: action.faceId,
        faceIndex: action.faceIndex ?? null,
        sourceSurfaceId: action.sourceSurfaceId
      }
    };
  }

  if (action.type === "closeFaceAssignment") {
    return {
      ...state,
      activeFaceAssignment: null
    };
  }

  if (action.type === "setFaceBoxesVisible") {
    return {
      ...state,
      areFaceBoxesVisible: action.visible
    };
  }

  return state;
}
