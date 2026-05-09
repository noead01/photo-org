import {
  mapFaceAssignmentError,
  mapFaceConfirmationError,
  mapFaceCorrectionError,
  mapFaceDismissalError,
  mapUnknownIdentityError,
  readErrorDetail,
} from "./faceLabelingErrors";

describe("faceLabelingErrors", () => {
  it("reads a detail string from API payloads", async () => {
    const response = {
      json: async () => ({ detail: "Conflict from API" }),
    } as Response;

    await expect(readErrorDetail(response)).resolves.toBe("Conflict from API");
  });

  it("returns null when detail cannot be read", async () => {
    const response = {
      json: async () => {
        throw new Error("bad json");
      },
    } as unknown as Response;

    await expect(readErrorDetail(response)).resolves.toBeNull();
  });

  it("maps assignment errors for permission, not found detail, conflict detail, and fallback", () => {
    expect(mapFaceAssignmentError(403, "ignored")).toBe(
      "You do not have permission to assign faces."
    );
    expect(mapFaceAssignmentError(404, "Face gone")).toBe("Face gone");
    expect(mapFaceAssignmentError(409, "Already assigned")).toBe("Already assigned");
    expect(mapFaceAssignmentError(500, null)).toBe("Assignment request failed (500).");
  });

  it("maps correction errors for permission, not found detail, conflict detail, and fallback", () => {
    expect(mapFaceCorrectionError(403, "ignored")).toBe(
      "You do not have permission to correct face assignments."
    );
    expect(mapFaceCorrectionError(404, "Person missing")).toBe("Person missing");
    expect(mapFaceCorrectionError(409, "Correction conflict")).toBe("Correction conflict");
    expect(mapFaceCorrectionError(500, null)).toBe("Correction request failed (500).");
  });

  it("maps dismissal errors for permission, not found detail, conflict detail, and fallback", () => {
    expect(mapFaceDismissalError(403, "ignored")).toBe(
      "You do not have permission to discard faces."
    );
    expect(mapFaceDismissalError(404, "Face missing")).toBe("Face missing");
    expect(mapFaceDismissalError(409, "Dismissal conflict")).toBe("Dismissal conflict");
    expect(mapFaceDismissalError(500, null)).toBe("Dismissal request failed (500).");
  });

  it("maps unknown-identity errors for permission, not found detail, conflict detail, and fallback", () => {
    expect(mapUnknownIdentityError(403, "ignored")).toBe(
      "You do not have permission to assign faces."
    );
    expect(mapUnknownIdentityError(404, "Face missing")).toBe("Face missing");
    expect(mapUnknownIdentityError(409, "Unknown conflict")).toBe("Unknown conflict");
    expect(mapUnknownIdentityError(500, null)).toBe("Unknown-identity request failed (500).");
  });

  it("maps confirmation errors for permission, not found detail, conflict detail, and fallback", () => {
    expect(mapFaceConfirmationError(403, "ignored")).toBe(
      "You do not have permission to confirm face assignments."
    );
    expect(mapFaceConfirmationError(404, "Face missing")).toBe("Face missing");
    expect(mapFaceConfirmationError(409, "Confirmation conflict")).toBe("Confirmation conflict");
    expect(mapFaceConfirmationError(500, null)).toBe("Confirmation request failed (500).");
  });
});
