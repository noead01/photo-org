import { useEffect, useMemo, useState } from "react";
import {
  createAlbum,
  deleteAlbum,
  exportPhotos,
  fetchAlbumDetail,
  fetchAlbums,
  removePhotoFromAlbum,
  updateAlbum,
  type AlbumDetail,
  type AlbumRecord
} from "../library/libraryRouteApi";
import { resolveInitialSessionIdentity } from "../../session/sessionIdentity";
import { parseSavedFilterDraft, serializeSavedFilter } from "./albumLibraryQuery";

export interface AlbumRowDraft {
  name: string;
  savedFilterJsonDraft: string;
}

const DEFAULT_CREATE_SAVED_FILTER_JSON_DRAFT = '{"person_names":[]}';
export const DETAIL_PAGE_SIZE = 24;

interface FileSystemWritableFileStreamLike {
  write(data: Blob): Promise<void>;
  close(): Promise<void>;
}

interface FileSystemFileHandleLike {
  createWritable(): Promise<FileSystemWritableFileStreamLike>;
}

interface FileSystemDirectoryHandleLike {
  name?: string;
  getFileHandle(name: string, options: { create: boolean }): Promise<FileSystemFileHandleLike>;
}

type DirectoryPickerWindow = Window & {
  showDirectoryPicker?: () => Promise<FileSystemDirectoryHandleLike>;
};

export interface AlbumExportProgress {
  albumId: string;
  albumName: string;
  folderLabel: string;
  completedCount: number;
  totalCount: number;
}

