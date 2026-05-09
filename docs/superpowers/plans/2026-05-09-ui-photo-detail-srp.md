# UI Photo Detail SRP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Photo Detail route data access, image fallback behavior, metadata rendering, and face assignment integration into focused units.

**Architecture:** Keep `PhotoDetailRoutePage` as a route-level coordinator. Extract photo/people loading hooks, original-image fallback hook, metadata flyout, preview panel, and pure formatting helpers.

**Tech Stack:** React 18, React Router 6, TypeScript, Vitest, Testing Library.

---

## Files

- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Create: `apps/ui/src/pages/photo-detail/photoDetailApi.ts`
- Create: `apps/ui/src/pages/photo-detail/photoDetailTypes.ts`
- Create: `apps/ui/src/pages/photo-detail/photoDetailFormatting.ts`
- Create: `apps/ui/src/pages/photo-detail/photoDetailFormatting.test.ts`
- Create: `apps/ui/src/pages/photo-detail/usePhotoDetail.ts`
- Create: `apps/ui/src/pages/photo-detail/useOriginalImageFallback.ts`
- Create: `apps/ui/src/pages/photo-detail/PhotoPreviewPanel.tsx`
- Create: `apps/ui/src/pages/photo-detail/PhotoMetadataFlyout.tsx`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`

## Current Problem

`PhotoDetailRoutePage.tsx` combines:

- Payload type definitions at `apps/ui/src/pages/PhotoDetailRoutePage.tsx:15`.
- Formatting helpers at `apps/ui/src/pages/PhotoDetailRoutePage.tsx:98`.
- API fetch at `apps/ui/src/pages/PhotoDetailRoutePage.tsx:162`.
- Photo detail loading effect at `apps/ui/src/pages/PhotoDetailRoutePage.tsx:331`.
- People directory loading effect at `apps/ui/src/pages/PhotoDetailRoutePage.tsx:376`.
- Object URL retry/fallback behavior at `apps/ui/src/pages/PhotoDetailRoutePage.tsx:535`.
- Full route and flyout JSX from `apps/ui/src/pages/PhotoDetailRoutePage.tsx:568`.

## Tasks

### Task 1: Extract Types and API

- [ ] Move `PhotoDetailPayload` and related face/person/thumbnail types into `photoDetailTypes.ts`.
- [ ] Move `PhotoDetailRequestError` and `fetchPhotoDetail` into `photoDetailApi.ts`.
- [ ] Add `fetchPeopleDirectory` to `photoDetailApi.ts` or reuse the shared people API if the People Management plan has landed.
- [ ] Update route imports.
- [ ] Run: `npm --prefix apps/ui test -- PhotoDetailRoutePage.test.tsx`.

### Task 2: Extract Formatting Helpers

- [ ] Move `formatTimestamp`, `formatFilesize`, `formatGps`, `formatOptionalText`, and `formatExifAttributeValue` into `photoDetailFormatting.ts`.
- [ ] Export `MISSING_VALUE`.
- [ ] Add tests for null/missing values, valid UTC timestamp, byte/kilobyte/megabyte sizes, GPS values, and long EXIF truncation.
- [ ] Run: `npm --prefix apps/ui test -- photoDetailFormatting.test.ts`.

### Task 3: Extract Data Loading Hook

- [ ] Create `usePhotoDetail.ts`.
- [ ] Move `detail`, `isLoading`, `error`, `isNotFound`, `reloadToken`, and photo detail loading effect into the hook.
- [ ] Return `retry()` instead of exposing `setReloadToken`.
- [ ] Preserve 404 behavior that sets `isNotFound` without a route error.
- [ ] Run: `npm --prefix apps/ui test -- PhotoDetailRoutePage.test.tsx`.

### Task 4: Extract Original Image Fallback Hook

- [ ] Create `useOriginalImageFallback.ts`.
- [ ] Move `isOriginalImageEnabled`, `originalImageRetrySrc`, `originalImageNaturalSize`, active photo ref, object URL cleanup, `isCurrentImageRequest`, and blob retry behavior into the hook.
- [ ] Return `previewImageSrc`, `shouldUseOriginalImage`, `activeOriginalImageSrc`, `originalImageNaturalSize`, `handleImageLoad`, and `handleImageError`.
- [ ] Keep all `URL.createObjectURL` and `URL.revokeObjectURL` usage inside this hook.

### Task 5: Extract Preview Panel

- [ ] Create `PhotoPreviewPanel.tsx`.
- [ ] Move preview controls, ingest status display, image rendering, face overlay rendering, scale control, and face-region state text into the component.
- [ ] Keep route-level state for `showFaceBoxes`, `imageScalePercent`, and `isDetailFlyoutOpen` if that keeps props simple.
- [ ] Use callbacks for `onOpenFaceAssignment` and `onToggleDetails`.

### Task 6: Extract Metadata Flyout

- [ ] Create `PhotoMetadataFlyout.tsx`.
- [ ] Move details flyout JSX, summary, metadata, EXIF disclosure, and classification panels into the component.
- [ ] Keep `isExifAttributesOpen` state inside the flyout because it only affects flyout rendering.
- [ ] Pass `detail`, `ingestStatus`, and `onClose`.

### Task 7: Final Route Cleanup

- [ ] Compose `usePhotoDetail`, people loading, `useOriginalImageFallback`, `PhotoPreviewPanel`, `PhotoMetadataFlyout`, and `PhotoFaceAssignmentModal` in `PhotoDetailRoutePage`.
- [ ] If shared face-labeling state helpers have landed, use them for assignment and dismissal updates.
- [ ] Run: `npm --prefix apps/ui test -- PhotoDetailRoutePage.test.tsx`.
- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.

## Acceptance Criteria

- `PhotoDetailRoutePage` no longer defines fetch helpers, formatting helpers, or object URL retry logic.
- Object URL lifecycle is isolated and still revokes old retry URLs.
- Existing photo detail tests pass and formatting helpers have direct unit coverage.

