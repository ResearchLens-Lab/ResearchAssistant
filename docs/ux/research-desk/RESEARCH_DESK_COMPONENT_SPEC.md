# Research Desk Component Specification

## Information architecture

1. **Navigation:** New research, compact Projects, and Recent Sessions/search.
2. **Conversation:** Session title and rename action, current scope, evidence count, conversation stream, and a concise persistent composer.
3. **Evidence:** Cited passages grouped by document and opened from the Evidence action or inline citation.

## Component responsibilities

- `ThreePaneChatWorkbench.jsx` owns pane sizing, session/scope state, responsive evidence behavior, and existing conversation actions.
- `ResearchHistorySidebar.jsx` renders project navigation/actions and recent session search/history. Project menu operations use the existing edit/delete/source routes and APIs.
- `PaperScopeRail.jsx` remains the source-selection surface; selecting or clearing source scope remains an explicit user action.
- `MessageItem.jsx` renders the researcher question and ResearchLens answer without implementation/provider badges.
- `GroundedAnswer.jsx` continues to render stored markdown, structured tables, charts, lists, and inline citations.
- `ChatInputBar.jsx` keeps Enter to send and Shift+Enter for a newline; optional modes are in Research tools. Existing slash commands remain available as optional shortcuts.
- `SourceInspectorRail.jsx` groups references by document/paper key and coordinates selection/open actions.
- `SourceCard.jsx` presents document identity, available authors/year, page locator, excerpt, copy, and PDF navigation.

## Width and scrolling rules

- Expanded left navigation: 268px initially; resizable 250–320px and stored in local storage.
- Collapsed left navigation: 64px with New research, Sessions, and Sources access.
- Evidence rail: 320–368px at wide desktop; overlay at 1024–1279px; existing drawer behavior below 1024px.
- Main pane flexes into remaining width, uses `min-w-0`, and owns its message scrolling. Composer stays below the message scroller.
- Existing palette variables and brand marks are preserved; no gradients or new colors were introduced.

## Empty and interaction states

The existing first-use question prompt, no-scope composer message, loading states, send errors, session empty state, citation empty state, and cancellation behavior remain. New menu actions use Radix dropdown behavior for keyboard, Escape, and outside-click handling. Deletion uses a confirmation dialog with a failure message.
