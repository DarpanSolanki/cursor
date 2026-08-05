# Port between the two workspaces on merit, never by copy

**Trigger:** 2026-08-05. Darpan: *"i hope you are taking genuine fixes only, and not just blindly
copying"* — asked while porting harness fixes between this workspace and `sliProdClaude` (Claude).

## The two workspaces are peers, and drift runs both ways

Neither side is the upstream. A normalised diff (fold out the branding layer:
`cursor-bundle`↔`claude-bundle`, `.cursor`↔`.claude`, `rules/*.mdc`↔`rules/*.md`,
`install-user-cursor-gates`↔`install-user-claude-gates`) showed **680/701 script files identical**.
This workspace happened to be ahead on the harness — `path_leak_gate.py`, a 26th test, and three
impact-mapping fixes — but the same audit found a defect *here* that the Claude side exposed.
Presence checks lie; only a normalised content diff tells you the truth.

## The port exposed a hole in this workspace's own gate

`path_leak_gate.hardcoded_ws_abs` required a **trailing slash**, so a bare
`Path("/home/darpan/Documents/sliProd")` was invisible. Proven by planting
`scripts/lib/_probe_leak_tmp.py` with exactly that string and watching the gate report `PASS`.
The pattern now ends in a char class (`/` or a closing quote).

**When a port exposes a weakness in the source, fix the source too.** The port is not done when
only one side is correct.

## Prove red on the receiving side before porting

Every candidate was demonstrated broken against **real files in the receiving workspace** — not
accepted because this side had already changed it. Three were live there
(`/dpi` matching `scripts/dpic/`, `novopay-service.sh` read as a service repo, harness edits
forced into a money-tier close); the `.cursorrules` entry in `infer_ship_apis.py` was correctly
**not** ported, because `CLAUDE.md` already fills that slot over there.

## What must never be copied verbatim

**A gate's banned-pattern list is workspace-specific.** This workspace safely bans the bare word
`sliProdClaude`. The mirror-image ban on `sliProd` fired **16 benign prose hits** on the Claude
side, because that is the family name used throughout its own docs — it had to be scoped to the
sibling *directory* instead. A noisy gate gets switched off.

Related: [[feedback_gates_must_be_provably_failable]], [[feedback_impact_mapping_harness_false_repos]].
