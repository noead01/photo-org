# Photo Interaction Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared photo interaction model across Library, Suggestions, Albums, and Photo Detail, including face assignment, metadata, photo selection, and album assignment.

**Architecture:** Introduce shared UI contracts and reusable components for photo surfaces, face overlays, metadata targeting, face assignment, selection, and album actions. Migrate each route in slices, removing obsolete route-specific implementations as soon as the shared replacement fully covers that route. Keep Suggestions as a specialized batch face-review route with distinct photo and face selection state.

**Tech Stack:** React 18, TypeScript, React Router 6, Vitest, Testing Library, existing Fetch API modules.

---

## Source Design

Read the approved design before implementation:

- `docs/superpowers/specs/2026-05-09-photo-interaction-unification-design.md`

## Cleanup Policy

Dead-code removal is part of this implementation, not a later phase.

- Remove obsolete route-specific components, helpers, CSS selectors, and tests within the same migration task that replaces them.
- Keep temporary adapters only when a later task still imports them. Mark the exact removal task in this plan.
- Do not leave old and new interaction paths active for the same route after that route is migrated.
- Every route migration task includes a cleanup gate.
- The final task runs repository-wide searches for stale names and duplicated logic.

## File Structure

### Shared Photo Interaction Domain

- Create: `apps/ui/src/pages/photo-interactions/photoInteractionTypes.ts`
  - Own shared UI contracts: `PhotoSummary`, `PhotoMedia`, `PhotoFace`, `AlbumTarget`, `PhotoAlbumMembership`, `PhotoInspectorState`.
- Create: `apps/ui/src/pages/photo-interactions/photoInteractionAdapters.ts`
  - Adapt existing route payloads into shared contracts.
- Create: `apps/ui/src/pages/photo-interactions/photoInteractionAdapters.test.ts`
  - Cover Library, Suggestions, Albums, and Photo Detail adapter shapes.
- Create: `apps/ui/src/pages/photo-interactions/photoSelectionState.ts`
  - Own shared photo selection reducer, serialization helpers, and selectors.
- Create: `apps/ui/src/pages/photo-interactions/photoSelectionState.test.ts`
  - Port and extend current library selection reducer tests.
- Create: `apps/ui/src/pages/photo-interactions/photoInspectorState.ts`
  - Own metadata target, active face target, and face-box visibility reducer.
- Create: `apps/ui/src/pages/photo-interactions/photoInspectorState.test.ts`
  - Cover retargeting, closing stale target, route defaults.

### Shared Components

- Create: `apps/ui/src/pages/photo-interactions/FaceOverlayLayer.tsx`
  - Wrap and eventually replace `apps/ui/src/pages/FaceBBoxOverlay.tsx`.
- Create: `apps/ui/src/pages/photo-interactions/FaceOverlayLayer.test.tsx`
  - Cover rendering and click delegation.
- Create: `apps/ui/src/pages/photo-interactions/PhotoSurface.tsx`
  - Render a thumbnail/original photo unit with selection, metadata, face overlay, and open-detail affordances.
- Create: `apps/ui/src/pages/photo-interactions/PhotoSurface.test.tsx`
  - Cover click routing, selection isolation, metadata target framing, face action isolation.
- Create: `apps/ui/src/pages/photo-interactions/PhotoGridSurface.tsx`
  - Render grid/list collections of `PhotoSurface`.
- Create: `apps/ui/src/pages/photo-interactions/PhotoGridSurface.test.tsx`
  - Cover normal-grid and Suggestions defaults.
- Create: `apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.tsx`
  - Shared retargetable metadata/EXIF flyout.
- Create: `apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.test.tsx`
  - Port and extend current photo detail flyout coverage.
- Create: `apps/ui/src/pages/photo-interactions/FaceAssignmentModal.tsx`
  - Shared centered face assignment modal.
- Create: `apps/ui/src/pages/photo-interactions/FaceAssignmentModal.test.tsx`
  - Port and extend current modal tests.
- Create: `apps/ui/src/pages/photo-interactions/AlbumActionSurface.tsx`
  - Shared add-to-album/create-and-add controls over photo selection.
- Create: `apps/ui/src/pages/photo-interactions/AlbumActionSurface.test.tsx`
  - Cover selected/page/all-filtered album assignment behavior.

### Route Migrations

- Modify: `apps/ui/src/pages/library/LibraryPhotoGrid.tsx`
  - Replace route-specific card rendering with shared `PhotoGridSurface`.
- Modify or delete: `apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx`
  - Delete when Library uses shared face modal and overlay directly.
- Modify or delete: `apps/ui/src/pages/FaceBBoxOverlay.tsx`
  - Delete after `FaceOverlayLayer` owns the shared face overlay API and all imports are migrated.
- Modify or delete: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
  - Delete after shared `FaceAssignmentModal` replaces all imports.
- Modify or delete: `apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx`
  - Delete after shared `PhotoMetadataFlyout` replaces all imports.
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.tsx`
- Modify: `apps/ui/src/pages/suggestions/SuggestionsGrid.tsx`
- Modify: `apps/ui/src/pages/suggestions/SuggestionFaceRow.tsx`
- Modify: `apps/ui/src/pages/AlbumsRoutePage.tsx`
- Modify: `apps/ui/src/pages/albums/AlbumsGrid.tsx`
- Modify: `apps/ui/src/pages/albums/AlbumDetailInline.tsx`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
  - Move route-specific selectors toward shared photo-interaction selectors and remove obsolete CSS after each migration.

---

## Task 1: Shared Photo Interaction Contracts And Adapters

**Files:**
- Create: `apps/ui/src/pages/photo-interactions/photoInteractionTypes.ts`
- Create: `apps/ui/src/pages/photo-interactions/photoInteractionAdapters.ts`
- Create: `apps/ui/src/pages/photo-interactions/photoInteractionAdapters.test.ts`

- [ ] **Step 1: Write adapter tests**

Create `apps/ui/src/pages/photo-interactions/photoInteractionAdapters.test.ts`:

```ts
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
          face_id: "face-1",
          person_id: null,
          bbox_x: 10,
          bbox_y: 20,
          bbox_w: 30,
          bbox_h: 40,
          bbox_space_width: 100,
          bbox_space_height: 100,
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
      faceId: "face-1",
      personId: null,
      bbox: {
        x: 10,
        y: 20,
        width: 30,
        height: 40,
        spaceWidth: 100,
        spaceHeight: 100,
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
              model_version: "face-v1",
              provenance: { workflow: "suggestions" },
            },
          ],
        },
      ],
    });

    expect(summary.defaultFaceBoxesVisible).toBe(true);
    expect(summary.faces[0].suggestions[0]).toMatchObject({
      personId: "person-2",
      displayName: "Ada",
      confidence: 0.91,
    });
  });

  it("adapts photo detail with original image intent enabled", () => {
    const summary = adaptPhotoDetail({
      photo_id: "photo-3",
      path: "/photos/original.jpg",
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
        exif_attributes: null,
      },
      faces: [],
    });

    expect(summary.media.originalIntent).toBe("auto-load");
  });
});
```

- [ ] **Step 2: Run adapter tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- photoInteractionAdapters.test.ts
```

Expected: fails because `photoInteractionAdapters` does not exist.

- [ ] **Step 3: Add shared types**

Create `apps/ui/src/pages/photo-interactions/photoInteractionTypes.ts`:

```ts
export type PhotoOriginalIntent = "detail-only" | "auto-load";

export type FaceLabelSource = "human_confirmed" | "machine_suggested" | null;

export type PhotoThumbnail = {
  mimeType: string;
  width: number;
  height: number;
  dataBase64: string;
};

export type PhotoMedia = {
  thumbnail: PhotoThumbnail | null;
  originalIntent: PhotoOriginalIntent;
  originalAvailability: {
    isAvailable: boolean | null;
    availabilityState: string | null;
    lastFailureReason: string | null;
  } | null;
};

export type PhotoFaceSuggestion = {
  personId: string;
  displayName: string;
  rank: number | null;
  confidence: number;
  modelVersion: string | null;
  provenance: Record<string, unknown> | null;
};

export type PhotoFace = {
  faceId: string;
  personId: string | null;
  bbox: {
    x: number | null;
    y: number | null;
    width: number | null;
    height: number | null;
    spaceWidth: number | null;
    spaceHeight: number | null;
  };
  labelSource: FaceLabelSource;
  confidence: number | null;
  modelVersion: string | null;
  provenance: Record<string, unknown> | null;
  labelRecordedTs: string | null;
  suggestions: PhotoFaceSuggestion[];
  canAssign: boolean;
  canCorrect: boolean;
  canDismiss: boolean;
  canConfirm: boolean;
};

export type PhotoAlbumMembership = {
  albumIds: string[];
  currentAlbumId: string | null;
};

export type PhotoSummary = {
  photoId: string;
  path: string;
  title: string;
  shotTs: string | null;
  filesize: number | null;
  people: string[];
  media: PhotoMedia;
  faces: PhotoFace[];
  albumMembership: PhotoAlbumMembership | null;
  defaultFaceBoxesVisible: boolean;
};

export type AlbumTarget = {
  albumId: string;
  name: string;
  kind: "manual" | "saved_filter";
  canAcceptManualAdditions: boolean;
};
```

