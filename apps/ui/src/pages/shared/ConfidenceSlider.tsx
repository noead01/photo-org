import { Range, getTrackBackground } from "react-range";

interface ConfidenceSingleSliderProps {
  value: number;
  onValueChange: (nextValue: number) => void;
  disabled?: boolean;
}

interface ConfidenceRangeSliderProps {
  minValue: number;
  maxValue: number;
  onValueChange: (minValue: number, maxValue: number) => void;
  disabled?: boolean;
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function normalizeRange(minValue: number, maxValue: number): [number, number] {
  const normalizedMin = clampPercent(minValue);
  const normalizedMax = clampPercent(maxValue);
  if (normalizedMin <= normalizedMax) {
    return [normalizedMin, normalizedMax];
  }
  return [normalizedMax, normalizedMin];
}

export function ConfidenceSingleSlider({
  value,
  onValueChange,
  disabled = false,
}: ConfidenceSingleSliderProps) {
  const normalizedValue = clampPercent(value);

  return (
    <div className="confidence-slider-wrapper">
      <p>{`Suggestion threshold: ${normalizedValue}%`}</p>
      <Range
        min={0}
        max={100}
        step={1}
        values={[normalizedValue]}
        disabled={disabled}
        onChange={(next) => {
          const [first = normalizedValue] = next;
          onValueChange(clampPercent(first));
        }}
        renderTrack={({ props, children }) => (
          <div
            onMouseDown={props.onMouseDown}
            onTouchStart={props.onTouchStart}
            style={props.style}
            className="confidence-slider"
            data-disabled={disabled ? "" : undefined}
          >
            <div
              ref={props.ref}
              className="confidence-slider-track"
              style={{
                background: getTrackBackground({
                  values: [normalizedValue],
                  colors: ["#3b82f6", "#dbeafe"],
                  min: 0,
                  max: 100,
                }),
              }}
            >
              {children}
            </div>
          </div>
        )}
        renderThumb={({ props }) => {
          const { key, ...thumbProps } = props as typeof props & { key?: string };
          return (
            <div
              key={key}
              {...thumbProps}
              className="confidence-slider-thumb"
              aria-label="Suggestion threshold"
            />
          );
        }}
      />
    </div>
  );
}

export function ConfidenceRangeSlider({
  minValue,
  maxValue,
  onValueChange,
  disabled = false,
}: ConfidenceRangeSliderProps) {
  const [normalizedMin, normalizedMax] = normalizeRange(minValue, maxValue);
  const sliderValues = [normalizedMin, normalizedMax];

  return (
    <div className="confidence-slider-wrapper">
      <p>{`Minimum certainty: ${normalizedMin}%`}</p>
      <p>{`Maximum certainty: ${normalizedMax}%`}</p>
      <Range
        min={0}
        max={100}
        step={1}
        values={sliderValues}
        disabled={disabled}
        onChange={(next) => {
          const [nextMin = normalizedMin, nextMax = normalizedMax] = next;
          const [safeMin, safeMax] = normalizeRange(nextMin, nextMax);
          onValueChange(safeMin, safeMax);
        }}
        renderTrack={({ props, children }) => (
          <div
            onMouseDown={props.onMouseDown}
            onTouchStart={props.onTouchStart}
            style={props.style}
            className="confidence-slider"
            data-disabled={disabled ? "" : undefined}
          >
            <div
              ref={props.ref}
              className="confidence-slider-track"
              style={{
                background: getTrackBackground({
                  values: sliderValues,
                  colors: ["#dbeafe", "#3b82f6", "#dbeafe"],
                  min: 0,
                  max: 100,
                }),
              }}
            >
              {children}
            </div>
          </div>
        )}
        renderThumb={({ props, index }) => {
          const { key, ...thumbProps } = props as typeof props & { key?: string };
          return (
            <div
              key={key}
              {...thumbProps}
              className="confidence-slider-thumb"
              aria-label={index === 0 ? "Minimum suggestion certainty" : "Maximum suggestion certainty"}
            />
          );
        }}
      />
    </div>
  );
}
