import { fireEvent, render, screen } from "@testing-library/react";

import { ConfidenceRangeSlider, ConfidenceSingleSlider } from "./ConfidenceSlider";

describe("ConfidenceSlider", () => {
  it("renders single value and emits updates", () => {
    const onValueChange = vi.fn();

    render(
      <ConfidenceSingleSlider value={91} onValueChange={onValueChange} disabled={false} />
    );

    expect(screen.getByText("Suggestion threshold: 91%")).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText("Suggestion threshold"), { key: "ArrowRight" });

    expect(onValueChange).toHaveBeenCalledWith(92);
  });

  it("renders range values and emits both values", () => {
    const onValueChange = vi.fn();

    render(
      <ConfidenceRangeSlider minValue={30} maxValue={80} onValueChange={onValueChange} disabled={false} />
    );

    expect(screen.getByText("Minimum certainty: 30%")).toBeInTheDocument();
    expect(screen.getByText("Maximum certainty: 80%")).toBeInTheDocument();

    const minThumb = screen.getByLabelText("Minimum suggestion certainty");
    fireEvent.keyDown(minThumb, { key: "ArrowRight" });

    expect(onValueChange).toHaveBeenCalledWith(31, 80);
  });

  it("supports disabled state", () => {
    const { container } = render(
      <ConfidenceRangeSlider minValue={30} maxValue={80} onValueChange={vi.fn()} disabled />
    );

    expect(container.querySelector(".confidence-slider[data-disabled]")).toBeInTheDocument();
  });
});
