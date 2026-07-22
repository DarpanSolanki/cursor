#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import time
import uuid


ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / "trustt-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java"
LOS = ROOT / "trustt-platform-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java"
ACCOUNTING = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java"
)
LUA = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def redis(*args: str) -> str:
    result = subprocess.run(
        ["redis-cli", "-n", "5", "--raw", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_lms_message(raw: str) -> dict:
    first_pipe = raw.index("|")
    api_name = raw[:first_pipe]
    last_pipe = raw.rfind("|")
    prev_pipe = raw.rfind("|", 0, last_pipe)
    last_segment = raw[last_pipe + 1 :]
    second_last = raw[prev_pipe + 1 : last_pipe] if prev_pipe >= 0 else ""

    if prev_pipe >= 0 and second_last.startswith("disburseLoan"):
        original_cache_key = second_last
        producer_owner_token = last_segment
        body_end = prev_pipe
    elif last_segment.startswith("disburseLoan"):
        original_cache_key = last_segment
        producer_owner_token = None
        body_end = last_pipe
    else:
        original_cache_key = last_segment
        producer_owner_token = None
        body_end = last_pipe

    request_body = raw[first_pipe + 1 : body_end]
    return {
        "api_name": api_name,
        "request_body": request_body,
        "original_cache_key": original_cache_key,
        "producer_owner_token": producer_owner_token,
    }


def verify_message_parse_contracts() -> None:
    old_msg = (
        'disburseLoan|{"function_sub_code":"DEFAULT","payment_reinitiation_update":"false"}'
        "|disburseLoan45_INDL_370164"
    )
    old_parts = parse_lms_message(old_msg)
    require(old_parts["original_cache_key"] == "disburseLoan45_INDL_370164", "old format cache key")
    require(old_parts["producer_owner_token"] is None, "old format must not carry owner token")
    require(
        '"function_sub_code":"DEFAULT"' in old_parts["request_body"],
        "old format body must exclude cache key segment",
    )

    token = "11111111-2222-3333-4444-555555555555"
    new_msg = old_msg + "|" + token
    new_parts = parse_lms_message(new_msg)
    require(new_parts["original_cache_key"] == "disburseLoan45_INDL_370164", "new format cache key")
    require(new_parts["producer_owner_token"] == token, "new format owner token")
    require(new_parts["request_body"] == old_parts["request_body"], "new format body unchanged")

    accounting = ACCOUNTING.read_text()
    require("parseLmsMessage" in accounting, "Accounting must centralize Kafka pipe parsing")
    require("static LmsMessageParts parseLmsMessage" in accounting,
            "parseLmsMessage must be reusable for orchestration body extraction")


def verify_source_contracts() -> None:
    lib = LIB.read_text()
    los = LOS.read_text()
    accounting = ACCOUNTING.read_text()

    require("removeIfValueEquals" in lib and "redis.call('get', KEYS[1]) == ARGV[1]" in lib,
            "platform-lib must use Lua compare-and-delete")
    require('mfi.disburse.loan.producer.marker.ttl.ms", defaultValue = "600000"' in los,
            "LOS producer TTL default must be 600000ms")
    require('mfi.disburse.loan.consumer.lock.ttl.ms", defaultValue = "600000"' in accounting,
            "Accounting consumer TTL default must be 600000ms")
    require(los.index("setIfAbsent(") < los.index("if (!acquired)") < los.index("pushDataToKafkaQueue("),
            "LOS must publish only after atomic lock acquisition")
    require(accounting.index("setIfAbsent(") < accounting.index("if (!acquired)") < accounting.index(
            "executeServiceOrchestration(consumerRec, tenant)"),
            "Accounting must orchestrate only after atomic lock acquisition")
    require("removeIfValueEquals(ThreadLocalContext.getTenantCode(), cacheKey, ownerToken" in los,
            "LOS exception cleanup must be owner-safe")
    require("removeIfValueEquals(tenant.getTenantCode(), cacheKey, ownerToken" in accounting,
            "Accounting finally cleanup must be owner-safe")
    require("clearProducerMarker" in accounting and "removeIfValueEquals(tenant.getTenantCode(), originalCacheKey, producerOwnerToken" in accounting,
            "Accounting producer marker cleanup must be owner-safe when token is present")
    require("publishResult = true" in accounting and accounting.index("catch (NovopayFatalException e)") < accounting.index("publishResult = true", accounting.index("catch (NovopayFatalException e)")),
            "NovopayFatalException must publish FAILED sync and clear producer marker")
    require('cacheKey + "|" + ownerToken' in los,
            "LOS must append producer owner token to Kafka message after cache key")
    require("disbursementStatus.equalsIgnoreCase(functionSubCode)" in accounting,
            "Intermediate rows must require an explicit matching continuation stage")
    require("DEFAULT_FUNCTION_SUB_CODE.equalsIgnoreCase(functionSubCode)" in accounting,
            "DEFAULT may process only when no loan row exists")
    require("LOCK_LOAN_STATUS" in accounting and "FAIL_CLOSED" in accounting,
            "LOCK and ambiguous replay decisions must not reach orchestration")


def verify_local_redis_atomicity() -> None:
    require(redis("PING") == "PONG", "local Redis must be available")
    key = f"tdpqa54:{uuid.uuid4()}"
    orphan_key = f"tdpqa54:orphan:{uuid.uuid4()}"
    tokens = [str(uuid.uuid4()) for _ in range(32)]
    try:
        with ThreadPoolExecutor(max_workers=len(tokens)) as pool:
            results = list(pool.map(lambda token: redis("SET", key, token, "NX", "PX", "600000"), tokens))
        winners = [token for token, result in zip(tokens, results) if result == "OK"]
        require(len(winners) == 1, f"expected one atomic winner, got {len(winners)}")

        ttl = int(redis("PTTL", key))
        require(0 < ttl <= 600000, f"expected positive TTL <=600000ms, got {ttl}")
        require(redis("EVAL", LUA, "1", key, "wrong-owner") == "0",
                "wrong owner must not delete the lock")
        require(redis("GET", key) == winners[0], "wrong-owner cleanup changed the lock")
        require(redis("EVAL", LUA, "1", key, winners[0]) == "1",
                "owner must delete its lock")
        require(redis("EXISTS", key) == "0", "owned lock must be removed")

        require(redis("SET", orphan_key, "crashed-owner", "NX", "PX", "100") == "OK",
                "orphan recovery fixture must acquire a TTL lock")
        time.sleep(0.2)
        require(redis("EXISTS", orphan_key) == "0",
                "orphaned lock must expire without owner cleanup")
    finally:
        redis("DEL", key)
        redis("DEL", orphan_key)


def main() -> None:
    verify_message_parse_contracts()
    verify_source_contracts()
    verify_local_redis_atomicity()
    print("PASS TDPQA-54 PROCESSOR_MIRROR_SIM + LOCAL_REDIS_RUNTIME")
    print("producer duplicate: exactly one SET NX winner -> one Kafka publish gate")
    print("consumer duplicate: exactly one SET NX winner -> one orchestration gate")
    print("TTL: positive, default 600000ms; orphan expiry and owner-safe Lua release verified")
    print("decision matrix: terminal/LOCK/DEFAULT/intermediate fail-closed source contracts verified")


if __name__ == "__main__":
    main()
