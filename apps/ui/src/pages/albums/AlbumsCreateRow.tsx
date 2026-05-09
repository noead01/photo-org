interface AlbumsCreateRowProps {
  createName: string;
  createType: "editable" | "saved_filter";
  createSavedFilterJsonDraft: string;
  isCreating: boolean;
  onCreateNameChange: (value: string) => void;
  onCreateTypeChange: (value: "editable" | "saved_filter") => void;
  onCreateSavedFilterJsonDraftChange: (value: string) => void;
  onCreateAlbum: () => void;
}

export function AlbumsCreateRow({
  createName,
  createType,
  createSavedFilterJsonDraft,
  isCreating,
  onCreateNameChange,
  onCreateTypeChange,
  onCreateSavedFilterJsonDraftChange,
  onCreateAlbum
}: AlbumsCreateRowProps) {
  return (
    <tr className="albums-grid-create-row">
      <td>
        <label className="visually-hidden" htmlFor="albums-create-name">
          Album name
        </label>
        <input
          id="albums-create-name"
          value={createName}
          onChange={(event) => onCreateNameChange(event.target.value)}
          placeholder="New album name"
        />
      </td>
      <td>
        <label className="visually-hidden" htmlFor="albums-create-type">
          Album type
        </label>
        <select
          id="albums-create-type"
          value={createType}
          onChange={(event) => onCreateTypeChange(event.target.value as "editable" | "saved_filter")}
        >
          <option value="editable">editable</option>
          <option value="saved_filter">saved_filter</option>
        </select>
      </td>
      <td>
        {createType === "saved_filter" ? (
          <>
            <label className="visually-hidden" htmlFor="albums-create-filter-json">
              Saved filter JSON
            </label>
            <textarea
              id="albums-create-filter-json"
              value={createSavedFilterJsonDraft}
              onChange={(event) => onCreateSavedFilterJsonDraftChange(event.target.value)}
            />
          </>
        ) : (
          <span className="albums-grid-count">Photo count appears after creation.</span>
        )}
      </td>
      <td>
        <button type="button" onClick={onCreateAlbum} disabled={isCreating}>
          {isCreating ? "Creating…" : "Create album"}
        </button>
      </td>
    </tr>
  );
}
