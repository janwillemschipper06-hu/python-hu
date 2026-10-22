import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA is served by Azure Static Web Apps; it calls the API through the
// shared APIM gateway using the build-time VITE_API_BASE_URL value, so no dev
// proxy is configured here.
export default defineConfig({
  plugins: [react()],
});
