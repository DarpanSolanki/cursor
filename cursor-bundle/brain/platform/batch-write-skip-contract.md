# Batch write-skip contract (`force_async`)

**Platform owns Future resolve.** Job `*FailureEntityMapper.fromWriter` must never call `resolveSkipItem`, `Future`, or job-local wrappers like `DpiBatchWriterSkipItemSupport`.

## Layering

```
onSkipInWrite(raw) 
  → GenericListenerV3.resolveWriterSkipItem 
  → BatchWriterSkipItemSupport.resolveSkipItem (Future → O)
  → mapper.fromWriter(O)
```

- **Vo `O`** (dpi calc, dpi billing): null-safe fields on `O` only.
- **List `O`** (dpi booking): `item == null || item.isEmpty()` then `item.get(0)`.

## Why calc had redundant unwrap (2026-07-02)

| Commit | What changed | Calc mapper |
|--------|----------------|-------------|
| `a8ad4a240` | Added `DpiBatchWriterSkipItemSupport` + booking/billing unwrap | **Not in diff** — calc already had plain Vo mapper |
| `ace99fdd0` | Added calc unwrap “to align with booking” | **Redundant** once platform `GenericListenerV3` resolves Future before `fromWriter` |
| Platform `43144909ac` | `resolveSkipItem` in listener | Correct generic fix — calc/billing should stay plain Vo mappers |

**Process gap:** no automated check that Vo mappers stay free of async unwrap after a platform-lib fix. **Gate:** `scripts/bin/audit-batch-skip-mappers.sh` (ship-loop on DPI / infra-batch skip paths).

## Verify

```bash
bash scripts/bin/audit-batch-skip-mappers.sh --dpi-only
ntest run dpic.batch.force_async_modes
```
