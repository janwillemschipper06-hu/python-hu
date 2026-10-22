// API client for the Customer Onboarding Portal. It targets the shared APIM
// gateway via VITE_API_BASE_URL and attaches the MSAL-acquired bearer token to
// every protected call. The access token is passed in by the caller (never read
// from web storage — security-design.md §5.5) and forwarded as `Authorization:
// Bearer <token>`, which Azure Container Apps built-in auth validates before the
// request reaches the app (docs/adr/0010).

import type {
  CustomerLookup,
  InvitationResult,
  LifecycleResult,
  PortalUser,
  Role,
  WhoAmI,
} from "./types";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Race a promise against a timeout.
 *
 * The backend can scale to zero, so a cold-start request may hang far longer
 * than a normal one. Bounding each attempt lets the caller retry quickly
 * instead of leaving the UI stalled on a single fetch.
 */
function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error("Request timed out while the backend was waking up."));
    }, timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

/**
 * Decide whether a failed request is worth retrying automatically.
 *
 * Network failures, timeouts, and gateway-level errors (502/503/504) are the
 * shapes a scale-to-zero backend produces while cold-starting, so they are
 * treated as transient. Application errors (4xx) are not.
 */
export function isRetryableError(err: unknown): boolean {
  if (err instanceof ApiError) {
    return err.status === 502 || err.status === 503 || err.status === 504;
  }
  return err instanceof Error;
}

async function request<T>(
  path: string,
  accessToken: string,
  options: RequestInit = {},
  timeoutMs = 15000,
): Promise<T> {
  const res = await withTimeout(
    fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        ...options.headers,
      },
    }),
    timeoutMs,
  );

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

/**
 * Read-only customer picker over the external customer table
 * (`GET /api/v1/portal/customers/lookup`, Admin/PM). `q` is a name fragment.
 */
export function lookupCustomers(
  accessToken: string,
  q?: string,
  limit = 25,
): Promise<CustomerLookup[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (q) params.set("q", q);
  return request<CustomerLookup[]>(
    `/api/v1/portal/customers/lookup?${params.toString()}`,
    accessToken,
  );
}

/**
 * Identity echo (`GET /api/v1/portal/whoami`).
 *
 * Returns the caller's claims as the **API** decoded them after platform auth —
 * a diagnostic to confirm the role survives the browser -> APIM -> Container
 * Apps path, not just what the SPA read from its own ID token.
 */
export function getWhoami(accessToken: string): Promise<WhoAmI> {
  return request<WhoAmI>("/api/v1/portal/whoami", accessToken);
}

/**
 * The caller's own Entra profile photo as an object URL, or null when they have
 * none (common for guest accounts) or it can't be loaded — the UI then shows
 * initials. Callers should revoke the URL when done.
 */
export async function getMyPhotoUrl(
  accessToken: string,
): Promise<string | null> {
  try {
    const res = await withTimeout(
      fetch(`${BASE_URL}/api/v1/portal/me/photo`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }),
      15000,
    );
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  } catch {
    return null;
  }
}

/** POST helper: JSON body (optional), bearer auth, shared error handling. */
function post<T>(
  path: string,
  accessToken: string,
  body?: unknown,
): Promise<T> {
  return request<T>(path, accessToken, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}

/** Invite and provision a portal user (`POST /api/v1/admin/invitations`). */
export function inviteUser(
  accessToken: string,
  body: { email: string; role: Role },
): Promise<InvitationResult> {
  return post<InvitationResult>("/api/v1/admin/invitations", accessToken, body);
}

/** List every portal user for the admin lifecycle view (`GET /api/v1/admin/users`). */
export function listUsers(accessToken: string): Promise<PortalUser[]> {
  return request<PortalUser[]>("/api/v1/admin/users", accessToken);
}

/** Re-issue a user's invitation email (`POST /api/v1/admin/users/{oid}/resend`). */
export function resendInvitation(
  accessToken: string,
  oid: string,
): Promise<LifecycleResult> {
  return post<LifecycleResult>(
    `/api/v1/admin/users/${oid}/resend`,
    accessToken,
  );
}

/** Promote or demote a user (`POST /api/v1/admin/users/{oid}/role`). */
export function setUserRole(
  accessToken: string,
  oid: string,
  role: Role,
): Promise<LifecycleResult> {
  return post<LifecycleResult>(`/api/v1/admin/users/${oid}/role`, accessToken, {
    role,
  });
}

/** Deactivate (soft) or reactivate a user (`POST /api/v1/admin/users/{oid}/deactivate`). */
export function setUserDeactivated(
  accessToken: string,
  oid: string,
  deactivate: boolean,
): Promise<LifecycleResult> {
  return post<LifecycleResult>(
    `/api/v1/admin/users/${oid}/deactivate`,
    accessToken,
    { deactivate },
  );
}

/** Hard-delete a user / revoke a pending invite (`POST /api/v1/admin/users/{oid}/delete`). */
export function deleteUser(
  accessToken: string,
  oid: string,
): Promise<LifecycleResult> {
  return post<LifecycleResult>(
    `/api/v1/admin/users/${oid}/delete`,
    accessToken,
  );
}
