# QuadStick Profile Studio — web

Vue 3 + Vite + TypeScript + Pinia. Served by nginx in production, which also
proxies `/api` to the api container. Fully offline: the Atkinson Hyperlegible
font is bundled from npm, not fetched from a CDN.

## Run locally

```
npm install
npm run dev            # http://localhost:5173, /api proxied to localhost:8000
QS_API_URL=http://localhost:9000 npm run dev     # point at a different API
```

The API must be running (see `../api/README.md`). Everything the app calls lives
under `/api`, so the same build works behind nginx and behind the Vite proxy.

## Checks

```
npm test               # Vitest: stores, the API client, components, Library flows
npm run typecheck      # vue-tsc, strict
npm run build          # type-check then build to dist/
```

## Shape

| path | what |
|---|---|
| `src/api/types.ts` | mirrors `api/app/schemas.py`; outputs are always PlayStation names on the wire |
| `src/api/client.ts` | typed fetch wrapper; `ApiError.isValidationBlock` is the 409 that means "export refused, here are the findings" |
| `src/stores/catalog.ts` | the keyword catalog, fetched once. Also answers `hidesFlashDrive(mode, firmware)` — which modes hide the flash drive depends on the firmware, so it is never hard-coded |
| `src/stores/profiles.ts` | the Library's list and every action; a refused export lands in `blocked`, not `error`, so the UI can say *why* |
| `src/components/ExportChecklist.vue` | the manual last step: copy the file, don't touch `default.csv`, then long hard sip → joystick → lip press |
| `src/views/LibraryView.vue` | Stage 1: list, search, import, export, print, duplicate, convert, delete |
| `src/views/EditorView.vue` | the profile editor: firmware budget, mode rail, mapping grid, live checks |

## Design rules these files follow

- **Single-pointer operable.** Nothing requires holding one control while using
  another — no drag-to-reorder, no hover-only menus, no modifier-clicks. Mode
  reordering (Stage 2) uses up/down buttons for this reason.
- **Large targets.** `--target: 44px` is the floor for anything clickable.
- **Keyboard navigable, with a visible focus ring** (`--focus`), and a skip link
  as the first tab stop. Dialogs take focus on open, return it on close, and
  close on Escape — including a dialog that is already open when it mounts.
- **Legibility over flourish.** Base text is 17px, the smallest allowed is 13px,
  and reduced motion is respected.
- **One palette, shared with the print card.** The sip/puff/mode colours are the
  same values `core/qsprofile/render.py` uses, so a mode looks the same on
  screen and on paper. There is deliberately no dark mode yet: it needs its own
  sip/puff pair to stay legible, and a half-working invert is worse than none.
