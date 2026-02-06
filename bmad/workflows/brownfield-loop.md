# Brownfield Loop (BMAD Adapted)

Use this loop for existing-system changes.

1. Select domain.
2. Load `bmad/context/generated/00-index.md` and the target domain pack.
3. Draft story using `bmad/templates/story-template.md`.
4. Implement changes in one domain first; cross-domain edits require explicit contract note.
5. Run relevant tests and compile checks.
6. Update context map if ownership/contracts changed.
7. Regenerate context packs.

## Guardrails

- No-lookahead invariants must remain valid.
- Strategy execution changes must include test updates.
- API contract changes must check frontend and runner compatibility.
