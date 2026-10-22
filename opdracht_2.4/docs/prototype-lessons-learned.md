# Prototype Lessons Learned — Template Wizard

Throwaway prototype: `prototype-template-wizard/` (do not merge to `main` — it lives on a throwaway branch as a primary source). This note captures the **verdict** and the **practical lessons** so the real implementation is easier.

## The question it answered

> Can a React frontend read our template format (`template.yml` shared structure + per-language `.md` content), render a usable step-by-step wizard, and write the customer's input back to a JSON file — honouring write-only `secret` fields?

**Verdict: yes, the format works end-to-end.** Structure (`template.yml`) merges cleanly with translated content (`.md`), fields render in the yml-defined order with labels from the `.md`, the EN/NL toggle swaps only content while structure stays identical, and `text` / `secret` / `checkbox` all render and submit.

## What was validated

- **Read/merge**: `template.yml` (field keys, types, order) + `{lang}.md` frontmatter (title, per-field labels) + `.md` body (instructions) combine into one object the UI renders directly.
- **Markdown instructions** render to HTML server-side (numbered ordered lists become the visible step numbers).
- **Write-only secrets**: on submit, the real secret value is written to the JSON file (the backend needs it), but the value echoed back to the browser is redacted (`· submitted ·`). This is the correct write-only shape.
- **Frozen version**: the submission records the exact `templateVersion` it was filled against (matches the versioning decision in `architecture-design.md`).

## Lessons for the real build

1. **A backend endpoint is required for the "write to JSON / storage" step.** The browser cannot write files. The prototype needed a tiny Node server for both reading templates and persisting input — the real app will likewise need a backend for persistence and for keeping secret values off the client after submit.

2. **Do not rely on CDN scripts (unpkg) or in-browser Babel.** The first prototype pass loaded React + Babel from `unpkg.com` and rendered a blank page on the corporate network (the banner showed, the React app did not). Fix: bundle locally with **esbuild** and serve the bundle from the server. For the real app, use a normal bundler/build step (Vite/esbuild/Next) and self-host all assets — assume the customer/admin network blocks public CDNs.

3. **esbuild's install is blocked by npm's script-approval on this machine.** After `npm install esbuild`, its postinstall (which fetches the platform binary) was skipped. Had to run `npm approve-scripts esbuild` (or `--allow-scripts-pending`) then `npm rebuild esbuild`. Remember this when standing up the real project's toolchain here.

4. **Checkbox inside a `<label>` double-toggles.** Nesting `<input type="checkbox">` inside its `<label>` made clicks cancel out (the input toggles once, then the label re-forwards the click). Fix: give the input an `id` and link the label with `htmlFor` **side-by-side**, not nested. Applies to any checkbox in the real UI.

5. **Images belong in the template folder and ride along with the version bundle.** Screenshots are referenced from the `.md` steps via relative Markdown image syntax (`![alt](images/...png)`), published in the same version bundle as the text so a step and its screenshot stay in sync. (Note: the prototype used one shared `images/` folder across languages; `architecture-design.md` §1.1.1 has since moved to per-language `images/{lang}/` folders, since a screenshot shows UI text in that language.)

6. **Risk level / version are internal, not customer-facing.** The first render showed "risk" and "version" pills to the customer; these were dropped. Version stays as an internal field (needed for freezing); risk level was removed entirely.

## How the prototype was structured (for reference)

- `sample-templates/entra-app-registration/` — a real example template (`template.yml`, `en.md`, `nl.md`).
- `server.js` — Node (no framework): `GET /api/template?lang=` parses yml+md → JSON; `POST /api/submit` writes `submission.PROTOTYPE-wipe-me.json`; bundles `public/app.jsx` with esbuild at startup and serves `/app.js`.
- `public/app.jsx` — the React wizard.
- Run: `cd prototype-template-wizard; npm install; npm start` → http://localhost:5173
