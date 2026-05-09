export {
  DEFAULT_PHOTO_SELECTION_STATE as DEFAULT_LIBRARY_SELECTION_STATE,
  createPhotoSelectionState as createLibrarySelectionState,
  formatPhotoSelectionScopeLabel as formatSelectionScopeLabel,
  parsePhotoSelectionRouteState as parseLibrarySelectionRouteState,
  photoSelectionReducer as librarySelectionReducer,
  resolvePhotoSelectionScopeCount as resolveSelectionScopeCount,
  serializePhotoSelectionState as serializeLibrarySelectionState
} from "../photo-interactions/photoSelectionState";

export type {
  PhotoSelectionAction as LibrarySelectionAction,
  PhotoSelectionRouteState as LibrarySelectionRouteState,
  PhotoSelectionScope as LibrarySelectionScope,
  PhotoSelectionState as LibrarySelectionState
} from "../photo-interactions/photoSelectionState";
