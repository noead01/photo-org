import { render, screen } from "@testing-library/react";
import { buildFaceOverlayRegions, FaceBBoxOverlay } from "./FaceBBoxOverlay";

describe("FaceBBoxOverlay", () => {
  it("builds overlay regions from explicit bbox coordinate-space dimensions", () => {
    const regions = buildFaceOverlayRegions(
      [
        {
          face_id: "face-1",
          person_id: "person-1",
          bbox_x: 1000,
          bbox_y: 300,
          bbox_w: 800,
          bbox_h: 600,
          bbox_space_width: 4000,
          bbox_space_height: 3000
        }
      ],
      100,
      75
    );

    expect(regions).toEqual([
      {
        faceId: "face-1",
        personId: "person-1",
        labelSource: null,
        leftPercent: 25,
        topPercent: 10,
        widthPercent: 20,
        heightPercent: 20
      }
    ]);
  });

  it("falls back to legacy inferred coordinate-space dimensions when explicit values are absent", () => {
    const regions = buildFaceOverlayRegions(
      [
        {
          face_id: "face-1",
          person_id: "person-1",
          bbox_x: 320,
          bbox_y: 160,
          bbox_w: 120,
          bbox_h: 140
        }
      ],
      100,
      100
    );

    expect(regions).toHaveLength(1);
    expect(regions[0]!.faceId).toBe("face-1");
    expect(regions[0]!.personId).toBe("person-1");
    expect(regions[0]!.leftPercent).toBeCloseTo(72.72727272727273, 8);
    expect(regions[0]!.topPercent).toBeCloseTo(53.333333333333336, 8);
    expect(regions[0]!.widthPercent).toBeCloseTo(27.272727272727266, 8);
    expect(regions[0]!.heightPercent).toBeCloseTo(46.666666666666664, 8);
  });

  it("renders region overlays and optional region content", () => {
    render(
      <FaceBBoxOverlay
        regions={[
          {
            faceId: "face-1",
            personId: "person-1",
            labelSource: "machine_suggested",
            leftPercent: 10,
            topPercent: 20,
            widthPercent: 30,
            heightPercent: 40
          }
        ]}
        ariaLabel="Detected face regions"
        renderRegionContent={(_region, index) => (
          <button type="button" aria-label={`Show provenance details for face region ${index + 1}`}>
            badge
          </button>
        )}
      />
    );

    expect(screen.getByRole("list", { name: "Detected face regions" })).toBeInTheDocument();
    expect(screen.getByLabelText("Face region 1 for person-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show provenance details for face region 1" })).toBeInTheDocument();
  });
});
