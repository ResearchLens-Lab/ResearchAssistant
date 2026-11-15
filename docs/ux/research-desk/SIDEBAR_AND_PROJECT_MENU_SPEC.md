# Sidebar and Project Menu Specification

## Sidebar

Expanded navigation defaults to 268px, can be resized from 250–320px, and persists width in browser local storage. The collapse control switches to a 64px icon rail while preserving access to New research, Sessions, and Sources. Projects and recent sessions are distinct groups; session filtering and grouping remain intact.

## Project rows

Each project row shows its name, selected state, and indexed document count. A Radix three-dot menu is available on hover, keyboard focus, and touch. Supported actions:

- **Use this project:** sets the selected source scope through the existing scope store.
- **Open project:** navigates to the existing project route.
- **Edit details:** opens the existing project edit modal and update API.
- **Manage sources:** opens the existing upload/source management route.
- **Delete project:** opens a confirmation dialog and calls the existing delete API.

## Deletion semantics

The backend checks ownership. When a RAG index is available it clears the project's vector/lexical index first. It then removes document database rows and the project row in a database transaction, and removes stored original files after commit. If index cleanup fails, it stops before the database/file deletion. The dialog states these semantics and explains irreversibility. On successful deletion the project query refreshes and the deleted project is removed from the selected scope. Errors remain visible in the confirmation dialog.

## Sessions

Recent sessions retain the existing date grouping, title search, selection, rename, and delete behaviors. Project deletion and session deletion remain separate operations.
