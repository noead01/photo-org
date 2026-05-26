import { readErrorDetail } from "../face-labeling/faceLabelingErrors";

export type AdminUserRecord = {
  user_id: string;
  auth_provider: string;
  auth_subject: string;
  email: string;
  display_name: string | null;
  roles: string[];
  created_ts: string;
  updated_ts: string;
};

async function errorMessage(response: Response, fallback: string): Promise<string> {
  const detail = await readErrorDetail(response);
  return detail ?? fallback;
}

export async function fetchAdminUsers(signal?: AbortSignal): Promise<AdminUserRecord[]> {
  const response = await fetch("/api/v1/admin/users", { signal });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `Admin users request failed (${response.status})`));
  }
  return (await response.json()) as AdminUserRecord[];
}

export async function replaceAdminUserRoles(
  userId: string,
  roles: string[]
): Promise<AdminUserRecord> {
  const response = await fetch(`/api/v1/admin/users/${userId}/roles`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ roles })
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `Role update failed (${response.status})`));
  }
  return (await response.json()) as AdminUserRecord;
}
