# Working Rules for this project's production pass

- Read `code_review.md` (active plan + TODO state) and `PRODUCTION_NOTES.md`
  (change-and-why learning log) before starting work.
- **Recovery:** if the context was compacted/reset/lost, DO NOT act from memory.
  Re-read `code_review.md` top to bottom, then `PRODUCTION_NOTES.md`, before doing
  anything. Never start work or the walkthrough until the user says so.
- Max 50 lines changed per step. Functions: written in full, then explained line-by-line
  with why. Classes: function-by-function, explaining why each function is needed.
  Full config files (toml/yaml/env): written fully, then every line explained
  top-to-bottom.
- Adding/removing any variable: explain what it means, why, and how it connects to
  other code/files.
- Adding/removing any setting or configuration: explain What it means, why, and how it
  connects to other code/files.
- Walkthrough mode: go over changes small change by small change; stop for user
  questions and approval. Ask first and clarify instead of assuming.