- [ ] **Step 4: Add adapters**

Create `apps/ui/src/pages/photo-interactions/photoInteractionAdapters.ts`:

```ts
import type { PhotoDetailPayload } from "../photo-detail/photoDetailTypes";
import type { LibraryPhoto } from "../library/libraryRouteTypes";
import type { SuggestionPhoto } from "../suggestions/types";
import type {
  PhotoFace,
  PhotoFaceSuggestion,
  PhotoSummary,
  PhotoThumbnail,
} from "./photoInteractionTypes";

type FaceLike = {
  face_id?: string;
  person_id?: string | null;
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_w?: number | null;
  bbox_h?: number | null;
  bbox_space_width?: number | null;
  bbox_space_height?: number | null;
  label_source?: "human_confirmed" | "machine_suggested" | null;
  confidence?: number | null;
  model_version?: string | null;
  provenance?: Record<string, unknown> | null;
  label_recorded_ts?: string | null;
  suggestions?: Array<{
    person_id: string;
    display_name: string;
    rank?: number | null;
    confidence: number;
    model_version?: string | null;
    provenance?: Record<string, unknown> | null;
  }>;
  top_suggestion?: {
    person_id: string;
    display_name: string;
    confidence: number;
  };
};

function titleFromPath(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) {
    return "Untitled photo";
  }
  const lastSlash = trimmed.lastIndexOf("/");
  return lastSlash >= 0 ? trimmed.slice(lastSlash + 1) : trimmed;
}

function adaptThumbnail(
  thumbnail:
    | {
        mime_type: string;
        width: number;
        height: number;
        data_base64: string;
      }
    | null
    | undefined
): PhotoThumbnail | null {
  if (!thumbnail) {
    return null;
  }
  return {
    mimeType: thumbnail.mime_type,
    width: thumbnail.width,
    height: thumbnail.height,
    dataBase64: thumbnail.data_base64,
  };
}

function adaptSuggestions(face: FaceLike): PhotoFaceSuggestion[] {
  const explicitSuggestions = Array.isArray(face.suggestions) ? face.suggestions : [];
  const fallbackSuggestion =
    explicitSuggestions.length === 0 && face.top_suggestion
      ? [
          {
            person_id: face.top_suggestion.person_id,
            display_name: face.top_suggestion.display_name,
            rank: 1,
            confidence: face.top_suggestion.confidence,
            model_version: null,
            provenance: null,
          },
        ]
      : [];

  return [...explicitSuggestions, ...fallbackSuggestion].map((suggestion) => ({
    personId: suggestion.person_id,
    displayName: suggestion.display_name,
    rank: suggestion.rank ?? null,
    confidence: suggestion.confidence,
    modelVersion: suggestion.model_version ?? null,
    provenance: suggestion.provenance ?? null,
  }));
}

function adaptFace(face: FaceLike, fallbackFaceId: string): PhotoFace {
  const personId = face.person_id ?? null;
  const labelSource = face.label_source ?? null;
  return {
    faceId: face.face_id ?? fallbackFaceId,
    personId,
    bbox: {
      x: face.bbox_x ?? null,
      y: face.bbox_y ?? null,
      width: face.bbox_w ?? null,
      height: face.bbox_h ?? null,
      spaceWidth: face.bbox_space_width ?? null,
      spaceHeight: face.bbox_space_height ?? null,
    },
    labelSource,
    confidence: face.confidence ?? null,
    modelVersion: face.model_version ?? null,
    provenance: face.provenance ?? null,
    labelRecordedTs: face.label_recorded_ts ?? null,
    suggestions: adaptSuggestions(face),
    canAssign: personId === null,
    canCorrect: personId !== null,
    canDismiss: personId === null,
    canConfirm: personId !== null && labelSource === "machine_suggested",
  };
}

export function adaptLibraryPhoto(photo: LibraryPhoto): PhotoSummary {
  return {
    photoId: photo.photo_id,
    path: photo.path,
    title: titleFromPath(photo.path),
    shotTs: photo.shot_ts,
    filesize: photo.filesize,
    people: photo.people ?? [],
    media: {
      thumbnail: adaptThumbnail(photo.thumbnail),
      originalIntent: "detail-only",
      originalAvailability: photo.original
        ? {
            isAvailable: photo.original.is_available,
            availabilityState: photo.original.availability_state,
            lastFailureReason: photo.original.last_failure_reason,
          }
        : null,
    },
    faces: (photo.faces ?? []).map((face, index) => adaptFace(face, `${photo.photo_id}-face-${index + 1}`)),
    albumMembership: null,
    defaultFaceBoxesVisible: false,
  };
}

export function adaptSuggestionPhoto(photo: SuggestionPhoto): PhotoSummary {
  return {
    photoId: photo.photo_id,
    path: photo.path,
    title: titleFromPath(photo.path),
    shotTs: null,
    filesize: null,
    people: [],
    media: {
      thumbnail: adaptThumbnail(photo.thumbnail),
      originalIntent: "detail-only",
      originalAvailability: null,
    },
    faces: photo.faces.map((face, index) => adaptFace(face, `${photo.photo_id}-suggested-face-${index + 1}`)),
    albumMembership: null,
    defaultFaceBoxesVisible: true,
  };
}

export function adaptPhotoDetail(detail: PhotoDetailPayload): PhotoSummary {
  return {
    photoId: detail.photo_id,
    path: detail.path,
    title: titleFromPath(detail.path),
    shotTs: detail.shot_ts,
    filesize: detail.filesize,
    people: detail.people,
    media: {
      thumbnail: adaptThumbnail(detail.thumbnail),
      originalIntent: "auto-load",
      originalAvailability: detail.original
        ? {
            isAvailable: detail.original.is_available,
            availabilityState: detail.original.availability_state,
            lastFailureReason: detail.original.last_failure_reason,
          }
        : null,
    },
    faces: detail.faces.map((face, index) => adaptFace(face, `${detail.photo_id}-face-${index + 1}`)),
    albumMembership: null,
    defaultFaceBoxesVisible: true,
  };
}
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
npm --prefix apps/ui test -- photoInteractionAdapters.test.ts
```

Expected: tests pass.

- [ ] **Step 6: Commit contracts**

Run:

```bash
git add apps/ui/src/pages/photo-interactions/photoInteractionTypes.ts apps/ui/src/pages/photo-interactions/photoInteractionAdapters.ts apps/ui/src/pages/photo-interactions/photoInteractionAdapters.test.ts
git commit -m "feat: add shared photo interaction contracts"
```

---

## Task 2: Shared Photo Selection And Inspector State

**Files:**
- Create: `apps/ui/src/pages/photo-interactions/photoSelectionState.ts`
- Create: `apps/ui/src/pages/photo-interactions/photoSelectionState.test.ts`
- Create: `apps/ui/src/pages/photo-interactions/photoInspectorState.ts`
- Create: `apps/ui/src/pages/photo-interactions/photoInspectorState.test.ts`
- Modify: `apps/ui/src/pages/library/librarySelection.ts`
- Modify: `apps/ui/src/pages/library/librarySelection.test.ts`

- [ ] **Step 1: Write shared selection tests**

Create `apps/ui/src/pages/photo-interactions/photoSelectionState.test.ts` by porting the existing assertions from `apps/ui/src/pages/library/librarySelection.test.ts` and adding this test:

```ts
import { describe, expect, it } from "vitest";
import {
  DEFAULT_PHOTO_SELECTION_STATE,
  photoSelectionReducer,
  serializePhotoSelectionState,
} from "./photoSelectionState";

describe("photoSelectionState", () => {
  it("keeps selected ids independent from inspector actions", () => {
    const selected = photoSelectionReducer(DEFAULT_PHOTO_SELECTION_STATE, {
      type: "togglePhotoSelection",
      photoId: "photo-1",
    });

    expect(selected.selectedPhotoIds.has("photo-1")).toBe(true);
    expect(serializePhotoSelectionState(selected)).toMatchObject({
      scope: "selected",
      selectedPhotoIds: ["photo-1"],
      allFilteredFingerprint: null,
    });
  });
});
```

- [ ] **Step 2: Write inspector state tests**

Create `apps/ui/src/pages/photo-interactions/photoInspectorState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
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
```

- [ ] **Step 3: Run state tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- photoSelectionState.test.ts photoInspectorState.test.ts
```

Expected: fails because files do not exist.

- [ ] **Step 4: Add shared photo selection state**

Create `apps/ui/src/pages/photo-interactions/photoSelectionState.ts` by moving the implementation from `apps/ui/src/pages/library/librarySelection.ts`, renaming exported symbols from `Library*` to `Photo*`, and keeping route-state compatibility:

```ts
export type PhotoSelectionScope = "selected" | "page" | "allFiltered";

