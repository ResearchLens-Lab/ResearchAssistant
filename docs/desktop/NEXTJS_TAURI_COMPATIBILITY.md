# Next.js 15 and Tauri Compatibility Assessment

## Scope and evidence

This is static source inspection of the current frontend, not a built Tauri proof. The frontend manifest defines `next dev`, `next build`, and `next start`; `next.config.js` does not declare static export or standalone output. The application root wraps React providers; workbench routes render through a shared `AppShell`. The app has client-side API calls to FastAPI and uses browser token storage.

## Route and runtime findings

| Feature | Observed source | Static-export implication |
|---|---|---|
| Dynamic conversation | `frontend/src/app/(workbench)/chat/[conversationId]/page.jsx` | Arbitrary conversation IDs need runtime route fallback or generated pages; IDs are not known at build. |
| Dynamic paper detail | `frontend/src/app/(workbench)/papers/[id]/page.jsx` | Same constraint for arbitrary project IDs. |
| PDF viewer | `frontend/src/app/(pdf)/pdf-viewer/page.jsx` | Viewer receives a document ID, filename and page through URL parameters; app must resolve locally at runtime. |
| Search params | Compare and graph pages use `useSearchParams`; graph initializes conversation context from query parameters. | Test export rendering and direct navigation; client hooks can require Suspense boundaries depending on build mode. |
| Next server endpoints | No `app/api/**/route.*` or Server Action declarations were found in the inspected app route tree. | API work belongs to FastAPI, which is favorable for an independent frontend bundle. |
| Image and markdown UI | `next/image` is configured unoptimized; markdown/math rendering is client-side dependency. | Likely compatible as static assets, but test WebView2 workers, fonts, PDF.js and CSP. |
| Auth | `frontend/src/utils/tokenStorage.js`, `frontend/src/services/api.client.js` | Current localStorage bearer/refresh tokens need desktop threat review; static export does not solve credential storage. |

## Tauri conclusion

**A no-server static Tauri frontend is not proven compatible and is not the recommended first implementation.** The dynamic routes are the hard blocker. Next static export requires that dynamic route paths be enumerable at build time or that the app’s navigation be restructured so the desktop loads one static route and resolves IDs client-side. The current app cannot enumerate future conversations/documents. Rewriting this behavior is possible but is a material UX/navigation change, and Tauri’s custom protocol may not provide the same fallback behavior as a Next server.

Running Next as a local server inside Tauri is possible in principle, but then the desktop must supervise both Next and FastAPI and secure two local origins. That is more complex than a static shell and should be compared directly against Electron.

## Required spike before any Tauri commitment

1. Make a separate, disposable prototype build configuration; do not change the production frontend in this assessment.
2. Test direct cold-start navigation to arbitrary chat, project detail, PDF viewer and compare URLs with query parameters.
3. Verify browser storage, refresh, logout, CSP, PDF.js workers, downloads and file chooser behavior under WebView2.
4. Package FastAPI as a sidecar, bind loopback only, inject a per-launch secret, wait for readiness, handle crashes, and verify clean shutdown.
5. Exercise source import with copy/link permissions and prove the renderer cannot access arbitrary files.
6. Record install size, cold start, idle/peak memory, offline behavior, update and uninstall behavior.

Do not add `output: "export"` to the existing app until all required routes and build constraints pass in an isolated proof.
