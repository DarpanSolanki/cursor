#!/usr/bin/env python3
"""Apply Jira Cloud REST updates using Cursor's Atlassian MCP OAuth token.

Shell agents cannot CallMcpTool. This decrypts the Cursor-stored MCP OAuth
access_token via libsecret Chromium Safe Storage and calls api.atlassian.com.

Usage:
  python3 scripts/bin/jira-rest-from-cursor-oauth.py get SDCP-11085
  python3 scripts/bin/jira-rest-from-cursor-oauth.py put-fields SDCP-11085 /path/fields.json
  python3 scripts/bin/jira-rest-from-cursor-oauth.py comment TDPQA-127 /path/adf-doc.json
  python3 scripts/bin/jira-rest-from-cursor-oauth.py apply-pack TDPQA-127 /path/pack.json
  python3 scripts/bin/jira-rest-from-cursor-oauth.py apply-pack TDPQA-127 pack.json --comment-id 388469

fields.json = raw Jira fields object (assignee, customfield_*, …)
pack.json = output of jira-fix-adf.py pack (edit_fields + comment_adf)
comment body file = ADF doc object {"type":"doc","version":1,...}

Never prints or commits tokens. Requires: secretstorage + cryptography
(install via scripts/bin/jira-enrich.sh ensure).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CLOUD_DEFAULT = "2f9bec17-0fa3-45d7-8399-209b8a496a61"
STATE_DB = Path.home() / ".config/Cursor/User/globalStorage/state.vscdb"
_TOKEN_CACHE: tuple[str, float] | None = None
_TOKEN_TTL_S = 3000  # ~50 min — access tokens are typically ~1h


def _cursor_safe_storage_password() -> bytes:
    try:
        import secretstorage
    except ImportError as e:
        raise RuntimeError(
            "secretstorage not installed — run: bash scripts/bin/jira-enrich.sh ensure"
        ) from e

    bus = secretstorage.dbus_init()
    coll = secretstorage.get_default_collection(bus)
    if coll.is_locked():
        coll.unlock()
    for it in coll.get_all_items():
        attrs = it.get_attributes() or {}
        if (
            attrs.get("application") == "Cursor"
            and attrs.get("xdg:schema") == "chrome_libsecret_os_crypt_password_v2"
        ):
            return it.get_secret()
    raise RuntimeError("Cursor Chromium Safe Storage password not found in libsecret")


def _decrypt_chromium_blob(password: bytes, blob: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    if not (blob.startswith(b"v10") or blob.startswith(b"v11")):
        raise RuntimeError(f"unsupported encrypt prefix: {blob[:8]!r}")
    payload = blob[3:]
    key = hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1, dklen=16)
    iv = b" " * 16
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = dec.update(payload) + dec.finalize()
    unpad = padding.PKCS7(128).unpadder()
    return unpad.update(padded) + unpad.finalize()


def _decrypt_access_token() -> str:
    password = _cursor_safe_storage_password()
    con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    cur = con.cursor()
    keyname = None
    for (k,) in cur.execute("SELECT key FROM ItemTable WHERE key LIKE 'mcpOAuth.secret%'"):
        if "b2tlbnM" in k:
            keyname = k
            break
    if not keyname:
        raise RuntimeError("mcpOAuth tokens key not found — re-auth Atlassian MCP in Cursor")
    val = cur.execute("SELECT value FROM ItemTable WHERE key=?", (keyname,)).fetchone()[0]
    con.close()
    wrap = json.loads(val)
    raw = bytes(wrap["data"])
    pt = json.loads(_decrypt_chromium_blob(password, raw).decode("utf-8"))
    tok = pt.get("access_token")
    if not tok:
        raise RuntimeError("access_token missing in decrypted MCP oauth blob")
    return tok


def access_token(*, force_refresh: bool = False) -> str:
    global _TOKEN_CACHE
    now = time.time()
    if not force_refresh and _TOKEN_CACHE and now < _TOKEN_CACHE[1]:
        return _TOKEN_CACHE[0]
    tok = _decrypt_access_token()
    _TOKEN_CACHE = (tok, now + _TOKEN_TTL_S)
    return tok


def jira(method: str, path: str, body=None, cloud: str = CLOUD_DEFAULT):
    token = access_token()
    url = f"https://api.atlassian.com/ex/jira/{cloud}/rest/api/3{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise SystemExit(f"HTTP {e.code} {path}: {err[:1200]}")


def apply_pack(key: str, pack_path: Path, comment_id: str | None = None) -> dict:
    pack = json.loads(pack_path.read_text())
    fields = pack.get("edit_fields") or {}
    results: dict[str, object] = {"issue": key}
    comment_id = comment_id or (str(pack.get("comment_id") or "").strip() or None)

    if fields:
        code, _ = jira("PUT", f"/issue/{key}", {"fields": fields})
        results["fields_http"] = code

    comment = pack.get("comment_adf")
    if comment:
        if comment_id:
            code, out = jira(
                "PUT",
                f"/issue/{key}/comment/{comment_id}",
                {"body": comment},
            )
            results["comment_action"] = "update"
        else:
            code, out = jira("POST", f"/issue/{key}/comment", {"body": comment})
            results["comment_action"] = "create"
        results["comment_http"] = code
        results["comment_id"] = (out or {}).get("id") if isinstance(out, dict) else comment_id

    return results


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "get":
        key = argv[2]
        fields = argv[3] if len(argv) > 3 else "summary,status"
        code, out = jira("GET", f"/issue/{key}?fields={fields}")
        print(json.dumps({"http": code, "issue": out}, indent=2)[:4000])
        return 0
    if cmd == "put-fields":
        key, path = argv[2], argv[3]
        fields = json.loads(Path(path).read_text())
        if "fields" in fields and len(fields) == 1:
            fields = fields["fields"]
        code, out = jira("PUT", f"/issue/{key}", {"fields": fields})
        print(json.dumps({"http": code, "ok": code in (200, 204)}))
        return 0 if code in (200, 204) else 1
    if cmd == "comment":
        key, path = argv[2], argv[3]
        body = json.loads(Path(path).read_text())
        if "commentBody" in body:
            body = body["commentBody"]
        if "body" in body and body.get("type") != "doc":
            body = body["body"]
        code, out = jira("POST", f"/issue/{key}/comment", {"body": body})
        print(json.dumps({"http": code, "comment_id": (out or {}).get("id")}))
        return 0 if code in (200, 201) else 1
    if cmd == "apply-pack":
        if len(argv) < 4:
            print("Usage: apply-pack <ISSUE-KEY> <pack.json> [--comment-id ID]", file=sys.stderr)
            return 2
        key, path = argv[2], argv[3]
        comment_id = None
        if "--comment-id" in argv:
            comment_id = argv[argv.index("--comment-id") + 1]
        t0 = time.perf_counter()
        result = apply_pack(key, Path(path), comment_id)
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        print(json.dumps(result, indent=2))
        return 0
    print("unknown command", cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
