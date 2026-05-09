import * as Slider from "@radix-ui/react-slider";

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
      <Slider.Root
        className="confidence-slider"
        min={0}
        max={100}
        step={1}
        value={[normalizedValue]}
        disabled={disabled}
        onValueChange={(next) => {
          const [first = normalizedValue] = next;
          onValueChange(clampPercent(first));
        }}
      >
        <Slider.Track className="confidence-slider-track">
          <Slider.Range className="confidence-slider-range" />
        </Slider.Track>
        <Slider.Thumb className="confidence-slider-thumb" aria-label="Suggestion threshold" />
      </Slider.Root>
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

  return (
    <div className="confidence-slider-wrapper">
      <p>{`Minimum certainty: ${normalizedMin}%`}</p>
      <p>{`Maximum certainty: ${normalizedMax}%`}</p>
      <Slider.Root
        className="confidence-slider"
        min={0}
        max={100}
        step={1}
        value={[normalizedMin, normalizedMax]}
        disabled={disabled}
        onValueChange={(next) => {
          const [nextMin = normalizedMin, nextMax = normalizedMax] = next;
          const [safeMin, safeMax] = normalizeRange(nextMin, nextMax);
          onValueChange(safeMin, safeMax);
        }}
      >
        <Slider.Track className="confidence-slider-track">
          <Slider.Range className="confidence-slider-range" />
        </Slider.Track>
        <Slider.Thumb className="confidence-slider-thumb" aria-label="Minimum suggestion certainty" />
        <Slider.Thumb className="confidence-slider-thumb" aria-label="Maximum suggestion certainty" />
      </Slider.Root>
    </div>
  );
}
