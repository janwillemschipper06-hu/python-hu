import {
  PublicClientApplication,
  type AccountInfo,
  type Configuration,
} from "@azure/msal-browser";

// TEMPORARY LOCAL DEV BYPASS — remove once local Entra sign-in is set up.
// Set VITE_DISABLE_AUTH=true in frontend/.env.local to skip the Microsoft
// sign-in flow entirely. The API itself has no in-app token check outside Azure
// Container Apps (the platform's built-in auth only runs there — docs/adr/0010),
// so a dummy token is harmless for local development.
const authDisabled = import.meta.env.VITE_DISABLE_AUTH === "true";

const DUMMY_ACCOUNT = {
  username: "local-dev (auth disabled)",
  idTokenClaims: { roles: ["Admin"] },
} as unknown as AccountInfo;

const clientId = import.meta.env.VITE_SPA_CLIENT_ID as string;
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID as string;

// The API is a **separate** app registration from the SPA (docs
// authentication-and-access.md §2.1), so the requested scope is the API's
// Application ID URI — e.g. api://<api-client-id>/access_as_user — not the SPA's.
// This value MUST equal the platform's allowedAudiences so Container Apps
// built-in auth accepts the bearer token (docs/adr/0010, Stage 4 plan).
const apiScope = import.meta.env.VITE_API_SCOPE as string;

// Fail loudly on a misconfigured build. A value that is empty or still an
// unsubstituted pipeline/token placeholder (e.g. "$(VITE_ENTRA_TENANT_ID)")
// would otherwise be baked into the authority and produce Entra's cryptic
// AADSTS900023 at sign-in. Detect it up front and surface a clear message via
// the app's error UI instead.
function isUnset(value: string | undefined): boolean {
  return (
    !value ||
    value.includes("$(") ||
    value.includes("#{") ||
    value.includes("${")
  );
}

const missing = authDisabled
  ? []
  : (
      [
        ["VITE_ENTRA_TENANT_ID", tenantId],
        ["VITE_SPA_CLIENT_ID", clientId],
        ["VITE_API_SCOPE", apiScope],
      ] as const
    )
      .filter(([, value]) => isUnset(value))
      .map(([name]) => name);

const configError =
  missing.length > 0
    ? `Sign-in is not configured: missing frontend build values ${missing.join(
        ", ",
      )}. These are baked in at build time from the ba-9a-cop-<env> variable ` +
      `group (populated by the infra stage from main.bicepparam); for local dev ` +
      `set them in frontend/.env.local (see .env.example).`
    : null;

// Silent flows (ssoSilent / acquireTokenSilent) run in a hidden iframe. They
// must redirect to a **minimal blank page**, not the SPA root: otherwise Azure
// Static Web Apps' navigationFallback reloads the whole app inside that iframe,
// which triggers the browser's "Unsafe attempt to initiate navigation …
// allow-top-navigation" error and makes MSAL stall on its iframe timeout (the
// long blank screen on load). `public/blank.html` carries the auth hash back
// with no app bundle executing. This URL must also be registered as a SPA
// redirect URI on the SPA app registration (see authentication-and-access.md).
const silentRedirectUri = `${window.location.origin}/blank.html`;

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    // Security design §7 / §5.5: the access token lives in **memory only** —
    // never localStorage or sessionStorage. MSAL keeps the whole token cache
    // (incl. the account) in memory, so a full page reload requires a silent
    // SSO re-acquisition (attempted on mount) or an interactive sign-in.
    cacheLocation: "memoryStorage",
  },
};

// Only constructed when auth is enabled and correctly configured — avoids
// building a client with a placeholder authority that would fail obscurely.
const msalInstance =
  authDisabled || configError ? null : new PublicClientApplication(msalConfig);

let initialized = false;

/** Initialize the MSAL instance. Must be awaited before any other MSAL call. */
export async function ensureMsalInitialized(): Promise<void> {
  if (authDisabled || initialized) {
    return;
  }
  if (configError) {
    throw new Error(configError);
  }
  await msalInstance!.initialize();
  initialized = true;
}

// The delegated scope the API exposes for the SPA (Stage 1 reference table:
// `access_as_user`). Requesting it yields an access token whose `aud` is the API
// app, which is exactly what the platform's built-in auth validates.
const loginRequest = {
  scopes: [apiScope],
};

/**
 * Return the signed-in account, or null if nobody is signed in.
 *
 * Falls back to the first cached account and marks it active on MSAL so
 * subsequent silent token acquisitions work.
 */
export function getActiveAccount(): AccountInfo | null {
  if (authDisabled) {
    return DUMMY_ACCOUNT;
  }
  const active = msalInstance!.getActiveAccount();
  if (active) {
    return active;
  }
  const fallback = msalInstance!.getAllAccounts()[0] ?? null;
  if (fallback) {
    msalInstance!.setActiveAccount(fallback);
  }
  return fallback;
}

/**
 * Sign in interactively via the Microsoft popup and mark the resulting account
 * as active. No-op when auth is disabled for local dev.
 */
export async function signIn(): Promise<AccountInfo> {
  if (authDisabled) {
    return DUMMY_ACCOUNT;
  }
  const result = await msalInstance!.loginPopup(loginRequest);
  msalInstance!.setActiveAccount(result.account);
  return result.account;
}

/** Sign out the active account. No-op when auth is disabled for local dev. */
export async function signOut(): Promise<void> {
  if (authDisabled) {
    return;
  }
  const account = getActiveAccount();
  if (account) {
    await msalInstance!.logoutPopup({ account });
  }
}

/**
 * Acquire an access token for the API, silently refreshing it if needed.
 *
 * Raises if no account is signed in — callers should only invoke this once
 * `getActiveAccount()` has returned a non-null account.
 */
export async function getAccessToken(): Promise<string> {
  if (authDisabled) {
    return "local-dev-token";
  }
  const account = getActiveAccount();
  if (!account) {
    throw new Error("Not signed in");
  }
  const result = await msalInstance!.acquireTokenSilent({
    ...loginRequest,
    account,
    redirectUri: silentRedirectUri,
  });
  return result.accessToken;
}

/**
 * Return the app-role values Entra stamped on the account's ID token.
 *
 * The authoritative role dimension is the token's `roles` claim, never a
 * database flag (authentication-and-access.md §2.2). Used only to pick which
 * view/API path the SPA presents; the API re-checks the role on every call.
 */
export function getAccountRoles(account: AccountInfo | null): string[] {
  const claims = account?.idTokenClaims as { roles?: string[] } | undefined;
  return claims?.roles ?? [];
}
