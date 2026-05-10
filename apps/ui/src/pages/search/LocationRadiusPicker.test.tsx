import { render } from "@testing-library/react";

import { LocationRadiusPicker } from "./LocationRadiusPicker";
import type { LocationRadiusValue } from "./types";

type LeafletEventHandler = (event: { latlng: { lat: number; lng: number }; target?: unknown }) => void;

type LayerOptions = {
  bubblingMouseEvents?: boolean;
};

type MockMap = {
  handlers: Map<string, LeafletEventHandler[]>;
  setView: (center: [number, number], zoom: number) => MockMap;
  on: (eventName: string, handler: LeafletEventHandler) => MockMap;
  fire: (eventName: string, event: { latlng: { lat: number; lng: number } }) => void;
  distance: (from: { lat: number; lng: number }, to: { lat: number; lng: number }) => number;
  getZoom: () => number;
  remove: () => void;
};

type MockMarker = {
  options: LayerOptions;
  addTo: (map: MockMap) => MockMarker;
  remove: () => void;
  on: (eventName: string, handler: LeafletEventHandler) => MockMarker;
  fire: (eventName: string, event?: { latlng: { lat: number; lng: number }; target?: unknown }) => void;
  getLatLng: () => { lat: number; lng: number };
};

type MockLeafletState = {
  lastMap: MockMap | null;
  lastMarker: MockMarker | null;
  reset: () => void;
};

vi.mock("leaflet", () => {
  let activeMap: MockMap | null = null;
  let lastMarker: MockMarker | null = null;

  function createMap(): MockMap {
    const handlers = new Map<string, LeafletEventHandler[]>();
    return {
      handlers,
      setView() {
        return this;
      },
      on(eventName, handler) {
        const eventHandlers = handlers.get(eventName) ?? [];
        eventHandlers.push(handler);
        handlers.set(eventName, eventHandlers);
        return this;
      },
      fire(eventName, event) {
        for (const handler of handlers.get(eventName) ?? []) {
          handler(event);
        }
      },
      distance(from, to) {
        const dx = from.lat - to.lat;
        const dy = from.lng - to.lng;
        return Math.sqrt(dx * dx + dy * dy) * 1000;
      },
      getZoom() {
        return 10;
      },
      remove() {
        handlers.clear();
      }
    };
  }

  function createLayer(options: LayerOptions = {}) {
    let mapForLayer: MockMap | null = null;
    const handlers = new Map<string, LeafletEventHandler[]>();
    return {
      options,
      addTo(map: MockMap) {
        mapForLayer = map;
        return this;
      },
      remove() {
        handlers.clear();
      },
      on(eventName: string, handler: LeafletEventHandler) {
        const eventHandlers = handlers.get(eventName) ?? [];
        eventHandlers.push(handler);
        handlers.set(eventName, eventHandlers);
        return this;
      },
      fire(eventName: string, event: { latlng: { lat: number; lng: number }; target?: unknown }) {
        for (const handler of handlers.get(eventName) ?? []) {
          handler(event);
        }
        if (eventName === "mousedown" && mapForLayer && options.bubblingMouseEvents !== false) {
          mapForLayer.fire("click", {
            latlng: event.latlng
          });
        }
      }
    };
  }

  const mockState: MockLeafletState = {
    get lastMap() {
      return activeMap;
    },
    get lastMarker() {
      return lastMarker;
    },
    reset() {
      activeMap = null;
      lastMarker = null;
    }
  };

  const leaflet = {
    map() {
      activeMap = createMap();
      return activeMap;
    },
    tileLayer() {
      return {
        on() {
          return this;
        },
        addTo() {
          return this;
        }
      };
    },
    circleMarker() {
      return createLayer();
    },
    circle() {
      return {
        ...createLayer(),
        setRadius() {
          return this;
        }
      };
    },
    marker(position: { lat: number; lng: number }, options: LayerOptions) {
      const layer = createLayer(options);
      const marker: MockMarker = {
        ...layer,
        getLatLng() {
          return position;
        },
        fire(eventName, event) {
          layer.fire(eventName, {
            latlng: event?.latlng ?? position,
            target: event?.target
          });
        }
      };
      lastMarker = marker;
      return marker;
    },
    divIcon() {
      return {};
    },
    latLng(lat: number, lng: number) {
      return { lat, lng };
    },
    __mock: mockState
  };

  return { default: leaflet };
});

describe("LocationRadiusPicker", () => {
  const locationValue: LocationRadiusValue = {
    latitude: 40.7128,
    longitude: -74.006,
    radiusKm: 5
  };

  beforeEach(async () => {
    const leaflet = await import("leaflet");
    const mockedLeaflet = leaflet.default as unknown as { __mock: MockLeafletState };
    mockedLeaflet.__mock.reset();
  });

  it("does not trigger map click updates when pressing the radius handle", async () => {
    const onChange = vi.fn();
    render(<LocationRadiusPicker value={locationValue} onChange={onChange} />);

    const leaflet = await import("leaflet");
    const mockedLeaflet = leaflet.default as unknown as { __mock: MockLeafletState };
    const marker = mockedLeaflet.__mock.lastMarker;

    expect(marker).not.toBeNull();
    marker?.fire("mousedown");

    expect(onChange).not.toHaveBeenCalled();
  });
});