export interface PhotoSelectionState {
  scope: PhotoSelectionScope;
  selectedPhotoIds: Set<string>;
  allFilteredFingerprint: string | null;
}

export interface PhotoSelectionRouteState {
  scope: PhotoSelectionScope;
  selectedPhotoIds: string[];
  allFilteredFingerprint: string | null;
}

export const DEFAULT_PHOTO_SELECTION_STATE: PhotoSelectionState = {
  scope: "selected",
  selectedPhotoIds: new Set<string>(),
  allFilteredFingerprint: null,
};

export type PhotoSelectionAction =
  | { type: "togglePhotoSelection"; photoId: string }
  | { type: "setScope"; scope: PhotoSelectionScope; activeFilterFingerprint: string }
  | { type: "filtersChanged"; activeFilterFingerprint: string }
  | { type: "clearExplicitSelection" };

export function serializePhotoSelectionState(state: PhotoSelectionState): PhotoSelectionRouteState {
  return {
    scope: state.scope,
    selectedPhotoIds: Array.from(state.selectedPhotoIds).sort((left, right) =>
      left.localeCompare(right, "en-US")
    ),
    allFilteredFingerprint: state.scope === "allFiltered" ? state.allFilteredFingerprint : null,
  };
}

export function photoSelectionReducer(
  state: PhotoSelectionState,
  action: PhotoSelectionAction
): PhotoSelectionState {
  if (action.type === "togglePhotoSelection") {
    const normalizedPhotoId = action.photoId.trim();
    if (normalizedPhotoId.length === 0) {
      return state;
    }
    const nextSelectedPhotoIds = new Set(state.selectedPhotoIds);
    if (nextSelectedPhotoIds.has(normalizedPhotoId)) {
      nextSelectedPhotoIds.delete(normalizedPhotoId);
    } else {
      nextSelectedPhotoIds.add(normalizedPhotoId);
    }
    return { ...state, selectedPhotoIds: nextSelectedPhotoIds };
  }

  if (action.type === "setScope") {
    return {
      ...state,
      scope: action.scope,
      allFilteredFingerprint:
        action.scope === "allFiltered" ? action.activeFilterFingerprint : null,
    };
  }

  if (action.type === "filtersChanged") {
    if (
      state.scope === "allFiltered" &&
      state.allFilteredFingerprint !== action.activeFilterFingerprint
    ) {
      return { ...state, scope: "selected", allFilteredFingerprint: null };
    }
    return state;
  }

  if (action.type === "clearExplicitSelection") {
    return state.selectedPhotoIds.size === 0
      ? state
      : { ...state, selectedPhotoIds: new Set<string>() };
  }

  return state;
}
```

Also copy the existing parse/count/format helpers from `librarySelection.ts` into this shared module, preserving current behavior.

- [ ] **Step 5: Add inspector state reducer**

Create `apps/ui/src/pages/photo-interactions/photoInspectorState.ts`:

```ts
export type ActiveFaceAssignmentTarget = {
  photoId: string;
  faceId: string;
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
  areFaceBoxesVisible: false,
};

export type PhotoInspectorAction =
  | { type: "openMetadata"; photoId: string; sourceSurfaceId: string }
  | { type: "closeMetadata" }
  | { type: "closeMetadataIfTargetMissing"; visiblePhotoIds: Set<string> }
  | { type: "openFaceAssignment"; photoId: string; faceId: string; sourceSurfaceId: string }
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
      activeMetadataSourceSurfaceId: action.sourceSurfaceId,
    };
  }

  if (action.type === "closeMetadata") {
    return {
      ...state,
      activeMetadataPhotoId: null,
      activeMetadataSourceSurfaceId: null,
    };
  }

  if (action.type === "closeMetadataIfTargetMissing") {
    if (!state.activeMetadataPhotoId || action.visiblePhotoIds.has(state.activeMetadataPhotoId)) {
      return state;
    }
    return {
      ...state,
      activeMetadataPhotoId: null,
      activeMetadataSourceSurfaceId: null,
    };
  }

  if (action.type === "openFaceAssignment") {
    return {
      ...state,
      activeFaceAssignment: {
        photoId: action.photoId,
        faceId: action.faceId,
        sourceSurfaceId: action.sourceSurfaceId,
      },
    };
  }

  if (action.type === "closeFaceAssignment") {
    return { ...state, activeFaceAssignment: null };
  }

  if (action.type === "setFaceBoxesVisible") {
    return { ...state, areFaceBoxesVisible: action.visible };
  }

  return state;
}
```

- [ ] **Step 6: Make library selection a compatibility re-export**

Replace `apps/ui/src/pages/library/librarySelection.ts` with compatibility aliases that import from `../photo-interactions/photoSelectionState`. Keep old export names until Library is migrated:

```ts
export {
  DEFAULT_PHOTO_SELECTION_STATE as DEFAULT_LIBRARY_SELECTION_STATE,
  formatPhotoSelectionScopeLabel as formatSelectionScopeLabel,
  parsePhotoSelectionRouteState as parseLibrarySelectionRouteState,
  photoSelectionReducer as librarySelectionReducer,
  resolvePhotoSelectionScopeCount as resolveSelectionScopeCount,
  serializePhotoSelectionState as serializeLibrarySelectionState,
} from "../photo-interactions/photoSelectionState";

export type {
  PhotoSelectionAction as LibrarySelectionAction,
  PhotoSelectionRouteState as LibrarySelectionRouteState,
  PhotoSelectionScope as LibrarySelectionScope,
  PhotoSelectionState as LibrarySelectionState,
} from "../photo-interactions/photoSelectionState";
```

- [ ] **Step 7: Run state tests**

Run:

```bash
npm --prefix apps/ui test -- photoSelectionState.test.ts photoInspectorState.test.ts librarySelection.test.ts
```

Expected: tests pass.

- [ ] **Step 8: Cleanup gate**

Run:

```bash
rg -n "DEFAULT_LIBRARY_SELECTION_STATE|librarySelectionReducer|LibrarySelectionState" apps/ui/src/pages
```

Expected: references may remain only in Library route files and compatibility tests. Do not delete the compatibility module until Library and Photo Detail route-state imports are migrated in later tasks.

- [ ] **Step 9: Commit shared state**

Run:

```bash
git add apps/ui/src/pages/photo-interactions/photoSelectionState.ts apps/ui/src/pages/photo-interactions/photoSelectionState.test.ts apps/ui/src/pages/photo-interactions/photoInspectorState.ts apps/ui/src/pages/photo-interactions/photoInspectorState.test.ts apps/ui/src/pages/library/librarySelection.ts apps/ui/src/pages/library/librarySelection.test.ts
git commit -m "feat: share photo selection and inspector state"
```

---

## Task 3: Shared Face Overlay And Photo Surface

**Files:**
- Create: `apps/ui/src/pages/photo-interactions/FaceOverlayLayer.tsx`
- Create: `apps/ui/src/pages/photo-interactions/FaceOverlayLayer.test.tsx`
- Create: `apps/ui/src/pages/photo-interactions/PhotoSurface.tsx`
- Create: `apps/ui/src/pages/photo-interactions/PhotoSurface.test.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`

- [ ] **Step 1: Write face overlay layer tests**

Create `apps/ui/src/pages/photo-interactions/FaceOverlayLayer.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FaceOverlayLayer } from "./FaceOverlayLayer";
import type { PhotoFace } from "./photoInteractionTypes";

const face: PhotoFace = {
  faceId: "face-1",
  personId: null,
  bbox: { x: 10, y: 10, width: 20, height: 20, spaceWidth: 100, spaceHeight: 100 },
  labelSource: null,
  confidence: null,
  modelVersion: null,
  provenance: null,
  labelRecordedTs: null,
  suggestions: [],
  canAssign: true,
  canCorrect: false,
  canDismiss: true,
  canConfirm: false,
};

