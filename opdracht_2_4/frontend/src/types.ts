// Shapes returned by the Customer Onboarding Portal API. Field names are the
// snake_case JSON the FastAPI services emit (see api/app/modules/customers/schemas.py).

// A customer option from the read-only lookup over ext.Customer
// (GET /api/v1/portal/customers/lookup).
export interface CustomerLookup {
  id: number;
  name: string;
}

// Diagnostic identity echo from GET /api/v1/portal/whoami — the caller's claims
// as the API decoded them after platform auth (see api/app/modules/session/schemas.py).
export interface WhoAmI {
  oid: string | null;
  tid: string | null;
  app_id: string | null;
  audience: string | string[] | null;
  roles: string[];
  is_admin: boolean;
}

// The portal role an invitation grants (api/app/modules/users/schemas.py).
export type Role = "admin" | "pm" | "user";

// A portal user as the admin lifecycle view sees it
// (GET /api/v1/admin/users — api/app/modules/users/schemas.py PortalUser).
export interface PortalUser {
  entra_oid: string;
  email: string;
  role: string | null;
  invited_utc: string | null;
  redeemed_utc: string | null;
  deactivated_utc: string | null;
  created_utc: string;
}

// Outcome of an invite (api/app/modules/users/schemas.py InvitationResult).
export interface InvitationResult {
  email: string;
  role: Role;
  entra_oid: string;
  invitation_status: string;
  redeem_url: string | null;
}

// Outcome of a lifecycle action (api/app/modules/users/schemas.py LifecycleResult).
export interface LifecycleResult {
  entra_oid: string;
  action: string;
  invitation_status: string | null;
  redeem_url: string | null;
}
