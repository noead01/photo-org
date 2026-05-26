import { useEffect, useMemo, useState } from "react";
import type { SessionIdentity } from "../session/sessionIdentity";
import {
  fetchAdminUsers,
  replaceAdminUserRoles,
  type AdminUserRecord
} from "./operations/operationsApi";

const ROLE_OPTIONS = [
  { role: "viewer", label: "Viewer" },
  { role: "contributor", label: "Contributor" },
  { role: "admin", label: "Admin" }
] as const;

interface OperationsRoutePageProps {
  sessionIdentity: SessionIdentity | null;
}

export function OperationsRoutePage({ sessionIdentity }: OperationsRoutePageProps) {
  const canManageRoles = sessionIdentity?.capabilities.manageRoles ?? false;
  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [draftRolesByUserId, setDraftRolesByUserId] = useState<Record<string, string[]>>({});
  const [busyByUserId, setBusyByUserId] = useState<Record<string, boolean>>({});
  const [errorByUserId, setErrorByUserId] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(canManageRoles);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!canManageRoles) {
      setUsers([]);
      setDraftRolesByUserId({});
      setBusyByUserId({});
      setErrorByUserId({});
      setLoadError(null);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setLoadError(null);

    fetchAdminUsers(controller.signal)
      .then((payload) => {
        setUsers(payload);
        setDraftRolesByUserId(
          Object.fromEntries(payload.map((user) => [user.user_id, user.roles]))
        );
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setLoadError(
          caughtError instanceof Error ? caughtError.message : "Could not load users."
        );
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [canManageRoles, reloadToken]);

  const sortedUsers = useMemo(
    () => [...users].sort((left, right) => left.email.localeCompare(right.email, "en-US")),
    [users]
  );

  function toggleRole(userId: string, role: string) {
    setDraftRolesByUserId((current) => {
      const activeRoles = new Set(current[userId] ?? []);
      if (activeRoles.has(role)) {
        activeRoles.delete(role);
      } else {
        activeRoles.add(role);
      }
      return {
        ...current,
        [userId]: ROLE_OPTIONS.map((option) => option.role).filter((candidate) =>
          activeRoles.has(candidate)
        )
      };
    });
    setErrorByUserId((current) => ({ ...current, [userId]: "" }));
  }

  async function saveRoles(userId: string) {
    setBusyByUserId((current) => ({ ...current, [userId]: true }));
    setErrorByUserId((current) => ({ ...current, [userId]: "" }));
    try {
      const updated = await replaceAdminUserRoles(userId, draftRolesByUserId[userId] ?? []);
      setUsers((current) => current.map((user) => (user.user_id === userId ? updated : user)));
      setDraftRolesByUserId((current) => ({ ...current, [userId]: updated.roles }));
    } catch (caughtError) {
      setErrorByUserId((current) => ({
        ...current,
        [userId]: caughtError instanceof Error ? caughtError.message : "Could not update roles."
      }));
    } finally {
      setBusyByUserId((current) => ({ ...current, [userId]: false }));
    }
  }

  return (
    <section aria-labelledby="page-title" className="page operations-page">
      <div className="people-management-header">
        <h1 id="page-title">Operations</h1>
        <p>Manage application roles for authenticated users and inspect current admin access.</p>
      </div>

      {!canManageRoles ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Admin access required</h2>
          <p>You do not have permission to manage application roles.</p>
        </div>
      ) : null}

      {canManageRoles && loadError ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load users</h2>
          <p>{loadError}</p>
          <button type="button" onClick={() => setReloadToken((current) => current + 1)}>
            Retry
          </button>
        </div>
      ) : null}

      {canManageRoles && !loadError && isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading role administration.
        </div>
      ) : null}

      {canManageRoles && !loadError && !isLoading ? (
        <>
          <section aria-labelledby="operations-session-heading" className="feedback-panel">
            <h2 id="operations-session-heading">Current session</h2>
            <p>{sessionIdentity?.email ?? "Session unavailable"}</p>
            <p>Roles: {sessionIdentity?.roles.join(", ") || "none"}</p>
          </section>

          <section aria-labelledby="operations-users-heading">
            <h2 id="operations-users-heading">Users and roles</h2>
            {sortedUsers.length === 0 ? (
              <div className="feedback-panel">
                <p>No authenticated users have been provisioned yet.</p>
              </div>
            ) : (
              <ul className="people-management-list" aria-label="Role-managed users">
                {sortedUsers.map((user) => {
                  const draftRoles = draftRolesByUserId[user.user_id] ?? [];
                  const isBusy = busyByUserId[user.user_id] ?? false;
                  const rowError = errorByUserId[user.user_id] ?? "";
                  return (
                    <li key={user.user_id} className="people-management-card">
                      <div className="people-management-summary">
                        <div>
                          <h3>{user.display_name ?? user.email}</h3>
                          <p>{user.email}</p>
                          <p>Provider: {user.auth_provider}</p>
                        </div>
                      </div>
                      <div role="group" aria-label={`Roles for ${user.email}`}>
                        {ROLE_OPTIONS.map((option) => (
                          <label key={option.role}>
                            <input
                              type="checkbox"
                              checked={draftRoles.includes(option.role)}
                              disabled={isBusy}
                              onChange={() => toggleRole(user.user_id, option.role)}
                            />
                            {option.label}
                          </label>
                        ))}
                      </div>
                      {rowError ? <p role="alert">{rowError}</p> : null}
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => {
                          void saveRoles(user.user_id);
                        }}
                      >
                        {isBusy ? "Saving..." : `Save roles for ${user.email}`}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}
