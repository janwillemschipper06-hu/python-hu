import { useEffect, useState } from "react";
import logo from "./pictures/idNw5WxKBU_1775051280371.png";
import { getWhoami, getMyPhotoUrl } from "./api";
import type { WhoAmI } from "./types";
import {
  ensureMsalInitialized,
  getAccessToken,
  getAccountRoles,
  getActiveAccount,
  signIn,
  signOut,
} from "./authConfig";
import { LoginForm } from "./components/LoginForm";
import { UserManagement } from "./components/UserManagement";
import { ProfileMenu } from "./components/ProfileMenu";

type AuthState =
  | { status: "initializing" }
  | { status: "unauthenticated"; error: string | null }
  | {
      status: "authenticated";
      accountName: string;
      displayName: string | null;
      isAdmin: boolean;
    };

export default function App(): JSX.Element | null {
  const [auth, setAuth] = useState<AuthState>({ status: "initializing" });
  const [loggingIn, setLoggingIn] = useState(false);

  const [whoami, setWhoami] = useState<WhoAmI | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  // On mount: initialize MSAL and reveal the login screen immediately. We use an
  // already-cached account if one exists (the local-dev bypass, or a sign-in
  // earlier in this tab) but deliberately do NOT probe the IdP with ssoSilent on
  // load — that hidden-iframe round trip is what made the page hang for many
  // seconds before the login button appeared. Clicking "Sign in" performs
  // single-sign-on automatically when an IdP session exists, so a returning user
  // is one quick click away with no password prompt.
  useEffect(() => {
    void (async () => {
      try {
        await ensureMsalInitialized();
      } catch (err) {
        // A misconfigured build (missing/placeholder VITE_* values) throws here.
        // Surface it on the login screen instead of leaving a blank page.
        setAuth({
          status: "unauthenticated",
          error: err instanceof Error ? err.message : "Sign-in unavailable.",
        });
        return;
      }

      const existing = getActiveAccount();
      if (existing) {
        setAuth({
          status: "authenticated",
          accountName: existing.username,
          displayName: existing.name ?? null,
          isAdmin: getAccountRoles(existing).includes("Admin"),
        });
      } else {
        setAuth({ status: "unauthenticated", error: null });
      }
    })();
  }, []);

  // Fetch the API's own view of the caller (`/api/v1/portal/whoami`) — the
  // authoritative roles after platform auth, shown in the profile menu — and the
  // caller's profile photo (null when they have none; initials are shown).
  useEffect(() => {
    if (auth.status !== "authenticated") {
      setWhoami(null);
      setPhotoUrl(null);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    void (async () => {
      try {
        const token = await getAccessToken();
        setWhoami(await getWhoami(token));
        objectUrl = await getMyPhotoUrl(token);
        if (cancelled && objectUrl) {
          URL.revokeObjectURL(objectUrl);
        } else {
          setPhotoUrl(objectUrl);
        }
      } catch {
        // Identity details are cosmetic; the UI falls back to the ID-token view.
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [auth.status]);

  async function handleLogin() {
    setLoggingIn(true);
    try {
      await ensureMsalInitialized();
      const account = await signIn();
      setAuth({
        status: "authenticated",
        accountName: account.username,
        displayName: account.name ?? null,
        isAdmin: getAccountRoles(account).includes("Admin"),
      });
    } catch (err) {
      setAuth({
        status: "unauthenticated",
        error: err instanceof Error ? err.message : "Sign-in failed.",
      });
    } finally {
      setLoggingIn(false);
    }
  }

  function handleSignOut() {
    setAuth({ status: "unauthenticated", error: null });
    void signOut();
  }

  if (auth.status === "initializing") {
    return null;
  }

  if (auth.status === "unauthenticated") {
    return (
      <LoginForm onLogin={handleLogin} loading={loggingIn} error={auth.error} />
    );
  }

  // The SPA's own ID token does not carry the Admin app role — it is defined on
  // the API app, so it only surfaces in the access token (what the API decodes
  // for /whoami). Trust the API's authoritative is_admin for admin UI
  // affordances; fall back to the ID-token roles until /whoami resolves.
  const isAdmin = whoami?.is_admin ?? auth.isAdmin;

  return (
    <div className="min-h-screen bg-brand-surface">
      {/* Header — white nav matching the 9altitudes style */}
      <header className="bg-white border-b border-brand-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <img src={logo} alt="nine altitudes" className="h-8" />
            <span className="text-brand-border select-none text-sm">|</span>
            <div>
              <span className="text-brand-dark text-sm font-semibold">
                Customer Onboarding
              </span>
              <span className="text-brand-muted text-xs ml-2">Portal</span>
            </div>
          </div>
          <ProfileMenu
            displayName={auth.displayName}
            email={auth.accountName}
            roles={whoami?.roles ?? (auth.isAdmin ? ["Admin"] : [])}
            photoUrl={photoUrl}
            onSignOut={handleSignOut}
          />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {isAdmin ? (
          <UserManagement
            getAccessToken={getAccessToken}
            currentUserOid={whoami?.oid ?? null}
          />
        ) : (
          <p className="text-sm text-brand-muted">Projects are coming soon.</p>
        )}
      </main>
    </div>
  );
}
