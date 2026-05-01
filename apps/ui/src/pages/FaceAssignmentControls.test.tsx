import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FaceAssignmentControls } from "./FaceAssignmentControls";

describe("FaceAssignmentControls", () => {
  const fetchMock = vi.fn();
  const onCorrected = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    onCorrected.mockReset();
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
        onCorrected={onCorrected}
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
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("You do not have permission to assign faces.")).toBeInTheDocument();
  });

  it("shows API detail for 409 conflicts", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: "Face already assigned" })
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: null }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("Face already assigned")).toBeInTheDocument();
  });

  it("shows fallback message for 404 without detail", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({})
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: null }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("Face or person no longer exists.")).toBeInTheDocument();
  });

  it("shows fallback status message for non-mapped server failures", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: "server blew up" })
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: null }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("Assignment request failed (500).")).toBeInTheDocument();
  });

  it("shows network fallback message on fetch exception", async () => {
    const user = userEvent.setup();

    fetchMock.mockRejectedValueOnce(new Error("network"));

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: null }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("Could not assign face.")).toBeInTheDocument();
  });

  it("disables select while assignment request is in flight", async () => {
    const user = userEvent.setup();
    let resolveRequest: ((value: Response) => void) | undefined;

    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve as (value: Response) => void;
        })
    );

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: null }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    const select = screen.getByLabelText("Assign face 1");
    await user.selectOptions(select, "person-1");
    expect(select).toBeDisabled();

    expect(resolveRequest).toBeDefined();
    resolveRequest!({
      ok: true,
      status: 201,
      json: async () => ({
        face_id: "face-1",
        photo_id: "photo-1",
        person_id: "person-1"
      })
    } as Response);

    await waitFor(() => {
      expect(screen.getByText("All visible faces assigned.")).toBeInTheDocument();
    });
  });

  it("renders completion when no unlabeled faces remain", () => {
    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: "person-1" }]}
        people={[{ person_id: "person-1", display_name: "Inez" }]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    expect(screen.getByText("All visible faces assigned.")).toBeInTheDocument();
  });

  it("corrects a labeled face and shows provenance feedback", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        face_id: "face-1",
        photo_id: "photo-1",
        previous_person_id: "person-1",
        person_id: "person-2"
      })
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: "person-1" }]}
        people={[
          { person_id: "person-1", display_name: "Inez" },
          { person_id: "person-2", display_name: "Mateo" }
        ]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Correct face 1"), "person-2");
    await user.click(screen.getByRole("button", { name: "Confirm reassignment" }));

    await waitFor(() => {
      expect(onCorrected).toHaveBeenCalledWith("face-1", "person-2");
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/corrections", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Face-Validation-Role": "contributor"
      },
      body: JSON.stringify({ person_id: "person-2" })
    });
    expect(await screen.findByText("Correction recorded: Inez -> Mateo.")).toBeInTheDocument();
  });

  it("shows deterministic correction permission error", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Face validation role required" })
    } as Response);

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: "person-1" }]}
        people={[
          { person_id: "person-1", display_name: "Inez" },
          { person_id: "person-2", display_name: "Mateo" }
        ]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Correct face 1"), "person-2");
    await user.click(screen.getByRole("button", { name: "Confirm reassignment" }));

    expect(await screen.findByText("You do not have permission to correct face assignments.")).toBeInTheDocument();
  });

  it("disables correction controls while correction request is in flight", async () => {
    const user = userEvent.setup();
    let resolveRequest: ((value: Response) => void) | undefined;

    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve as (value: Response) => void;
        })
    );

    render(
      <FaceAssignmentControls
        faces={[{ face_id: "face-1", person_id: "person-1" }]}
        people={[
          { person_id: "person-1", display_name: "Inez" },
          { person_id: "person-2", display_name: "Mateo" }
        ]}
        onAssigned={vi.fn()}
        onCorrected={onCorrected}
      />
    );

    await user.selectOptions(screen.getByLabelText("Correct face 1"), "person-2");
    await user.click(screen.getByRole("button", { name: "Confirm reassignment" }));
    expect(screen.getByLabelText("Correct face 1")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Confirm reassignment" })).toBeDisabled();

    expect(resolveRequest).toBeDefined();
    resolveRequest!({
      ok: true,
      status: 200,
      json: async () => ({
        face_id: "face-1",
        photo_id: "photo-1",
        previous_person_id: "person-1",
        person_id: "person-2"
      })
    } as Response);

    await waitFor(() => {
      expect(onCorrected).toHaveBeenCalledWith("face-1", "person-2");
    });
  });
});
