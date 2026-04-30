# Issue #177 Location Radius Map Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a free map-based location-radius picker to Search that supports click-center + drag-radius, validates latitude/longitude/radius before submit, shows removable active filter state, and serializes deterministic `filters.location_radius` requests.

**Architecture:** Keep `SearchRoutePage.tsx` as an orchestrator and extract location logic into SRP modules. Use a Leaflet-backed `LocationRadiusPicker` component for map interactions and a pure `locationFilter` helper module for parsing/validation/payload/chip formatting. Extend existing Search route tests with location-specific behaviors while mocking the map component for deterministic unit tests.

**Tech Stack:** React 18, TypeScript, Vite/Vitest, Testing Library, Leaflet + OpenStreetMap tiles

---

### Task 1: Add failing location filter helper tests (TDD Red)

**Files:**
- Create: `apps/ui/src/pages/search/locationFilter.test.ts`
- Create: `apps/ui/src/pages/search/locationFilter.ts`

- [ ] **Step 1: Write failing tests for parsing, validation, payload, and chip formatting**

```ts
import {
  buildLocationRadiusFilter,
  formatLocationChipLabel,
  parseLocationDraft,
  validateLocationDraft
} from "./locationFilter";

it("parses valid drafts to numeric location state", () => {
  expect(parseLocationDraft("37.7749", "-122.4194", "12.5")).toEqual({
    latitude: 37.7749,
    longitude: -122.4194,
    radiusKm: 12.5
  });
});

it("returns validation error for out-of-range latitude", () => {
  const parsed = parseLocationDraft("91", "0", "10");
  expect(validateLocationDraft(parsed)).toBe("Latitude must be between -90 and 90.");
});

it("builds location_radius payload only when state is valid", () => {
  const valid = parseLocationDraft("37.7749", "-122.4194", "10");
  expect(buildLocationRadiusFilter(valid)).toEqual({
    latitude: 37.7749,
    longitude: -122.4194,
    radius_km: 10
  });
});

it("formats deterministic location chip label", () => {
  expect(formatLocationChipLabel({ latitude: 37.774912, longitude: -122.419488, radiusKm: 12.54 })).toBe(
    "location: 37.7749, -122.4195 (12.5 km)"
  );
});
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm --prefix apps/ui test -- src/pages/search/locationFilter.test.ts`
Expected: FAIL because helper module functions are not implemented.

### Task 2: Implement location helper module (TDD Green)

**Files:**
- Modify: `apps/ui/src/pages/search/locationFilter.ts`
- Test: `apps/ui/src/pages/search/locationFilter.test.ts`

- [ ] **Step 1: Implement minimal helper module to satisfy tests**

```ts
export type ParsedLocationDraft = {
  latitude: number | null;
  longitude: number | null;
  radiusKm: number | null;
};

export function parseLocationDraft(latitudeDraft: string, longitudeDraft: string, radiusDraft: string): ParsedLocationDraft {
  // parse trimmed numeric drafts; return null for empty/non-finite
}

export function validateLocationDraft(parsed: ParsedLocationDraft): string | null {
  // enforce finite + range checks for latitude/longitude/radius
}

export function buildLocationRadiusFilter(parsed: ParsedLocationDraft): { latitude: number; longitude: number; radius_km: number } | null {
  // return payload only when valid
}

export function formatLocationChipLabel(location: { latitude: number; longitude: number; radiusKm: number }): string {
  // round lat/lon to 4, radius to 1
}
```

- [ ] **Step 2: Re-run helper tests and verify pass**

Run: `npm --prefix apps/ui test -- src/pages/search/locationFilter.test.ts`
Expected: PASS.

- [ ] **Step 3: Commit helper module and tests**

```bash
git add apps/ui/src/pages/search/locationFilter.ts apps/ui/src/pages/search/locationFilter.test.ts
git commit -m "feat(ui): add location filter parsing and validation helpers"
```

### Task 3: Add failing SearchRoutePage tests for location filter semantics (TDD Red)

**Files:**
- Modify: `apps/ui/src/pages/SearchRoutePage.test.tsx`

- [ ] **Step 1: Add failing tests for location payload, validation, clear behavior, and no auto-search**

