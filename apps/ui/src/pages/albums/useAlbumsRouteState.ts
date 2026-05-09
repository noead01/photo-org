import { useEffect, useMemo, useState } from "react";
import {
  createAlbum,
  deleteAlbum,
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

export function useAlbumsRouteState() {
  const sessionUserId = resolveInitialSessionIdentity()?.userId ?? null;

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

  return {
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
    handleCreateAlbum,
    handleSaveRow,
    handleDeleteRow,
    handleSelectRow,
    handleHideRow,
    handleRemovePhoto,
    handleUpdateCreateName,
    handleUpdateCreateType,
    handleUpdateCreateSavedFilterJsonDraft,
    handleUpdateRowName,
    handleUpdateRowSavedFilterJsonDraft
  };
}