describe("FaceOverlayLayer", () => {
  it("renders face controls and delegates face clicks", async () => {
    const user = userEvent.setup();
    const onOpenFace = vi.fn();

    render(
      <FaceOverlayLayer
        faces={[face]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible
        onOpenFace={onOpenFace}
      />
    );

    await user.click(screen.getByRole("button", { name: /open face 1 actions/i }));

    expect(onOpenFace).toHaveBeenCalledWith("face-1");
  });

  it("renders nothing when face boxes are hidden", () => {
    render(
      <FaceOverlayLayer
        faces={[face]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible={false}
        onOpenFace={vi.fn()}
      />
    );

    expect(screen.queryByRole("button", { name: /open face/i })).toBeNull();
  });
});
```

- [ ] **Step 2: Write photo surface tests**

Create `apps/ui/src/pages/photo-interactions/PhotoSurface.test.tsx`:

```tsx
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PhotoSurface } from "./PhotoSurface";
import type { PhotoSummary } from "./photoInteractionTypes";

const photo: PhotoSummary = {
  photoId: "photo-1",
  path: "/photos/lake.jpg",
  title: "lake.jpg",
  shotTs: null,
  filesize: 123,
  people: [],
  media: {
    thumbnail: {
      mimeType: "image/jpeg",
      width: 100,
      height: 80,
      dataBase64: "abc",
    },
    originalIntent: "detail-only",
    originalAvailability: null,
  },
  faces: [],
  albumMembership: null,
  defaultFaceBoxesVisible: false,
};

describe("PhotoSurface", () => {
  it("keeps selection, metadata, and detail navigation separate", async () => {
    const user = userEvent.setup();
    const onToggleSelected = vi.fn();
    const onOpenMetadata = vi.fn();

    render(
      <MemoryRouter>
        <PhotoSurface
          photo={photo}
          selected={false}
          faceBoxesVisible={false}
          activeMetadata={false}
          detailTo="/library/photo-1"
          onToggleSelected={onToggleSelected}
          onOpenMetadata={onOpenMetadata}
          onOpenFace={vi.fn()}
        />
      </MemoryRouter>
    );

    await user.click(screen.getByRole("checkbox", { name: /select photo lake.jpg/i }));
    expect(onToggleSelected).toHaveBeenCalledWith("photo-1");
    expect(onOpenMetadata).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /show metadata for lake.jpg/i }));
    expect(onOpenMetadata).toHaveBeenCalledWith("photo-1", "photo-surface-photo-1");
    expect(onToggleSelected).toHaveBeenCalledTimes(1);

    expect(screen.getByRole("link", { name: /open details for lake.jpg/i })).toHaveAttribute(
      "href",
      "/library/photo-1"
    );
  });

  it("marks the active metadata source", () => {
    render(
      <MemoryRouter>
        <PhotoSurface
          photo={photo}
          selected={false}
          faceBoxesVisible={false}
          activeMetadata
          detailTo="/library/photo-1"
          onToggleSelected={vi.fn()}
          onOpenMetadata={vi.fn()}
          onOpenFace={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByTestId("photo-surface-photo-1")).toHaveClass("photo-surface-active-metadata");
  });
});
```

- [ ] **Step 3: Run component tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- FaceOverlayLayer.test.tsx PhotoSurface.test.tsx
```

Expected: fails because components do not exist.

- [ ] **Step 4: Implement `FaceOverlayLayer`**

Create `apps/ui/src/pages/photo-interactions/FaceOverlayLayer.tsx`:

```tsx
import { buildFaceOverlayRegions, FaceBBoxOverlay } from "../FaceBBoxOverlay";
import type { PhotoFace } from "./photoInteractionTypes";

interface FaceOverlayLayerProps {
  faces: PhotoFace[];
  thumbnailSize: { width: number; height: number } | null;
  visible: boolean;
  onOpenFace: (faceId: string) => void;
}

export function FaceOverlayLayer({
  faces,
  thumbnailSize,
  visible,
  onOpenFace,
}: FaceOverlayLayerProps) {
  if (!visible || !thumbnailSize) {
    return null;
  }

  const regions = buildFaceOverlayRegions(
    faces.map((face) => ({
      face_id: face.faceId,
      person_id: face.personId,
      bbox_x: face.bbox.x,
      bbox_y: face.bbox.y,
      bbox_w: face.bbox.width,
      bbox_h: face.bbox.height,
      bbox_space_width: face.bbox.spaceWidth,
      bbox_space_height: face.bbox.spaceHeight,
      label_source: face.labelSource,
    })),
    thumbnailSize.width,
    thumbnailSize.height
  );

  return (
    <FaceBBoxOverlay
      regions={regions}
      allowRegionHover
      ariaLabel="Detected face regions"
      onRegionClick={(region) => onOpenFace(region.faceId)}
      renderRegionContent={(_region, index) => (
        <button
          type="button"
          className="photo-face-region-button"
          aria-label={`Open face ${index + 1} actions`}
          onClick={(event) => {
            event.stopPropagation();
            onOpenFace(_region.faceId);
          }}
        >
          {index + 1}
        </button>
      )}
    />
  );
}
```

- [ ] **Step 5: Implement `PhotoSurface`**

Create `apps/ui/src/pages/photo-interactions/PhotoSurface.tsx`:

```tsx
import { Link } from "react-router-dom";
import { FaceOverlayLayer } from "./FaceOverlayLayer";
import type { PhotoSummary } from "./photoInteractionTypes";

interface PhotoSurfaceProps {
  photo: PhotoSummary;
  selected: boolean;
  faceBoxesVisible: boolean;
  activeMetadata: boolean;
  detailTo: string;
  onToggleSelected: (photoId: string) => void;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (photoId: string, faceId: string, sourceSurfaceId: string) => void;
}

export function buildPhotoSurfaceId(photoId: string): string {
  return `photo-surface-${photoId}`;
}

export function PhotoSurface({
  photo,
  selected,
  faceBoxesVisible,
  activeMetadata,
  detailTo,
  onToggleSelected,
  onOpenMetadata,
  onOpenFace,
}: PhotoSurfaceProps) {
  const surfaceId = buildPhotoSurfaceId(photo.photoId);
  const thumbnail = photo.media.thumbnail;

  return (
    <article
      data-testid={surfaceId}
      className={`photo-surface${selected ? " photo-surface-selected" : ""}${
        activeMetadata ? " photo-surface-active-metadata" : ""
      }`}
    >
      <label className="photo-surface-select">
        <input
          type="checkbox"
          checked={selected}
          aria-label={`Select photo ${photo.title}`}
          onChange={() => onToggleSelected(photo.photoId)}
        />
      </label>

      <div
        className="photo-surface-media"
        style={thumbnail ? { aspectRatio: `${thumbnail.width} / ${thumbnail.height}` } : undefined}
      >
        <Link className="photo-surface-link" to={detailTo} aria-label={`Open details for ${photo.title}`}>
          {thumbnail ? (
            <img
              className="photo-surface-image"
              src={`data:${thumbnail.mimeType};base64,${thumbnail.dataBase64}`}
              width={thumbnail.width}
              height={thumbnail.height}
              alt={`Preview of ${photo.path}`}
            />
          ) : (
            <div className="photo-surface-placeholder" aria-hidden="true">
              No preview
            </div>
          )}
        </Link>
        <FaceOverlayLayer
          faces={photo.faces}
          thumbnailSize={thumbnail ? { width: thumbnail.width, height: thumbnail.height } : null}
          visible={faceBoxesVisible}
          onOpenFace={(faceId) => onOpenFace(photo.photoId, faceId, surfaceId)}
        />
      </div>

      <div className="photo-surface-body">
        <p className="photo-surface-title" title={photo.path}>
          {photo.title}
        </p>
        <button
          type="button"
          className="photo-surface-metadata-button"
          onClick={() => onOpenMetadata(photo.photoId, surfaceId)}
        >
          Show metadata
        </button>
      </div>
    </article>
  );
}
```

- [ ] **Step 6: Add shared CSS**

Modify `apps/ui/src/styles/app-shell.css` with these shared selectors near existing photo/card styles:

```css
.photo-surface {
  position: relative;
  border: 1px solid var(--border-subtle, #d7dde8);
  border-radius: 8px;
  background: var(--surface, #fff);
  overflow: hidden;
}

.photo-surface-selected {
  border-color: var(--accent, #2563eb);
}

.photo-surface-active-metadata {
  border-color: var(--accent, #2563eb);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
}

.photo-surface-select {
  position: absolute;
  z-index: 3;
  top: 8px;
  left: 8px;
}

.photo-surface-media {
  position: relative;
  background: #f8fafc;
}

.photo-surface-link {
  display: block;
}

.photo-surface-image,
.photo-surface-placeholder {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-surface-placeholder {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
}

.photo-face-region-button {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 999px;
  border: 1px solid #fff;
  background: rgba(37, 99, 235, 0.9);
  color: #fff;
}
```

- [ ] **Step 7: Run component tests**

Run:

```bash
npm --prefix apps/ui test -- FaceOverlayLayer.test.tsx PhotoSurface.test.tsx
```

Expected: tests pass.

- [ ] **Step 8: Cleanup gate**

Run:

```bash
rg -n "photo-surface|photo-face-region-button|FaceBBoxOverlay" apps/ui/src/pages apps/ui/src/styles/app-shell.css
```

Expected: `FaceBBoxOverlay` still appears because routes are not migrated yet. Do not delete it in this task.

- [ ] **Step 9: Commit surface primitives**

Run:

```bash
git add apps/ui/src/pages/photo-interactions/FaceOverlayLayer.tsx apps/ui/src/pages/photo-interactions/FaceOverlayLayer.test.tsx apps/ui/src/pages/photo-interactions/PhotoSurface.tsx apps/ui/src/pages/photo-interactions/PhotoSurface.test.tsx apps/ui/src/styles/app-shell.css
git commit -m "feat: add shared photo surface primitives"
```