```ts
it("submits valid location filter as filters.location_radius", async () => {
  // set latitude, longitude, radius and submit
  expect(body.filters.location_radius).toEqual({
    latitude: 37.7749,
    longitude: -122.4194,
    radius_km: 12.5
  });
});

it("blocks submit when location values are invalid", async () => {
  // set invalid latitude and submit
  expect(searchCalls(fetchMock)).toHaveLength(0);
  expect(await screen.findByRole("alert")).toHaveTextContent("Latitude must be between -90 and 90.");
});

it("removes location chip and re-fetches without location_radius", async () => {
  // submit with location, remove chip, verify payload no longer contains location_radius
});

it("does not auto-search when location fields change", async () => {
  // type location values only
  expect(searchCalls(fetchMock)).toHaveLength(0);
});
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm --prefix apps/ui test -- src/pages/SearchRoutePage.test.tsx`
Expected: FAIL because location controls/behavior are not implemented.

### Task 4: Implement SRP location picker component and route integration (TDD Green)

**Files:**
- Create: `apps/ui/src/pages/search/LocationRadiusPicker.tsx`
- Create: `apps/ui/src/pages/search/types.ts`
- Modify: `apps/ui/src/pages/SearchRoutePage.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
- Modify: `apps/ui/package.json`

- [ ] **Step 1: Add map dependencies**

Run: `npm --prefix apps/ui install leaflet`
Run: `npm --prefix apps/ui install -D @types/leaflet`

- [ ] **Step 2: Implement `LocationRadiusPicker` with click-center and draggable-radius behavior**

```tsx
export function LocationRadiusPicker({
  value,
  onChange,
  onMapError
}: LocationRadiusPickerProps) {
  // create map + OSM tile layer
  // click map sets center and default radius when empty
  // draw circle + edge handle marker
  // drag handle recomputes radiusKm and calls onChange
}
```

- [ ] **Step 3: Integrate location drafts + helper module into `SearchRoutePage`**

```tsx
const [latitudeDraft, setLatitudeDraft] = useState("");
const [longitudeDraft, setLongitudeDraft] = useState("");
const [radiusDraft, setRadiusDraft] = useState("");

const parsedLocation = useMemo(
  () => parseLocationDraft(latitudeDraft, longitudeDraft, radiusDraft),
  [latitudeDraft, longitudeDraft, radiusDraft]
);
const locationError = useMemo(() => validateLocationDraft(parsedLocation), [parsedLocation]);
```

Include `location_radius` through `buildLocationRadiusFilter(parsedLocation)` and show removable location chip.

- [ ] **Step 4: Add responsive styling for location panel and map container**

```css
.search-location-panel { display: grid; gap: 0.45rem; }
.search-location-map { height: 16rem; border: 1px solid #cbd5e1; border-radius: 0.55rem; }
```

- [ ] **Step 5: Re-run SearchRoutePage test file and verify pass**

Run: `npm --prefix apps/ui test -- src/pages/SearchRoutePage.test.tsx`
Expected: PASS.

### Task 5: Run broader verification and finalize

**Files:**
- Modify (if needed): `apps/ui/src/pages/SearchRoutePage.test.tsx`
- Modify (if needed): `apps/ui/src/pages/search/LocationRadiusPicker.tsx`

- [ ] **Step 1: Run targeted UI test suite for touched units**

Run: `npm --prefix apps/ui test -- src/pages/search/locationFilter.test.ts src/pages/SearchRoutePage.test.tsx`
Expected: PASS.

- [ ] **Step 2: Run full UI unit suite**

Run: `npm --prefix apps/ui test`
Expected: PASS.

- [ ] **Step 3: Commit feature changes**

```bash
git add apps/ui/package.json apps/ui/package-lock.json apps/ui/src/pages/SearchRoutePage.tsx apps/ui/src/pages/SearchRoutePage.test.tsx apps/ui/src/pages/search/locationFilter.ts apps/ui/src/pages/search/locationFilter.test.ts apps/ui/src/pages/search/types.ts apps/ui/src/pages/search/LocationRadiusPicker.tsx apps/ui/src/styles/app-shell.css
git commit -m "feat(ui): add map-based location radius filter for search"
```
