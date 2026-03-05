# Frontend Style Architecture 2026

- `index.css`: legacy base and compatibility selectors that are still shared across the app.
- `shell-2026.css`: shell theme, cards, buttons, and layout tokens for the primary workspace.
- `frontend-primitives-2026.css`: reusable FE primitives for stacks, segmented controls, notes, dialogs, and code surfaces. New component work should start here.
- `data-manager-2026.css` and `analysis-2026.css`: domain skins layered on top of the shared primitives.

Rules:

- Prefer semantic classes over component-local inline layout styles.
- Reuse primitives before adding domain-specific selectors.
- Keep dynamic inline styles limited to measured runtime values such as chart sizes or progress widths.