---

## Task 4: Shared Metadata Flyout

**Files:**
- Create: `apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.tsx`
- Create: `apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.test.tsx`
- Modify: `apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`

- [ ] **Step 1: Write shared metadata flyout tests**

Create `apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PhotoMetadataFlyout } from "./PhotoMetadataFlyout";

describe("PhotoMetadataFlyout", () => {
  it("shows active photo identity and closes without mutating route state", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <PhotoMetadataFlyout
        isOpen
        summary={{
          photoId: "photo-1",
          title: "lake.jpg",
          path: "/photos/lake.jpg",
          thumbnail: {
            mimeType: "image/jpeg",
            width: 100,
            height: 80,
            dataBase64: "abc",
          },
        }}
        detail={null}
        isLoadingDetail={false}
        detailError={null}
        onClose={onClose}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByRole("complementary", { name: /metadata for lake.jpg/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close metadata/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows scoped retry when detail loading fails", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    render(
      <PhotoMetadataFlyout
        isOpen
        summary={{ photoId: "photo-1", title: "lake.jpg", path: "/photos/lake.jpg", thumbnail: null }}
        detail={null}
        isLoadingDetail={false}
        detailError="Could not load metadata."
        onClose={vi.fn()}
        onRetry={onRetry}
      />
    );

    expect(screen.getByText("Could not load metadata.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry metadata/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run metadata flyout tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- PhotoMetadataFlyout.test.tsx
```

Expected: fails because shared component does not exist.

- [ ] **Step 3: Implement shared metadata flyout**

Create `apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.tsx` by moving the render logic from `apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx` and changing props to accept a lightweight summary plus optional full detail:

```tsx
import type { PhotoDetailPayload } from "../photo-detail/photoDetailTypes";
import {
  MISSING_VALUE,
  formatExifAttributeValue,
  formatFilesize,
  formatGps,
  formatOptionalText,
  formatTimestamp,
} from "../photo-detail/photoDetailFormatting";

export interface PhotoMetadataSummary {
  photoId: string;
  title: string;
  path: string;
  thumbnail: {
    mimeType: string;
    width: number;
    height: number;
    dataBase64: string;
  } | null;
}

interface PhotoMetadataFlyoutProps {
  isOpen: boolean;
  summary: PhotoMetadataSummary | null;
  detail: PhotoDetailPayload | null;
  isLoadingDetail: boolean;
  detailError: string | null;
  onClose: () => void;
  onRetry: () => void;
}

export function PhotoMetadataFlyout({
  isOpen,
  summary,
  detail,
  isLoadingDetail,
  detailError,
  onClose,
  onRetry,
}: PhotoMetadataFlyoutProps) {
  if (!isOpen || !summary) {
    return null;
  }

  const exifEntries = detail?.metadata.exif_attributes
    ? Object.entries(detail.metadata.exif_attributes).sort(([left], [right]) =>
        left.localeCompare(right, "en-US")
      )
    : [];

  return (
    <aside className="detail-flyout is-open" aria-label={`Metadata for ${summary.title}`}>
      <div className="detail-flyout-header">
        <div>
          <h2>{summary.title}</h2>
          <p className="detail-path">{summary.path}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close metadata">
          Close
        </button>
      </div>

      {summary.thumbnail ? (
        <img
          className="detail-flyout-thumbnail"
          src={`data:${summary.thumbnail.mimeType};base64,${summary.thumbnail.dataBase64}`}
          width={summary.thumbnail.width}
          height={summary.thumbnail.height}
          alt={`Preview of ${summary.path}`}
        />
      ) : null}

      {isLoadingDetail ? <p role="status">Loading metadata.</p> : null}
      {detailError ? (
        <div className="feedback-panel feedback-panel-error">
          <p>{detailError}</p>
          <button type="button" onClick={onRetry}>
            Retry metadata
          </button>
        </div>
      ) : null}

      {detail ? (
        <>
          <article className="detail-panel">
            <h2>Summary</h2>
            <dl>
              <div><dt>Captured</dt><dd>{formatTimestamp(detail.shot_ts)}</dd></div>
              <div><dt>File size</dt><dd>{formatFilesize(detail.filesize)}</dd></div>
              <div><dt>Camera make</dt><dd>{formatOptionalText(detail.camera_make)}</dd></div>
              <div><dt>Orientation</dt><dd>{formatOptionalText(detail.orientation)}</dd></div>
              <div><dt>Availability</dt><dd>{detail.original?.availability_state ?? "Unknown availability"}</dd></div>
            </dl>
          </article>

          <article className="detail-panel">
            <h2>Metadata</h2>
            <dl>
              <div><dt>SHA-256</dt><dd>{detail.metadata.sha256}</dd></div>
              <div><dt>Perceptual hash</dt><dd>{formatOptionalText(detail.metadata.phash)}</dd></div>
              <div><dt>Timestamp source</dt><dd>{formatOptionalText(detail.metadata.shot_ts_source)}</dd></div>
              <div><dt>Camera model</dt><dd>{formatOptionalText(detail.metadata.camera_model)}</dd></div>
              <div><dt>Software</dt><dd>{formatOptionalText(detail.metadata.software)}</dd></div>
              <div><dt>GPS</dt><dd>{formatGps(detail.metadata.gps_latitude, detail.metadata.gps_longitude)}</dd></div>
              <div>
                <dt>GPS altitude</dt>
                <dd>{detail.metadata.gps_altitude === null ? MISSING_VALUE : `${detail.metadata.gps_altitude.toFixed(1)} m`}</dd>
              </div>
              <div><dt>Faces</dt><dd>{detail.metadata.faces_count === 1 ? "1 detected" : `${detail.metadata.faces_count} detected`}</dd></div>
            </dl>
            {exifEntries.length > 0 ? (
              <details className="detail-exif-attributes">
                <summary>Show all EXIF attributes</summary>
                <dl className="detail-exif-attributes-list">
                  {exifEntries.map(([name, value]) => (
                    <div key={name}><dt>{name}</dt><dd>{formatExifAttributeValue(value)}</dd></div>
                  ))}
                </dl>
              </details>
            ) : null}
          </article>
        </>
      ) : null}
    </aside>
  );
}
```

- [ ] **Step 4: Update Photo Detail to use shared flyout**

Modify `apps/ui/src/pages/PhotoDetailRoutePage.tsx` to import shared `PhotoMetadataFlyout` from `./photo-interactions/PhotoMetadataFlyout`. Pass `summary` from the loaded detail and keep `detail` as the already loaded full payload. Keep existing `isDetailFlyoutOpen` behavior.

- [ ] **Step 5: Run Photo Detail tests**

Run:

```bash
npm --prefix apps/ui test -- PhotoMetadataFlyout.test.tsx PhotoDetailRoutePage.test.tsx
```

Expected: tests pass. If the shared flyout changes an aria label, update the affected assertion in the same task before proceeding.

- [ ] **Step 6: Cleanup gate**

Run:

```bash
rg -n "photo-detail/PhotoMetadataFlyout|PhotoMetadataFlyout" apps/ui/src/pages
```

Expected: no imports from `photo-detail/PhotoMetadataFlyout`. Delete `apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx` if no imports remain.

- [ ] **Step 7: Commit metadata flyout**

Run:

```bash
git add apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.tsx apps/ui/src/pages/photo-interactions/PhotoMetadataFlyout.test.tsx apps/ui/src/pages/PhotoDetailRoutePage.tsx apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx
git commit -m "feat: share photo metadata flyout"
```

---

## Task 5: Shared Face Assignment Modal

**Files:**
- Create: `apps/ui/src/pages/photo-interactions/FaceAssignmentModal.tsx`
- Create: `apps/ui/src/pages/photo-interactions/FaceAssignmentModal.test.tsx`
- Modify: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Modify: `apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx`

- [ ] **Step 1: Write shared face modal tests**

Create `apps/ui/src/pages/photo-interactions/FaceAssignmentModal.test.tsx` by porting the current `PhotoFaceAssignmentModal` tests and adding this test:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FaceAssignmentModal } from "./FaceAssignmentModal";
import type { PhotoFace, PhotoSummary } from "./photoInteractionTypes";

const face: PhotoFace = {
  faceId: "face-1",
  personId: null,
  bbox: { x: 10, y: 10, width: 40, height: 40, spaceWidth: 100, spaceHeight: 100 },
  labelSource: null,
  confidence: null,
  modelVersion: null,
  provenance: null,
  labelRecordedTs: null,
  suggestions: [],
  canAssign: true,
  canCorrect: false,
  canDismiss: true,
  canConfirm: false,
};