function sanitizeExportFilename(filename: string, fallback: string): string {
  const cleaned = filename.trim().replace(/[\\/:*?"<>|]/g, "_");
  return cleaned.length > 0 ? cleaned : fallback;
}

function parseAttachmentFilename(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) {
    return fallback;
  }
  const match = contentDisposition.match(/filename=\"([^\"]+)\"/i);
  if (!match || !match[1]) {
    return fallback;
  }
  return sanitizeExportFilename(match[1], fallback);
}

async function fetchOriginalPhotoBlob(photoId: string): Promise<{ filename: string; blob: Blob }> {
  const response = await fetch(
    `/api/v1/photos/${encodeURIComponent(photoId)}/original?download=true`
  );
  if (!response.ok) {
    throw new Error(`Download request failed for ${photoId} (${response.status}).`);
  }

  const fallbackName = `${photoId}.bin`;
  return {
    filename: parseAttachmentFilename(response.headers.get("Content-Disposition"), fallbackName),
    blob: await response.blob(),
  };
}

function isDirectoryPickerAvailable(): boolean {
  return typeof (window as DirectoryPickerWindow).showDirectoryPicker === "function";
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

export function useAlbumsRouteState() {
  const sessionIdentity = resolveInitialSessionIdentity();
  const sessionUserId = sessionIdentity?.userId ?? null;
  const canExport = sessionIdentity?.capabilities.export ?? false;

  const [albums, setAlbums] = useState<AlbumRecord[]>([]);
  const [selectedAlbumId, setSelectedAlbumId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AlbumDetail | null>(null);
  const [detailPage, setDetailPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createName, setCreateName] = useState("");
  const [createType, setCreateType] = useState<"editable" | "saved_filter">("editable");
  const [createSavedFilterJsonDraft, setCreateSavedFilterJsonDraft] = useState(
    DEFAULT_CREATE_SAVED_FILTER_JSON_DRAFT
  );
  const [isCreating, setIsCreating] = useState(false);

  const [rowDrafts, setRowDrafts] = useState<Record<string, AlbumRowDraft>>({});
  const [savingAlbumId, setSavingAlbumId] = useState<string | null>(null);
  const [deletingAlbumId, setDeletingAlbumId] = useState<string | null>(null);
  const [exportingAlbumId, setExportingAlbumId] = useState<string | null>(null);
  const [exportProgress, setExportProgress] = useState<AlbumExportProgress | null>(null);

  async function resolveExportDirectoryHandle(): Promise<FileSystemDirectoryHandleLike> {
    const pickerWindow = window as DirectoryPickerWindow;
    if (typeof pickerWindow.showDirectoryPicker !== "function") {
      throw new Error("Folder export is unavailable in this browser.");
    }
    try {
      return await pickerWindow.showDirectoryPicker();
    } catch (caughtError) {
      const pickerError = caughtError as { name?: string } | undefined;
      if (pickerError?.name === "AbortError") {
        throw new Error("Folder selection was canceled.");
      }
      throw caughtError instanceof Error ? caughtError : new Error("Could not choose an export folder.");
    }
  }

  function syncRowDrafts(payload: AlbumRecord[]) {
    setRowDrafts((current) => {
      const next: Record<string, AlbumRowDraft> = {};
      for (const album of payload) {
        const currentDraft = current[album.album_id];
        next[album.album_id] = {
          name: currentDraft?.name ?? album.name,
          savedFilterJsonDraft:
            currentDraft?.savedFilterJsonDraft ?? serializeSavedFilter(album.saved_filter)
        };
      }
      return next;
    });
  }

  async function refreshAlbums(
    preferredAlbumId: string | null = selectedAlbumId,
    preferredDetailPage: number = detailPage
  ) {
    const payload = await fetchAlbums(sessionUserId);
    setAlbums(payload);
    syncRowDrafts(payload);

    if (payload.length === 0) {
      setSelectedAlbumId(null);
      setDetail(null);
      return;
    }

    if (!preferredAlbumId) {
      setSelectedAlbumId(null);
      setDetail(null);
      setDetailPage(1);
      return;
    }

    const resolvedAlbumId = payload.some((album) => album.album_id === preferredAlbumId)
      ? preferredAlbumId
      : null;
    setSelectedAlbumId(resolvedAlbumId);

    if (resolvedAlbumId) {
      const nextDetail = await fetchAlbumDetail(resolvedAlbumId, {
        page: preferredDetailPage,
        pageSize: DETAIL_PAGE_SIZE
      });
      setDetail(nextDetail);
      setDetailPage(nextDetail.page);
    } else {
      setDetail(null);
      setDetailPage(1);
    }
  }

  useEffect(() => {
    let isActive = true;

    void (async () => {
      try {
        setIsLoading(true);
        const payload = await fetchAlbums(sessionUserId);
        if (!isActive) {
          return;
        }

        setAlbums(payload);
        syncRowDrafts(payload);
        setSelectedAlbumId(null);
        setDetailPage(1);
        setDetail(null);
      } catch (caughtError) {
        if (!isActive) {
          return;
        }
        setError(caughtError instanceof Error ? caughtError.message : "Could not load albums.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      isActive = false;
    };
  }, [sessionUserId]);

  const sortedAlbums = useMemo(
    () => [...albums].sort((left, right) => left.name.localeCompare(right.name, "en-US")),
    [albums]
  );

  function handleUpdateCreateName(value: string) {
    setCreateName(value);
  }

  function handleUpdateCreateType(value: "editable" | "saved_filter") {
    setCreateType(value);
  }

  function handleUpdateCreateSavedFilterJsonDraft(value: string) {
    setCreateSavedFilterJsonDraft(value);
  }

  function handleUpdateRowName(albumId: string, nextName: string) {
    setRowDrafts((current) => {
      const currentDraft = current[albumId] ?? { name: "", savedFilterJsonDraft: "{}" };
      return {
        ...current,
        [albumId]: {
          ...currentDraft,
          name: nextName
        }
      };
    });
  }

  function handleUpdateRowSavedFilterJsonDraft(albumId: string, nextFilter: string) {
    setRowDrafts((current) => {
      const currentDraft = current[albumId] ?? { name: "", savedFilterJsonDraft: "{}" };
      return {
        ...current,
        [albumId]: {
          ...currentDraft,
          savedFilterJsonDraft: nextFilter
        }
      };
    });
  }

  async function handleCreateAlbum() {
    setError(null);

    const trimmedName = createName.trim();
    if (!trimmedName) {
      setError("Album name is required.");
      return;
    }

    try {
      setIsCreating(true);
      let filterJson: Record<string, unknown> | undefined;
      if (createType === "saved_filter") {
        filterJson = parseSavedFilterDraft(createSavedFilterJsonDraft);
      }

      await createAlbum(
        {
          name: trimmedName,
          kind: createType,
          ...(createType === "saved_filter" ? { filter_json: filterJson ?? {} } : {})
        },
        sessionUserId
      );

      setCreateName("");
      if (createType === "saved_filter") {
        setCreateSavedFilterJsonDraft(DEFAULT_CREATE_SAVED_FILTER_JSON_DRAFT);
      }
      await refreshAlbums(selectedAlbumId, detailPage);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not create album.");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleSaveRow(album: AlbumRecord) {
    const draft = rowDrafts[album.album_id];
    if (!draft) {
      return;
    }

    const trimmedName = draft.name.trim();
    if (!trimmedName) {
      setError("Album name is required.");
      return;
    }

    setError(null);
    try {
      setSavingAlbumId(album.album_id);

      if (album.kind === "saved_filter") {
        const filterJson = parseSavedFilterDraft(draft.savedFilterJsonDraft);
        await updateAlbum(album.album_id, { name: trimmedName, filter_json: filterJson }, sessionUserId);
      } else {
        await updateAlbum(album.album_id, { name: trimmedName }, sessionUserId);
      }

      await refreshAlbums(album.album_id, detailPage);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not update album.");
    } finally {
      setSavingAlbumId(null);
    }
  }

  async function handleDeleteRow(album: AlbumRecord) {
    setError(null);
    try {
      setDeletingAlbumId(album.album_id);
      await deleteAlbum(album.album_id);
      await refreshAlbums(album.album_id === selectedAlbumId ? null : selectedAlbumId, 1);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not delete album.");
    } finally {
      setDeletingAlbumId(null);
    }
  }

  async function handleSelectRow(albumId: string, page = 1) {
    setSelectedAlbumId(albumId);
    try {
      const payload = await fetchAlbumDetail(albumId, { page, pageSize: DETAIL_PAGE_SIZE });
      setDetail(payload);
      setDetailPage(payload.page);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not load album detail.");
    }
  }

  function handleHideRow() {
    setSelectedAlbumId(null);
    setDetail(null);
    setDetailPage(1);
  }

  async function handleRemovePhoto(photoId: string) {
    if (!detail) {
      return;
    }
    try {
      await removePhotoFromAlbum(detail.album_id, photoId);
      await refreshAlbums(detail.album_id, detailPage);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not remove photo.");
    }
  }

  async function resolveAlbumPhotoIds(albumId: string): Promise<string[]> {
    const photoIds: string[] = [];
    const seen = new Set<string>();
    let page = 1;
    let totalPages = 1;

    while (page <= totalPages) {
      const albumDetail = await fetchAlbumDetail(albumId, {
        page,
        pageSize: DETAIL_PAGE_SIZE
      });
      totalPages = Math.max(albumDetail.total_pages, 1);
      for (const item of albumDetail.items) {
        if (seen.has(item.photo_id)) {
          continue;
        }
        seen.add(item.photo_id);
        photoIds.push(item.photo_id);
      }
      page += 1;
    }

    return photoIds;
  }

  async function handleExportAlbum(album: AlbumRecord) {
    if (!canExport) {
      setError("You do not have permission for this action.");
      return;
    }

    setError(null);
    try {
      setExportingAlbumId(album.album_id);
      const photoIds = await resolveAlbumPhotoIds(album.album_id);
      if (photoIds.length === 0) {
        setError(`Album "${album.name}" has no photos to export.`);
        return;
      }

      if (isDirectoryPickerAvailable()) {
        const directory = await resolveExportDirectoryHandle();
        const folderLabel = directory.name?.trim() ? directory.name.trim() : "selected folder";
        setExportProgress({
          albumId: album.album_id,
          albumName: album.name,
          folderLabel,
          completedCount: 0,
          totalCount: photoIds.length,
        });

        let completedCount = 0;
        for (const photoId of photoIds) {
          const { filename, blob } = await fetchOriginalPhotoBlob(photoId);
          const fileHandle = await directory.getFileHandle(filename, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();
          completedCount += 1;
          setExportProgress((current) =>
            current && current.albumId === album.album_id
              ? {
                  ...current,
                  completedCount,
                }
              : current
          );
        }
        if (typeof window.alert === "function") {
          window.alert(
            `Export complete: ${photoIds.length} photos saved to "${folderLabel}". Open that folder in your file manager to access the photos.`
          );
        }
        return;
      }

      const exportResult = await exportPhotos(photoIds);
      downloadBlob(exportResult.blob, exportResult.filename);
      if (typeof window.alert === "function") {
        window.alert(
          `Folder picker is unavailable in this browser. Downloaded "${exportResult.filename}" as a ZIP file. Open your Downloads folder to access it.`
        );
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not export album.");
    } finally {
      setExportingAlbumId(null);
      setExportProgress(null);
    }
  }

  return {
    canExport,
    sortedAlbums,
    selectedAlbumId,
    detail,
    error,
    isLoading,
    createName,
    createType,
    createSavedFilterJsonDraft,
    isCreating,
    rowDrafts,
    savingAlbumId,
    deletingAlbumId,
    exportingAlbumId,
    exportProgress,
    handleCreateAlbum,
    handleSaveRow,
    handleDeleteRow,
    handleSelectRow,
    handleHideRow,
    handleRemovePhoto,
    handleExportAlbum,
    handleUpdateCreateName,
    handleUpdateCreateType,
    handleUpdateCreateSavedFilterJsonDraft,
    handleUpdateRowName,
    handleUpdateRowSavedFilterJsonDraft
  };
}
