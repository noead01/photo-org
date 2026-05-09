import { useState, type FormEvent } from "react";
import { resolveInitialSessionIdentity } from "../../session/sessionIdentity";
import type { NotificationEntry } from "../../app/feedback/feedbackTypes";
import {
  addPhotosToAlbum,
  createAlbum,
  exportPhotos,
  fetchLibraryPage,
} from "./libraryRouteApi";
import { buildSearchFilters } from "./libraryRouteSearchState";
import type { LibrarySelectionState } from "./librarySelection";
import type { LibraryLocationRadius, LibraryPhoto, PersonCertaintyMode, SortDirection } from "./libraryRouteTypes";

const ACTION_SCOPE_FETCH_LIMIT = 120;

interface UseLibraryBulkActionsArgs {
  selectionState: LibrarySelectionState;
  photos: LibraryPhoto[];
  committedQuery: string;
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  selectedAlbumIds: string[];
  personCertaintyMode: PersonCertaintyMode;
  suggestionConfidenceMinDraft: string;
  locationRadiusFilter: LibraryLocationRadius | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  sortDirection: SortDirection;
}

export function useLibraryBulkActions({
  selectionState,
  photos,
  committedQuery,
  fromDate,
  toDate,
  selectedPersonNames,
  selectedAlbumIds,
  personCertaintyMode,
  suggestionConfidenceMinDraft,
  locationRadiusFilter,
  hasFacesFilter,
  pathHintFilters,
  sortDirection,
}: UseLibraryBulkActionsArgs) {
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [isAddToAlbumDialogOpen, setIsAddToAlbumDialogOpen] = useState(false);
  const [addToAlbumKind, setAddToAlbumKind] = useState<"editable" | "saved_filter">("editable");
  const [addToAlbumName, setAddToAlbumName] = useState("");
  const [addToAlbumPhotoIds, setAddToAlbumPhotoIds] = useState<string[]>([]);
  const [showAlbumTypeInfo, setShowAlbumTypeInfo] = useState(false);
  const [addToAlbumError, setAddToAlbumError] = useState<string | null>(null);
  const [isSavingAlbum, setIsSavingAlbum] = useState(false);
  const sessionIdentity = resolveInitialSessionIdentity();

  function pushNotification(entry: NotificationEntry) {
    setNotifications((current) => [entry, ...current]);
  }

  function dismissNotification(id: string) {
    setNotifications((current) => current.filter((entry) => entry.id !== id));
  }

  function formatPhotoCountLabel(count: number): string {
    return `${count} photo${count === 1 ? "" : "s"}`;
  }

  function downloadBlob(blob: Blob, filename: string) {
    if (
      typeof URL.createObjectURL !== "function" ||
      typeof URL.revokeObjectURL !== "function"
    ) {
      throw new Error("Download is unavailable in this browser.");
    }

    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  }

  async function resolveActiveScopePhotoIds(): Promise<string[]> {
    if (selectionState.scope === "selected") {
      return Array.from(selectionState.selectedPhotoIds).sort((left, right) =>
        left.localeCompare(right, "en-US")
      );
    }

    if (selectionState.scope === "page") {
      return photos.map((photo) => photo.photo_id);
    }

    const collectedIds: string[] = [];
    const seen = new Set<string>();
    let offset = 0;
    let total = Number.POSITIVE_INFINITY;

    while (offset < total) {
      const payload = await fetchLibraryPage(
        committedQuery,
        fromDate,
        toDate,
        selectedPersonNames,
        selectedAlbumIds,
        personCertaintyMode,
        suggestionConfidenceMinDraft,
        locationRadiusFilter,
        hasFacesFilter,
        pathHintFilters,
        sortDirection,
        offset,
        ACTION_SCOPE_FETCH_LIMIT
      );

      total = payload.hits.total;
      const pageItems = payload.hits.items;
      if (pageItems.length === 0) {
        break;
      }

      for (const item of pageItems) {
        if (seen.has(item.photo_id)) {
          continue;
        }
        seen.add(item.photo_id);
        collectedIds.push(item.photo_id);
      }
      offset += pageItems.length;
    }

    return collectedIds;
  }

  async function openAddToAlbumDialog() {
    const photoIds = await resolveActiveScopePhotoIds();
    if (photoIds.length === 0) {
      pushNotification({
        id: `library-action-add-to-album-empty-${Date.now()}`,
        tone: "warning",
        message: "No photos available in the active selection scope.",
      });
      return;
    }

    setAddToAlbumPhotoIds(photoIds);
    setAddToAlbumName("");
    setAddToAlbumKind("editable");
    setShowAlbumTypeInfo(false);
    setAddToAlbumError(null);
    setIsAddToAlbumDialogOpen(true);
  }

  function closeAddToAlbumDialog() {
    if (isSavingAlbum) {
      return;
    }
    setIsAddToAlbumDialogOpen(false);
    setAddToAlbumError(null);
  }

  async function handleSaveToAlbum(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const albumName = addToAlbumName.trim();
    if (!albumName) {
      setAddToAlbumError("Album name is required.");
      return;
    }

    setIsSavingAlbum(true);
    setAddToAlbumError(null);
    try {
      const userId = sessionIdentity?.userId ?? null;
      if (addToAlbumKind === "saved_filter") {
        const savedFilter = buildSearchFilters(
          fromDate,
          toDate,
          selectedPersonNames,
          selectedAlbumIds,
          personCertaintyMode,
          suggestionConfidenceMinDraft,
          locationRadiusFilter,
          hasFacesFilter,
          pathHintFilters
        ) ?? {};
        const created = await createAlbum(
          {
            name: albumName,
            kind: "saved_filter",
            filter_json: savedFilter,
          },
          userId
        );
        pushNotification({
          id: `library-action-add-to-album-${Date.now()}`,
          tone: "success",
          message: `Saved-filter album "${created.name}" created from active filters.`,
        });
        setIsAddToAlbumDialogOpen(false);
        return;
      }

      const createdAlbum = await createAlbum({ name: albumName, kind: "editable" }, userId);
      const result = await addPhotosToAlbum(createdAlbum.album_id, addToAlbumPhotoIds, userId);
      const summary = `Added ${formatPhotoCountLabel(result.added_photo_ids.length)} to album "${createdAlbum.name}".`;
      const detailParts: string[] = [];
      if (result.duplicate_photo_ids.length > 0) {
        detailParts.push(`${result.duplicate_photo_ids.length} already in album`);
      }
      if (result.missing_photo_ids.length > 0) {
        detailParts.push(`${result.missing_photo_ids.length} missing`);
      }
      const message = detailParts.length > 0 ? `${summary} (${detailParts.join(", ")}).` : summary;

      pushNotification({
        id: `library-action-add-to-album-${Date.now()}`,
        tone: result.added_photo_ids.length > 0 ? "success" : "warning",
        message,
      });
      setIsAddToAlbumDialogOpen(false);
    } catch (error: unknown) {
      const message = error instanceof Error && error.message
        ? error.message
        : "Could not add the current selection to an album.";
      setAddToAlbumError(message);
    } finally {
      setIsSavingAlbum(false);
    }
  }

  async function handleExportAction() {
    const photoIds = await resolveActiveScopePhotoIds();
    if (photoIds.length === 0) {
      pushNotification({
        id: `library-action-export-empty-${Date.now()}`,
        tone: "warning",
        message: "No photos available in the active selection scope.",
      });
      return;
    }

    const exportResult = await exportPhotos(photoIds);
    downloadBlob(exportResult.blob, exportResult.filename);

    pushNotification({
      id: `library-action-export-${Date.now()}`,
      tone: "success",
      message: `Export completed: ${formatPhotoCountLabel(exportResult.exportedCount)}, ${exportResult.skippedCount} skipped.`,
    });
  }

  async function handleLibraryAction(action: "addToAlbum" | "export") {
    try {
      if (action === "addToAlbum") {
        await openAddToAlbumDialog();
        return;
      }
      await handleExportAction();
    } catch (error: unknown) {
      const fallback = action === "addToAlbum"
        ? "Could not add the current selection to an album."
        : "Could not export the current selection.";
      const message = error instanceof Error && error.message ? error.message : fallback;
      pushNotification({
        id: `library-action-${action}-error-${Date.now()}`,
        tone: "warning",
        message,
      });
    }
  }

  return {
    notifications,
    dismissNotification,
    handleLibraryAction,
    isAddToAlbumDialogOpen,
    addToAlbumKind,
    addToAlbumName,
    addToAlbumPhotoIds,
    showAlbumTypeInfo,
    addToAlbumError,
    isSavingAlbum,
    closeAddToAlbumDialog,
    handleSaveToAlbum,
    setAddToAlbumKind,
    setAddToAlbumName,
    setShowAlbumTypeInfo,
    setAddToAlbumError,
  };
}
