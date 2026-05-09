export async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Fall through to mapped fallback messages.
  }

  return null;
}

export function mapFaceAssignmentError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to assign faces.";
  }
  if (status === 404) {
    return detail ?? "Face or person no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face is already assigned.";
  }
  return `Assignment request failed (${status}).`;
}

export function mapFaceCorrectionError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to correct face assignments.";
  }
  if (status === 404) {
    return detail ?? "Face or person no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face correction could not be applied.";
  }
  return `Correction request failed (${status}).`;
}

export function mapFaceDismissalError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to discard faces.";
  }
  if (status === 404) {
    return detail ?? "Face no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face dismissal could not be applied.";
  }
  return `Dismissal request failed (${status}).`;
}

export function mapUnknownIdentityError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to assign faces.";
  }
  if (status === 404) {
    return detail ?? "Face no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face assignment could not be applied.";
  }
  return `Unknown-identity request failed (${status}).`;
}

export function mapFaceConfirmationError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to confirm face assignments.";
  }
  if (status === 404) {
    return detail ?? "Face or person no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face confirmation could not be applied.";
  }
  return `Confirmation request failed (${status}).`;
}
