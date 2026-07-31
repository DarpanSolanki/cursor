# Semantics + Framework bone (2026-07-31)

Typed KG layer for **what is X** and **how the substrate behaves**. Builder: `cursor-bundle/kg/bin/build_semantics_bone.py`. Query: `kg concept <name>` or MCP `kg_concept` / `kg_search`.

## Node kinds

| Kind | Answers |
|------|---------|
| `entity` | @Entity/@Table purpose, key columns, maps_to `table:*` |
| `txn_type` | LAN `transaction_type` literals + creators (file:line) |
| `gl_mech` | Placeholder→IAD/GL **mechanics** (not product GL account numbers) |
| `batch_cfg` | Chunk (when coded); skip/retry often UNKNOWN |
| `redis_key` | From redis-key-registry |
| `framework` | Spring/Hibernate/Kafka/Redis/HTTP/batch as used here |
| `server` | `server.port` per service |

## Honesty

Product-specific GL account numbers, Kafka DLQ/concurrency per env, Tomcat pools, and entities without db-code-map purpose are **UNKNOWN** — never invented. See `semantics:unknown_index` and the session report UNKNOWN list.
