# sliProd Knowledge Sync

Portable snapshot of operational knowledge and agent guidance for `sliProd`, intended to quickly bootstrap a new development machine.

## Included

- `.cursor/` knowledge base and rules
- `system_brain/` flow intelligence and edge-case runbooks
- `.cursorrules`
- `AGENTS.md`
- Key payment-reinitiation docs under `docs/`

## Restore on a New Machine

From the workspace root of a fresh `sliProd` checkout:

```bash
rsync -a "/path/to/sliProd-knowledge-sync/.cursor/" "./.cursor/"
rsync -a "/path/to/sliProd-knowledge-sync/system_brain/" "./system_brain/"
cp "/path/to/sliProd-knowledge-sync/.cursorrules" "./.cursorrules"
cp "/path/to/sliProd-knowledge-sync/AGENTS.md" "./AGENTS.md"
```

Optional docs restore:

```bash
rsync -a "/path/to/sliProd-knowledge-sync/docs/" "./docs/"
```

## Notes

- This repository is documentation/knowledge only.
- Source code changes must continue in their respective service repositories.

## Sync Rule (Mandatory)

Whenever any tracked knowledge artifact in this repository is updated (`.cursor/`, `system_brain/`, `.cursorrules`, `AGENTS.md`, `docs/`):

1. Commit the change in this repo.
2. Push `main` to `origin` immediately.

This keeps machine-to-machine bootstrap state always current.