const photo: PhotoSummary = {
  photoId: "photo-1",
  path: "/photos/lake.jpg",
  title: "lake.jpg",
  shotTs: null,
  filesize: 1,
  people: [],
  media: {
    thumbnail: { mimeType: "image/jpeg", width: 100, height: 100, dataBase64: "abc" },
    originalIntent: "detail-only",
    originalAvailability: null,
  },
  faces: [face],
  albumMembership: null,
  defaultFaceBoxesVisible: false,
};

describe("FaceAssignmentModal", () => {
  it("shows full thumbnail context independent from the underlying grid", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <FaceAssignmentModal
        isOpen
        photo={photo}
        face={face}
        people={[]}
        onClose={onClose}
        onFaceUpdated={vi.fn()}
        onFaceDismissed={vi.fn()}
        onPersonCreated={vi.fn()}
      />
    );

    expect(screen.getByRole("dialog", { name: /face assignment for lake.jpg/i })).toBeInTheDocument();
    expect(screen.getByAltText("Preview of /photos/lake.jpg")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run shared face modal tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- FaceAssignmentModal.test.tsx
```

Expected: fails because shared modal does not exist.

- [ ] **Step 3: Implement shared face modal**

Create `apps/ui/src/pages/photo-interactions/FaceAssignmentModal.tsx` by moving the current implementation from `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx` and changing props from detail-specific thumbnail/region shapes to shared `PhotoSummary` and `PhotoFace`. Preserve the existing API calls from `face-labeling/faceLabelingApi`.

Required prop shape:

```ts
interface FaceAssignmentModalProps {
  isOpen: boolean;
  photo: PhotoSummary | null;
  face: PhotoFace | null;
  people: Array<{ person_id: string; display_name: string; created_ts?: string; updated_ts?: string }>;
  onClose: () => void;
  onFaceUpdated: (faceId: string, personId: string) => void;
  onFaceDismissed: (faceId: string) => void;
  onPersonCreated: (person: { person_id: string; display_name: string; created_ts?: string; updated_ts?: string }) => void;
}
```

The modal should build crop/face context from `photo.media.thumbnail` and `face.bbox`. The full thumbnail must always be visible when available, even if a crop preview is also shown.

- [ ] **Step 4: Replace Photo Detail modal import**

Modify `apps/ui/src/pages/PhotoDetailRoutePage.tsx` to use the shared modal. Use `adaptPhotoDetail(detail)` to produce the `PhotoSummary` passed to the modal.

- [ ] **Step 5: Update Library face panel temporarily**

Modify `apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx` only enough to compile with the shared modal if it imports the old modal. Full Library migration happens later.

- [ ] **Step 6: Run modal and route tests**

Run:

```bash
npm --prefix apps/ui test -- FaceAssignmentModal.test.tsx PhotoDetailRoutePage.test.tsx
```

Expected: tests pass.

- [ ] **Step 7: Cleanup gate**

Run:

```bash
rg -n "PhotoFaceAssignmentModal|FaceAssignmentModal" apps/ui/src/pages
```

Expected: no imports of `PhotoFaceAssignmentModal`. Delete `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx` if no imports remain.

- [ ] **Step 8: Commit shared modal**

Run:

```bash
git add apps/ui/src/pages/photo-interactions/FaceAssignmentModal.tsx apps/ui/src/pages/photo-interactions/FaceAssignmentModal.test.tsx apps/ui/src/pages/PhotoDetailRoutePage.tsx apps/ui/src/pages/PhotoFaceAssignmentModal.tsx apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx
git commit -m "feat: share face assignment modal"
```

---

## Task 6: Shared Album Action Surface

**Files:**
- Create: `apps/ui/src/pages/photo-interactions/AlbumActionSurface.tsx`
- Create: `apps/ui/src/pages/photo-interactions/AlbumActionSurface.test.tsx`
- Modify: `apps/ui/src/pages/library/AddToAlbumDialog.tsx`
- Modify: `apps/ui/src/pages/library/useLibraryBulkActions.ts`

- [ ] **Step 1: Write album action tests**

Create `apps/ui/src/pages/photo-interactions/AlbumActionSurface.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AlbumActionSurface } from "./AlbumActionSurface";
import type { AlbumTarget } from "./photoInteractionTypes";

const albums: AlbumTarget[] = [
  { albumId: "album-1", name: "Family", kind: "manual", canAcceptManualAdditions: true },
  { albumId: "album-2", name: "Saved filter", kind: "saved_filter", canAcceptManualAdditions: false },
];

describe("AlbumActionSurface", () => {
  it("submits selected photo ids to an eligible album", async () => {
    const user = userEvent.setup();
    const onAddToAlbum = vi.fn();

    render(
      <AlbumActionSurface
        albums={albums}
        selectedPhotoIds={["photo-1", "photo-2"]}
        isSubmitting={false}
        resultMessage={null}
        onAddToAlbum={onAddToAlbum}
        onCreateAlbumAndAdd={vi.fn()}
      />
    );

    await user.selectOptions(screen.getByLabelText(/album/i), "album-1");
    await user.click(screen.getByRole("button", { name: /add 2 photos/i }));

    expect(onAddToAlbum).toHaveBeenCalledWith("album-1", ["photo-1", "photo-2"]);
  });

  it("does not offer saved-filter albums as manual targets", () => {
    render(
      <AlbumActionSurface
        albums={albums}
        selectedPhotoIds={["photo-1"]}
        isSubmitting={false}
        resultMessage={null}
        onAddToAlbum={vi.fn()}
        onCreateAlbumAndAdd={vi.fn()}
      />
    );

    expect(screen.queryByRole("option", { name: "Saved filter" })).toBeNull();
  });
});
```

- [ ] **Step 2: Run album action tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- AlbumActionSurface.test.tsx
```

Expected: fails because component does not exist.

- [ ] **Step 3: Implement album action surface**

Create `apps/ui/src/pages/photo-interactions/AlbumActionSurface.tsx`:

```tsx
import { useMemo, useState } from "react";
import type { AlbumTarget } from "./photoInteractionTypes";

interface AlbumActionSurfaceProps {
  albums: AlbumTarget[];
  selectedPhotoIds: string[];
  isSubmitting: boolean;
  resultMessage: string | null;
  onAddToAlbum: (albumId: string, photoIds: string[]) => void;
  onCreateAlbumAndAdd: (name: string, photoIds: string[]) => void;
}

export function AlbumActionSurface({
  albums,
  selectedPhotoIds,
  isSubmitting,
  resultMessage,
  onAddToAlbum,
  onCreateAlbumAndAdd,
}: AlbumActionSurfaceProps) {
  const [selectedAlbumId, setSelectedAlbumId] = useState("");
  const [newAlbumName, setNewAlbumName] = useState("");
  const eligibleAlbums = useMemo(
    () => albums.filter((album) => album.canAcceptManualAdditions),
    [albums]
  );
  const countLabel = `${selectedPhotoIds.length} photo${selectedPhotoIds.length === 1 ? "" : "s"}`;
  const disabled = isSubmitting || selectedPhotoIds.length === 0;

  return (
    <section className="album-action-surface" aria-label="Album actions">
      <label>
        Album
        <select
          value={selectedAlbumId}
          disabled={disabled}
          onChange={(event) => setSelectedAlbumId(event.currentTarget.value)}
        >
          <option value="">Select album</option>
          {eligibleAlbums.map((album) => (
            <option key={album.albumId} value={album.albumId}>
              {album.name}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        disabled={disabled || selectedAlbumId.length === 0}
        onClick={() => onAddToAlbum(selectedAlbumId, selectedPhotoIds)}
      >
        Add {countLabel}
      </button>

      <label>
        New album
        <input
          value={newAlbumName}
          disabled={disabled}
          onChange={(event) => setNewAlbumName(event.currentTarget.value)}
        />
      </label>
      <button
        type="button"
        disabled={disabled || newAlbumName.trim().length === 0}
        onClick={() => onCreateAlbumAndAdd(newAlbumName.trim(), selectedPhotoIds)}
      >
        Create and add {countLabel}
      </button>

      {resultMessage ? <p className="album-action-result">{resultMessage}</p> : null}
    </section>
  );
}
```

- [ ] **Step 4: Run album tests**

Run:

```bash
npm --prefix apps/ui test -- AlbumActionSurface.test.tsx
```

Expected: tests pass.

- [ ] **Step 5: Cleanup gate**

Run:

```bash
rg -n "AddToAlbumDialog|AlbumActionSurface|create.*album|add.*album" apps/ui/src/pages
```

Expected: existing Library dialog remains until Library migration. Do not delete it in this task.

- [ ] **Step 6: Commit album action surface**

Run:

```bash
git add apps/ui/src/pages/photo-interactions/AlbumActionSurface.tsx apps/ui/src/pages/photo-interactions/AlbumActionSurface.test.tsx
git commit -m "feat: add shared album action surface"
```

---

## Task 7: Migrate Library To Shared Photo Surface

**Files:**
- Modify: `apps/ui/src/pages/library/LibraryPhotoGrid.tsx`
- Modify: `apps/ui/src/pages/LibraryRoutePage.tsx`
- Modify: `apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx`
- Modify: `apps/ui/src/pages/library/LibrarySelectionPanel.tsx`
- Modify: `apps/ui/src/pages/LibraryRoutePage.test.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`

- [ ] **Step 1: Add Library route test for shared interactions**

Extend `apps/ui/src/pages/LibraryRoutePage.test.tsx` with a test that verifies thumbnail navigation, selection, and metadata are separate:

```tsx
it("keeps library photo selection while opening metadata from a shared photo surface", async () => {
  const user = userEvent.setup();
  renderLibraryRoute();

  await user.click(await screen.findByRole("checkbox", { name: /select photo/i }));
  await user.click(screen.getByRole("button", { name: /show metadata/i }));

  expect(screen.getByRole("checkbox", { name: /select photo/i })).toBeChecked();
  expect(screen.getByRole("complementary", { name: /metadata/i })).toBeInTheDocument();
});
```

Adjust helper names to match the existing test setup.

- [ ] **Step 2: Run Library test and verify it fails**

Run:

```bash
npm --prefix apps/ui test -- LibraryRoutePage.test.tsx
```

Expected: new assertion fails until Library uses shared metadata/photo surface.

- [ ] **Step 3: Replace LibraryPhotoGrid card rendering**

Modify `apps/ui/src/pages/library/LibraryPhotoGrid.tsx` to adapt photos and render `PhotoGridSurface` or `PhotoSurface` directly. Preserve route state passed to detail links.

Key mapping:

```tsx
const summary = adaptLibraryPhoto(photo);
<PhotoSurface
  photo={summary}
  selected={selectedPhotoIds.has(photo.photo_id)}
  faceBoxesVisible={faceBoxesVisible}
  activeMetadata={activeMetadataPhotoId === photo.photo_id}
  detailTo={`/library/${photo.photo_id}`}
  onToggleSelected={onTogglePhotoSelection}
  onOpenMetadata={onOpenMetadata}
  onOpenFace={onOpenFace}
/>
```

- [ ] **Step 4: Wire Library inspector state**

Modify `apps/ui/src/pages/LibraryRoutePage.tsx` to own `photoInspectorReducer`. Add normal-grid default:

```ts
const [photoInspectorState, dispatchPhotoInspector] = useReducer(
  photoInspectorReducer,
  DEFAULT_PHOTO_INSPECTOR_STATE
);
```

Render a screen-level face-box toggle that dispatches `setFaceBoxesVisible`.

- [ ] **Step 5: Wire shared metadata flyout in Library**

When `activeMetadataPhotoId` changes, fetch `/api/v1/photos/{photoId}` using existing photo detail API. Pass staged summary and loaded detail into shared `PhotoMetadataFlyout`.

- [ ] **Step 6: Remove Library face panel if fully replaced**

If shared face modal covers assignment, correction, confirmation, unknown, and false-positive from Library surfaces, delete `apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx` and remove its imports/usages. If confirmation still lacks a shared entry point, keep only the smallest temporary wrapper and add a comment referencing Task 11 cleanup.

- [ ] **Step 7: Run Library tests**

Run:

```bash
npm --prefix apps/ui test -- LibraryRoutePage.test.tsx LibraryActionBar.test.tsx librarySelection.test.ts
```

Expected: tests pass.

- [ ] **Step 8: Cleanup gate**

Run:

```bash
rg -n "browse-thumbnail|browse-card|LibraryPhotoFacePanel|Review faces|Hide face review" apps/ui/src/pages apps/ui/src/styles/app-shell.css
```

Expected: remove obsolete Library-only card/face-panel selectors and tests if no route imports remain. Keep generic `browse-` selectors only if other routes still use them.

- [ ] **Step 9: Commit Library migration**

Run:

```bash
git add apps/ui/src/pages/library/LibraryPhotoGrid.tsx apps/ui/src/pages/LibraryRoutePage.tsx apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx apps/ui/src/pages/library/LibrarySelectionPanel.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx apps/ui/src/styles/app-shell.css
git commit -m "feat: migrate library to shared photo interactions"
```

---

## Task 8: Migrate Suggestions With Separate Photo And Face Selection

**Files:**
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.tsx`
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/suggestions/SuggestionsGrid.tsx`
- Modify: `apps/ui/src/pages/suggestions/SuggestionFaceRow.tsx`
- Modify: `apps/ui/src/pages/suggestions/useSuggestionsActions.ts`
- Modify: `apps/ui/src/styles/app-shell.css`

- [ ] **Step 1: Add Suggestions selection separation tests**

Extend `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`:

```tsx
it("keeps photo selection separate from selected suggestion faces", async () => {
  const user = userEvent.setup();
  renderSuggestionsRoute();

  await user.click(await screen.findByRole("checkbox", { name: /select photo/i }));
  await user.click(screen.getByRole("checkbox", { name: /confirm suggestion for face/i }));

  expect(screen.getByRole("checkbox", { name: /select photo/i })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /confirm suggestion for face/i })).toBeChecked();
});

it("uses selected photos for album actions without clearing selected faces", async () => {
  const user = userEvent.setup();
  renderSuggestionsRoute();

  await user.click(await screen.findByRole("checkbox", { name: /select photo/i }));
  await user.click(screen.getByRole("checkbox", { name: /confirm suggestion for face/i }));
  await user.click(screen.getByRole("button", { name: /add selected photos to album/i }));

  expect(screen.getByRole("checkbox", { name: /confirm suggestion for face/i })).toBeChecked();
});
```

Adjust button names to match the final `AlbumActionSurface` integration.

- [ ] **Step 2: Run Suggestions tests and verify they fail**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage.test.tsx
```

Expected: new tests fail because Suggestions has no photo selection/album action surface yet.

- [ ] **Step 3: Add photo selection state to Suggestions**

Modify `SuggestionsRoutePage.tsx` to use `photoSelectionReducer` for photo selection. Keep existing `selectedFaceIds` untouched.

- [ ] **Step 4: Render Suggestions cards through shared photo surface**

Modify `SuggestionsGrid.tsx` to adapt each suggestion photo with `adaptSuggestionPhoto`. Pass `faceBoxesVisible` defaulting to true from `photoInspectorState`.

- [ ] **Step 5: Preserve face-review rows**

Keep `SuggestionFaceRow` for batch review controls. Do not merge face checkboxes with photo selection.

- [ ] **Step 6: Add album action surface to Suggestions**

Use `AlbumActionSurface` with selected photo ids. Reuse existing album API functions from Library route modules, or extract them to a shared album API module if importing from Library creates route coupling.

- [ ] **Step 7: Run Suggestions tests**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage.test.tsx
```

Expected: tests pass.

- [ ] **Step 8: Cleanup gate**

Run:

```bash
rg -n "suggestions-thumbnail|suggestions-thumbnail-shell|suggestions-face-overlay|selectedFaceIds|selectedPhotoIds" apps/ui/src/pages/suggestions apps/ui/src/pages/SuggestionsRoutePage.tsx apps/ui/src/styles/app-shell.css
```

Expected: `selectedFaceIds` remains for batch review. Remove obsolete Suggestions thumbnail/overlay selectors if shared surface replaced them.

- [ ] **Step 9: Commit Suggestions migration**

Run:

```bash
git add apps/ui/src/pages/SuggestionsRoutePage.tsx apps/ui/src/pages/SuggestionsRoutePage.test.tsx apps/ui/src/pages/suggestions/SuggestionsGrid.tsx apps/ui/src/pages/suggestions/SuggestionFaceRow.tsx apps/ui/src/pages/suggestions/useSuggestionsActions.ts apps/ui/src/styles/app-shell.css
git commit -m "feat: add shared photo interactions to suggestions"
```

---

## Task 9: Migrate Albums To Shared Photo Surface And Album Actions

**Files:**
- Modify: `apps/ui/src/pages/AlbumsRoutePage.tsx`
- Modify: `apps/ui/src/pages/AlbumsRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/albums/AlbumsGrid.tsx`
- Modify: `apps/ui/src/pages/albums/AlbumDetailInline.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`

- [ ] **Step 1: Add Albums route test**

Extend `apps/ui/src/pages/AlbumsRoutePage.test.tsx`:

```tsx
it("uses shared photo selection and metadata inside album detail", async () => {
  const user = userEvent.setup();
  renderAlbumsRoute();

  await user.click(await screen.findByRole("button", { name: /open album/i }));
  await user.click(await screen.findByRole("checkbox", { name: /select photo/i }));
  await user.click(screen.getByRole("button", { name: /show metadata/i }));

  expect(screen.getByRole("checkbox", { name: /select photo/i })).toBeChecked();
  expect(screen.getByRole("complementary", { name: /metadata/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run Albums test and verify it fails**

Run:

```bash
npm --prefix apps/ui test -- AlbumsRoutePage.test.tsx
```

Expected: fails until album detail photos use shared surface.

- [ ] **Step 3: Migrate album detail photos**

Modify `AlbumDetailInline.tsx` to render photos through shared adapters and `PhotoSurface`. If album detail currently derives library search photos through `albumLibraryQuery`, keep that query path and adapt its results.

- [ ] **Step 4: Wire metadata and face modal in album detail**

Use the same `photoInspectorReducer`, shared metadata flyout, and shared face modal wiring used by Library.

- [ ] **Step 5: Wire album membership hints**

When current album id is known, populate `PhotoAlbumMembership.currentAlbumId` for each adapted photo. Use this only for display/disable states; do not block backend validation.

- [ ] **Step 6: Run Albums tests**

Run:

```bash
npm --prefix apps/ui test -- AlbumsRoutePage.test.tsx albumLibraryQuery.test.ts
```

Expected: tests pass.

- [ ] **Step 7: Cleanup gate**

Run:

```bash
rg -n "album.*thumbnail|AlbumDetailInline|photo-surface|browse-thumbnail" apps/ui/src/pages/albums apps/ui/src/pages/AlbumsRoutePage.tsx apps/ui/src/styles/app-shell.css
```

Expected: remove obsolete album-specific thumbnail/card selectors replaced by shared photo surface.

- [ ] **Step 8: Commit Albums migration**

Run:

```bash
git add apps/ui/src/pages/AlbumsRoutePage.tsx apps/ui/src/pages/AlbumsRoutePage.test.tsx apps/ui/src/pages/albums/AlbumsGrid.tsx apps/ui/src/pages/albums/AlbumDetailInline.tsx apps/ui/src/styles/app-shell.css
git commit -m "feat: migrate albums to shared photo interactions"
```

---

## Task 10: Migrate Photo Detail Selection And Shared Inspectors

**Files:**
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/photo-detail/PhotoPreviewPanel.tsx`
- Modify: `apps/ui/src/pages/photo-detail/useOriginalImageFallback.ts`
- Modify: `apps/ui/src/styles/app-shell.css`

- [ ] **Step 1: Add Photo Detail selection test**

Extend `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`:

```tsx
it("exposes photo selection on detail without disabling original image loading", async () => {
  const user = userEvent.setup();
  renderPhotoDetailRoute();

  const image = await screen.findByRole("img", { name: /preview for photo-1/i });
  expect(image).toHaveAttribute("src", "/api/v1/photos/photo-1/original");

  await user.click(screen.getByRole("checkbox", { name: /select photo/i }));
  expect(screen.getByRole("checkbox", { name: /select photo/i })).toBeChecked();
});
```

- [ ] **Step 2: Run Photo Detail test and verify it fails**

Run:

```bash
npm --prefix apps/ui test -- PhotoDetailRoutePage.test.tsx
```

Expected: new selection assertion fails.

- [ ] **Step 3: Add shared selection to Photo Detail**

Modify `PhotoDetailRoutePage.tsx` to parse incoming photo selection route state using shared photo selection helpers. Render a selected/unselected control in the detail header or preview controls.

- [ ] **Step 4: Keep original loading behavior unchanged**

Do not change `useOriginalImageFallback` behavior except type imports needed by shared `PhotoMedia`. Existing tests for automatic original loading must keep passing.

- [ ] **Step 5: Replace detail face overlay with shared layer where practical**

Modify `PhotoPreviewPanel.tsx` to use `FaceOverlayLayer` or keep its current original-image-specific overlay only if shared layer cannot yet support active original image coordinate space. If kept, add a final cleanup item in Task 11.

- [ ] **Step 6: Run Photo Detail tests**

Run:

```bash
npm --prefix apps/ui test -- PhotoDetailRoutePage.test.tsx
```

Expected: tests pass.

- [ ] **Step 7: Cleanup gate**

Run:

```bash
rg -n "PhotoPreviewPanel|detail-face-overlay|FaceBBoxOverlay|PhotoMetadataFlyout|PhotoFaceAssignmentModal" apps/ui/src/pages apps/ui/src/styles/app-shell.css
```

Expected: no references to deleted old metadata/modal components. Keep `PhotoPreviewPanel` only if it still owns original-image-specific preview concerns.

- [ ] **Step 8: Commit Photo Detail migration**

Run:

```bash
git add apps/ui/src/pages/PhotoDetailRoutePage.tsx apps/ui/src/pages/PhotoDetailRoutePage.test.tsx apps/ui/src/pages/photo-detail/PhotoPreviewPanel.tsx apps/ui/src/pages/photo-detail/useOriginalImageFallback.ts apps/ui/src/styles/app-shell.css
git commit -m "feat: align photo detail with shared interactions"
```

---

## Task 11: Final Dead-Code Audit And Verification

**Files:**
- Review and update/delete files returned by the audit commands in this task.
- Modify: affected tests and CSS identified by those commands.

- [ ] **Step 1: Search for obsolete components**

Run:

```bash
rg -n "PhotoFaceAssignmentModal|PhotoMetadataFlyout|LibraryPhotoFacePanel|FaceBBoxOverlay|browse-card|browse-thumbnail|suggestions-thumbnail|suggestions-face-overlay" apps/ui/src
```

Expected: old component names should not appear unless intentionally retained. For every remaining match, either delete it or document why it remains in the final verification notes.

- [ ] **Step 2: Search for duplicated state/domain logic**

Run:

```bash
rg -n "selectedPhotoIds|selectedFaceIds|activeMetadata|activeFaceAssignment|readErrorDetail|applyFaceAssignment|AddToAlbumDialog" apps/ui/src/pages
```

Expected:

- `selectedPhotoIds` appears in shared photo selection modules and route composition only.
- `selectedFaceIds` appears only in Suggestions batch-review code.
- `activeMetadata` and `activeFaceAssignment` appear in shared inspector state and route composition only.
- `readErrorDetail` and `applyFaceAssignment` appear only in shared face-labeling modules.
- `AddToAlbumDialog` is removed if `AlbumActionSurface` fully replaces it.

- [ ] **Step 3: Delete obsolete tests with their obsolete components**

For each deleted component, delete or migrate its test:

```bash
git rm apps/ui/src/pages/PhotoFaceAssignmentModal.tsx apps/ui/src/pages/PhotoFaceAssignmentModal.test.tsx
git rm apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx
git rm apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx
```

Only run `git rm` for files that still exist and have no imports.

- [ ] **Step 4: Remove obsolete CSS selectors**

Edit `apps/ui/src/styles/app-shell.css` and remove selectors that no longer match rendered markup:

```bash
rg -n "browse-card|browse-thumbnail|suggestions-thumbnail|suggestions-face-overlay|library-face-panel|face-assignment-modal" apps/ui/src/styles/app-shell.css
```

For every match, confirm whether shared `photo-surface`, `photo-face-region-button`, `detail-flyout`, or shared modal selectors replaced it. Delete stale selectors.

- [ ] **Step 5: Run focused test suites**

Run:

```bash
npm --prefix apps/ui test -- photoInteractionAdapters.test.ts photoSelectionState.test.ts photoInspectorState.test.ts FaceOverlayLayer.test.tsx PhotoSurface.test.tsx PhotoMetadataFlyout.test.tsx FaceAssignmentModal.test.tsx AlbumActionSurface.test.tsx LibraryRoutePage.test.tsx SuggestionsRoutePage.test.tsx AlbumsRoutePage.test.tsx PhotoDetailRoutePage.test.tsx
```

Expected: all listed suites pass.

- [ ] **Step 6: Run full UI test suite**

Run:

```bash
npm --prefix apps/ui test
```

Expected: all tests pass.

- [ ] **Step 7: Run UI build**

Run:

```bash
npm --prefix apps/ui run build
```

Expected: build passes with no TypeScript errors.

- [ ] **Step 8: Commit final cleanup**

Run:

```bash
git add apps/ui/src docs/superpowers/plans/2026-05-09-photo-interaction-unification.md
git commit -m "chore: remove obsolete photo interaction code"
```

---

## Self-Review Notes

- Spec coverage:
  - Shared photo/face/metadata/album contracts: Tasks 1, 2, 6.
  - Shared photo surface and face boxes: Task 3.
  - Shared metadata flyout: Task 4.
  - Shared face assignment modal: Task 5.
  - Library, Suggestions, Albums, Photo Detail migrations: Tasks 7 through 10.
  - Explicit cleanup/dead-code removal: cleanup gates in Tasks 2 through 10 and final audit in Task 11.
  - Performance rules: route migrations use thumbnails in grids and preserve Photo Detail original loading.
- Placeholder scan:
  - No open-ended implementation placeholders remain; `photo-surface-placeholder` matches are CSS class names, not unfinished plan content.
- Type consistency:
  - Shared contracts use camelCase UI types and adapters isolate existing snake_case API payloads.
