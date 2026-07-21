#!/usr/bin/env python3
"""Publish a LOS-shaped disburseLoan message to Kafka (TDPQA-54 harness).

Message format (matches DisburseLoanAPIUtil after hardening):
  apiName|jsonBody|cacheKey|ownerToken

Also SET NX the producer Redis marker when --with-redis is set.
Note: redis-cli string values are NOT Java-serializer compatible with removeIfValueEquals;
default is --skip-redis so Kafka parse/ownerToken path can run without leaving stale locks.
Use real LOS DisburseLoanAPIUtil for end-to-end Redis owner clear proof.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


DEFAULT_TOPIC = os.environ.get("NPS_DISBURSE_TOPIC", "disburse_loan_api_mfi_local")
DEFAULT_BOOTSTRAP = os.environ.get("NPS_KAFKA_BOOTSTRAP", "127.0.0.1:9092")
DEFAULT_KAFKA_HOME = os.environ.get("KAFKA_HOME", "/home/darpan/Documents/kafka_2.12-3.7.0")
PRODUCT_ENTITY = {"2": "INDIVIDUAL", "44": "GROUP", "45": "INDIVIDUAL"}


def build_cache_key(payload: dict) -> str:
    req = payload.get("request") or {}
    loan = req.get("loan_details") or {}
    disb = req.get("disbursement_details") or {}
    product_id = str(loan.get("product_id") or "").strip()
    ext = str(disb.get("external_ref_number") or "").strip()
    entity = str(
        req.get("entity_type")
        or loan.get("entity_type")
        or os.environ.get("DISBURSE_ENTITY_TYPE")
        or PRODUCT_ENTITY.get(product_id, "INDIVIDUAL")
    ).strip()
    if not product_id or not ext:
        raise SystemExit("payload missing product_id or external_ref_number")
    # Product labels (INDL/JLG/SHG) are not entity_type — map common mistakes.
    label_to_entity = {"INDL": "INDIVIDUAL", "JLG": "INDIVIDUAL", "SHG": "GROUP"}
    entity = label_to_entity.get(entity.upper(), entity)
    return f"disburseLoan{product_id}_{entity}_{ext}"


def redis_set_nx(cache_key: str, owner_token: str, ttl_ms: int = 600000) -> None:
    redis_key = f"localmfi_{cache_key}"
    # SET key value PX ttl NX
    out = subprocess.check_output(
        ["redis-cli", "-n", "5", "SET", redis_key, owner_token, "PX", str(ttl_ms), "NX"],
        text=True,
    ).strip()
    if out != "OK":
        raise SystemExit(f"producer Redis SET NX failed for {redis_key}: {out!r} (stale lock?)")
    ttl = subprocess.check_output(["redis-cli", "-n", "5", "PTTL", redis_key], text=True).strip()
    print(f"[kafka-publish] redis NX ok key={redis_key} ttl_ms={ttl} owner={owner_token}", flush=True)


def publish(message: str, *, topic: str, bootstrap: str, kafka_home: str) -> None:
    producer = Path(kafka_home) / "bin" / "kafka-console-producer.sh"
    if not producer.is_file():
        raise SystemExit(f"missing kafka console producer: {producer}")
    proc = subprocess.run(
        [str(producer), "--bootstrap-server", bootstrap, "--topic", topic],
        input=message + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"kafka-console-producer failed rc={proc.returncode}: {proc.stderr or proc.stdout}"
        )
    print(f"[kafka-publish] published topic={topic} bytes={len(message)}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request-file", required=True)
    p.add_argument("--topic", default=DEFAULT_TOPIC)
    p.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP)
    p.add_argument("--kafka-home", default=DEFAULT_KAFKA_HOME)
    p.add_argument("--ttl-ms", type=int, default=600000)
    p.add_argument(
        "--with-redis",
        action="store_true",
        help="SET NX producer marker via redis-cli (not Java-serializer compatible; can leave stale locks).",
    )
    p.add_argument("--skip-redis", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()

    payload = json.loads(Path(args.request_file).read_text(encoding="utf-8"))
    cache_key = build_cache_key(payload)
    owner = str(uuid.uuid4())
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    message = f"disburseLoan|{body}|{cache_key}|{owner}"
    segments = message.count("|")
    if segments < 3:
        raise SystemExit(f"invalid message segment count: {segments}")
    print(
        f"[kafka-publish] format=apiName|json|cacheKey|ownerToken cache_key={cache_key}",
        flush=True,
    )
    if args.with_redis and not args.skip_redis:
        redis_set_nx(cache_key, owner, ttl_ms=args.ttl_ms)
    else:
        # Avoid stale localmfi_* keys from prior redis-cli NX that Java cannot clear.
        redis_key = f"localmfi_{cache_key}"
        subprocess.run(["redis-cli", "-n", "5", "DEL", redis_key, f"localmfi_dl{cache_key}"], check=False)
        print(f"[kafka-publish] redis skip (cleared {redis_key} if any)", flush=True)
    publish(message, topic=args.topic, bootstrap=args.bootstrap, kafka_home=args.kafka_home)
    # Machine-readable for suite
    print(json.dumps({"cache_key": cache_key, "owner_token": owner, "topic": args.topic}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
