/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the API through the shared APIM gateway (e.g. https://api-himal-dev.9altitudes.com/cop). */
  readonly VITE_API_BASE_URL: string;
  /** Identity (workforce) Entra tenant ID the SPA authenticates against. */
  readonly VITE_ENTRA_TENANT_ID: string;
  /** Application (client) ID of the SPA app registration (public client). */
  readonly VITE_SPA_CLIENT_ID: string;
  /** Delegated API scope, e.g. api://<api-client-id>/access_as_user. */
  readonly VITE_API_SCOPE: string;
  /** "true" disables Microsoft sign-in for local development only. */
  readonly VITE_DISABLE_AUTH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
