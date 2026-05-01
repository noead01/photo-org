import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FaceAssignmentControls } from "./FaceAssignmentControls";

describe("FaceAssignmentControls", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("assigns active unlabeled face and auto-advances", async () => {
    const user = userEvent.setup();
    const onAssigned = vi.fn();

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ face_id: "face-1", photo_id: "photo-1", person_id: "person-2" })
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[
          { face_id: "face-1", person_id: null },
          { face_id: "face-2", person_id: null },
          { face_id: "face-3", person_id: "person-1" }
        ]}
        people={[
          { person_id: "person-1", display_name: "Inez" },
          { person_id: "person-2", display_name: "Mateo" }
        ]}
        onAssigned={onAssigned}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-2");

    await waitFor(() => {
      expect(onAssigned).toHaveBeenCalledWith("face-1", "person-2");
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/assignments", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Face-Validation-Role": "contributor"
      },
      body: JSON.stringify({ person_id: "person-2" })
    });

    expect(screen.getByLabelText("Assign face 2")).toBeInTheDocument();
  });

  it("shows deterministic inline 403 error", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Face validation role required" })
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: null }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("You do not have permission to assign faces.")).toBeInTheDocument();
  });

  it("renders completion when no unlabeled faces remain", () => {
    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: "person-1" }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
      />
    );

    expect(screen.getByText("All visible faces assigned.")).toBeInTheDocument();
  });
});
