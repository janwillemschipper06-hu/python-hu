import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  deleteUser,
  inviteUser,
  listUsers,
  resendInvitation,
  setUserDeactivated,
  setUserRole,
} from "../api";
import type { PortalUser, Role } from "../types";

interface UserManagementProps {
  // Resolves a fresh access token for each call (tokens live in memory only —
  // security-design.md §5.5). Supplied by the authenticated shell.
  getAccessToken: () => Promise<string>;
  // The signed-in admin's own oid, so self-destructive actions can be disabled.
  currentUserOid: string | null;
}

type UserStatus = "Pending" | "Active" | "Deactivated";

function statusOf(user: PortalUser): UserStatus {
  if (user.deactivated_utc) return "Deactivated";
  if (user.redeemed_utc) return "Active";
  return "Pending";
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  pm: "Project manager",
  user: "User",
};

function isAdmin(user: PortalUser): boolean {
  return (user.role ?? "").toLowerCase() === "admin";
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError)
    return `${fallback} (HTTP ${err.status}): ${err.message}`;
  if (err instanceof Error) return err.message;
  return fallback;
}

function StatusBadge({ status }: { status: UserStatus }) {
  const styles: Record<UserStatus, string> = {
    Active: "text-green-700 bg-green-50 border-green-200",
    Pending: "text-amber-700 bg-amber-50 border-amber-200",
    Deactivated: "text-brand-muted bg-brand-surface border-brand-border",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium border ${styles[status]}`}
    >
      {status}
    </span>
  );
}

export function UserManagement({
  getAccessToken,
  currentUserOid,
}: UserManagementProps) {
  const [users, setUsers] = useState<PortalUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyOid, setBusyOid] = useState<string | null>(null);

  // Invite form.
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("user");
  const [inviteBusy, setInviteBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessToken();
      setUsers(await listUsers(token));
    } catch (err) {
      setError(errorMessage(err, "Failed to load users"));
    } finally {
      setLoading(false);
    }
  }, [getAccessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Run a per-user action, then refresh so every derived view stays consistent.
  const runAction = useCallback(
    async (
      oid: string,
      action: (token: string) => Promise<unknown>,
      done: string,
    ) => {
      setBusyOid(oid);
      setError(null);
      setNotice(null);
      try {
        const token = await getAccessToken();
        await action(token);
        setNotice(done);
        await refresh();
      } catch (err) {
        setError(errorMessage(err, "Action failed"));
      } finally {
        setBusyOid(null);
      }
    },
    [getAccessToken, refresh],
  );

  async function handleInvite(event: React.FormEvent) {
    event.preventDefault();
    setInviteBusy(true);
    setError(null);
    setNotice(null);
    try {
      const token = await getAccessToken();
      const body = {
        email: inviteEmail.trim(),
        role: inviteRole,
      };
      const result = await inviteUser(token, body);
      setNotice(`Invited ${result.email} (${result.invitation_status}).`);
      setInviteEmail("");
      setInviteRole("user");
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "Invite failed"));
    } finally {
      setInviteBusy(false);
    }
  }

  const anyBusy = busyOid !== null || inviteBusy;

  return (
    <div className="space-y-6">
      {/* Invite form */}
      <section className="bg-white border border-brand-border rounded">
        <div className="px-4 py-3 border-b border-brand-border">
          <h2 className="text-sm font-semibold text-brand-dark">Invite user</h2>
          <p className="text-xs text-brand-muted">
            Sends an Entra B2B invitation and assigns the role in one action.
          </p>
        </div>
        <form onSubmit={handleInvite} className="px-4 py-4 space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <label className="flex-1 text-xs text-brand-muted">
              Email
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="person@customer.com"
                className="mt-1 w-full border border-brand-border rounded px-3 py-2 text-sm text-brand-dark"
              />
            </label>
            <label className="text-xs text-brand-muted">
              Role
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as Role)}
                className="mt-1 w-full sm:w-40 border border-brand-border rounded px-3 py-2 text-sm text-brand-dark bg-white"
              >
                <option value="user">User</option>
                <option value="pm">Project manager</option>
                <option value="admin">Admin</option>
              </select>
            </label>
          </div>

          <button
            type="submit"
            disabled={inviteBusy || inviteEmail.trim() === ""}
            className="bg-brand-primary hover:bg-brand-dark text-white text-sm font-medium px-4 py-2 rounded transition-colors disabled:opacity-50"
          >
            {inviteBusy ? "Inviting…" : "Send invitation"}
          </button>
        </form>
      </section>

      {/* Notices */}
      {notice && (
        <p className="text-sm text-green-700 bg-green-50 border border-green-200 px-4 py-2 rounded">
          {notice}
        </p>
      )}
      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 px-4 py-2 rounded">
          {error}
        </p>
      )}

      {/* User list */}
      <section className="bg-white border border-brand-border rounded">
        <div className="px-4 py-3 border-b border-brand-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-brand-dark">Users</h2>
          <button
            onClick={() => void refresh()}
            disabled={loading}
            className="border border-brand-border bg-white hover:bg-brand-surface text-brand-muted text-sm px-3 py-1.5 rounded transition-colors disabled:opacity-50"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {loading && users.length === 0 ? (
          <p className="text-sm text-brand-muted text-center py-12">
            Loading users…
          </p>
        ) : users.length === 0 ? (
          <p className="text-sm text-brand-muted text-center py-12">
            No users yet. Invite one above.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-brand-surface text-left text-xs font-semibold text-brand-primary uppercase tracking-wide border-b border-brand-border">
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border">
                {users.map((user) => {
                  const admin = isAdmin(user);
                  const status = statusOf(user);
                  const self = user.entra_oid === currentUserOid;
                  return (
                    <tr
                      key={user.entra_oid}
                      className="hover:bg-brand-surface transition-colors align-top"
                    >
                      <td className="px-4 py-3 text-brand-dark break-all">
                        {user.email}
                        {self && (
                          <span className="ml-2 text-xs text-brand-muted">
                            (you)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded border ${
                            admin
                              ? "text-brand-primary border-brand-primary bg-brand-surface"
                              : "text-brand-muted border-brand-border bg-brand-surface"
                          }`}
                        >
                          {ROLE_LABELS[user.role?.toLowerCase() ?? ""] ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={status} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5 justify-end">
                          <button
                            onClick={() =>
                              void runAction(
                                user.entra_oid,
                                (t) => resendInvitation(t, user.entra_oid),
                                "Invitation resent.",
                              )
                            }
                            disabled={anyBusy}
                            className="text-xs border border-brand-border bg-white hover:bg-brand-surface px-2 py-1 rounded disabled:opacity-50"
                          >
                            Resend
                          </button>
                          <select
                            value={user.role?.toLowerCase() ?? ""}
                            onChange={(e) => {
                              const role = e.target.value as Role;
                              void runAction(
                                user.entra_oid,
                                (t) => setUserRole(t, user.entra_oid, role),
                                `Role changed to ${ROLE_LABELS[role]}.`,
                              );
                            }}
                            disabled={anyBusy || self}
                            title={
                              self ? "You cannot change your own role." : ""
                            }
                            aria-label="Role"
                            className="text-xs border border-brand-border bg-white px-2 py-1 rounded disabled:opacity-50"
                          >
                            {!user.role && (
                              <option value="" disabled>
                                Select role
                              </option>
                            )}
                            <option value="user">User</option>
                            <option value="pm">Project manager</option>
                            <option value="admin">Admin</option>
                          </select>
                          {status === "Deactivated" ? (
                            <button
                              onClick={() =>
                                void runAction(
                                  user.entra_oid,
                                  (t) =>
                                    setUserDeactivated(
                                      t,
                                      user.entra_oid,
                                      false,
                                    ),
                                  "User reactivated.",
                                )
                              }
                              disabled={anyBusy}
                              className="text-xs border border-brand-border bg-white hover:bg-brand-surface px-2 py-1 rounded disabled:opacity-50"
                            >
                              Reactivate
                            </button>
                          ) : (
                            <button
                              onClick={() =>
                                void runAction(
                                  user.entra_oid,
                                  (t) =>
                                    setUserDeactivated(t, user.entra_oid, true),
                                  "User deactivated.",
                                )
                              }
                              disabled={anyBusy || self}
                              title={
                                self ? "You cannot deactivate yourself." : ""
                              }
                              className="text-xs border border-brand-border bg-white hover:bg-brand-surface px-2 py-1 rounded disabled:opacity-50"
                            >
                              Deactivate
                            </button>
                          )}
                          <button
                            onClick={() => {
                              const label =
                                status === "Pending"
                                  ? `Revoke the pending invitation for ${user.email}?`
                                  : `Permanently delete ${user.email}? This removes the Entra guest account.`;
                              if (!window.confirm(label)) return;
                              void runAction(
                                user.entra_oid,
                                (t) => deleteUser(t, user.entra_oid),
                                status === "Pending"
                                  ? "Invitation revoked."
                                  : "User deleted.",
                              );
                            }}
                            disabled={anyBusy || self}
                            title={self ? "You cannot delete yourself." : ""}
                            className="text-xs border border-red-200 text-red-600 bg-white hover:bg-red-50 px-2 py-1 rounded disabled:opacity-50"
                          >
                            {status === "Pending" ? "Revoke" : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
