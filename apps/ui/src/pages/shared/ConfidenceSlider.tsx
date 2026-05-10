import { useEffect, useState } from "react";
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
  minBound?: number;
  maxBound?: number;
  minLabel?: string;
  maxLabel?: string;
  minValueFormatter?: (value: number) => string;
  maxValueFormatter?: (value: number) => string;
  minThumbAriaLabel?: string;
  maxThumbAriaLabel?: string;
}

function clampToBounds(value: number, minBound: number, maxBound: number): number {
  if (!Number.isFinite(value)) {
    return minBound;
  }
  return Math.max(minBound, Math.min(maxBound, Math.round(value)));
}

function clampPercent(value: number): number {
  return clampToBounds(value, 0, 100);
}

function normalizeRange(
  minValue: number,
  maxValue: number,
  minBound: number,
  maxBound: number
): [number, number] {
  const normalizedMin = clampToBounds(minValue, minBound, maxBound);
  const normalizedMax = clampToBounds(maxValue, minBound, maxBound);
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
  const [draftValue, setDraftValue] = useState(normalizedValue);

  useEffect(() => {
    setDraftValue(normalizedValue);
  }, [normalizedValue]);

  return (
    <div className="confidence-slider-wrapper">
      <p>{`Suggestion threshold: ${draftValue}%`}</p>
      <Range
        min={0}
        max={100}
        step={1}
        values={[draftValue]}
        disabled={disabled}
        onChange={(next) => {
          const [first = draftValue] = next;
          setDraftValue(clampPercent(first));
        }}
        onFinalChange={(next) => {
          const [first = draftValue] = next;
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
                  values: [draftValue],
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
  minBound = 0,
  maxBound = 100,
  minLabel = "Minimum certainty",
  maxLabel = "Maximum certainty",
  minValueFormatter = (value) => `${value}%`,
  maxValueFormatter = (value) => `${value}%`,
  minThumbAriaLabel = "Minimum suggestion certainty",
  maxThumbAriaLabel = "Maximum suggestion certainty",
}: ConfidenceRangeSliderProps) {
  const [normalizedMin, normalizedMax] = normalizeRange(minValue, maxValue, minBound, maxBound);
  const [draftRange, setDraftRange] = useState<[number, number]>([normalizedMin, normalizedMax]);
  const [draftMin, draftMax] = draftRange;

  useEffect(() => {
    setDraftRange([normalizedMin, normalizedMax]);
  }, [normalizedMin, normalizedMax]);

  return (
    <div className="confidence-slider-wrapper">
      <p>{`${minLabel}: ${minValueFormatter(draftMin)}`}</p>
      <p>{`${maxLabel}: ${maxValueFormatter(draftMax)}`}</p>
      <Range
        min={minBound}
        max={maxBound}
        step={1}
        values={draftRange}
        disabled={disabled}
        onChange={(next) => {
          const [nextMin = draftMin, nextMax = draftMax] = next;
          const [safeMin, safeMax] = normalizeRange(nextMin, nextMax, minBound, maxBound);
          setDraftRange([safeMin, safeMax]);
        }}
        onFinalChange={(next) => {
          const [nextMin = draftMin, nextMax = draftMax] = next;
          const [safeMin, safeMax] = normalizeRange(nextMin, nextMax, minBound, maxBound);
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
                  values: draftRange,
                  colors: ["#dbeafe", "#3b82f6", "#dbeafe"],
                  min: minBound,
                  max: maxBound,
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
              aria-label={index === 0 ? minThumbAriaLabel : maxThumbAriaLabel}
            />
          );
        }}
      />
    </div>
  );
}
