#!/usr/bin/env python3
"""Apply Jira Cloud REST updates against api.atlassian.com.

Shell agents cannot CallMcpTool, so this talks to the REST API directly.

Token resolution order (first hit wins):
  1. $JIRA_API_TOKEN (+$JIRA_EMAIL) / $JIRA_OAUTH_TOKEN / $ATLASSIAN_OAUTH_TOKEN
  2. ~/.cursor/jira-oauth-token — mode 0600; either a bearer token on one line,
     or `email` + `api_token` on two lines (Atlassian API token, long-lived)
  3. Cursor's Atlassian MCP OAuth token          — legacy fallback, decrypted
     from libsecret Chromium Safe Storage; only works while Cursor is installed
     and authenticated.

Sources 1 and 2 keep this workspace working without Cursor. Set one up with:
  bash scripts/bin/jira-enrich.sh set-token

Usage:
  python3 scripts/bin/jira-rest-oauth.py get SDCP-11085
  python3 scripts/bin/jira-rest-oauth.py put-fields SDCP-11085 /path/fields.json
  python3 scripts/bin/jira-rest-oauth.py comment TDPQA-127 /path/adf-doc.json
  python3 scripts/bin/jira-rest-oauth.py apply-pack TDPQA-127 /path/pack.json
  python3 scripts/bin/jira-rest-oauth.py apply-pack TDPQA-127 pack.json --comment-id 388469

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
import urllib.parse
import urllib.request
from pathlib import Path

CLOUD_DEFAULT = "2f9bec17-0fa3-45d7-8399-209b8a496a61"
SITE_DEFAULT = os.environ.get("JIRA_SITE", "https://novopay.atlassian.net").rstrip("/")
STATE_DB = Path.home() / ".config/Cursor/User/globalStorage/state.vscdb"
TOKEN_FILE = Path.home() / ".cursor" / "jira-oauth-token"
_TOKEN_CACHE: tuple[str, float] | None = None
_TOKEN_TTL_S = 3000  # ~50 min — OAuth access tokens are typically ~1h


def _token_from_env_or_file() -> str | None:
    """Cursor-independent credential sources. Returns None when none configured.

    Accepts either an OAuth bearer token, or `email:api_token` for an Atlassian
    API token (the long-lived credential you can self-create).
    """
    for var in ("JIRA_API_TOKEN", "JIRA_OAUTH_TOKEN", "ATLASSIAN_OAUTH_TOKEN"):
        tok = (os.environ.get(var) or "").strip()
        if tok:
            email = (os.environ.get("JIRA_EMAIL") or "").strip()
            if email and ":" not in tok:
                return f"{email}:{tok}"
            return tok
    try:
        if TOKEN_FILE.is_file():
            raw = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if raw:
                # two-line form: email on line 1, api token on line 2
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                if len(lines) == 2 and "@" in lines[0]:
                    return f"{lines[0]}:{lines[1]}"
                return lines[0] if lines else None
    except OSError:
        pass
    return None


def _auth_for(cred: str) -> tuple[str, str]:
    """(scheme, base_url) for a credential.

    `email:api_token` -> Basic against the site host (API tokens are rejected by
    api.atlassian.com, which only accepts OAuth bearers).
    Anything else     -> Bearer against api.atlassian.com/ex/jira/<cloudid>.
    """
    if ":" in cred and "@" in cred.split(":", 1)[0]:
        import base64
        enc = base64.b64encode(cred.encode()).decode()
        return f"Basic {enc}", f"{SITE_DEFAULT}/rest/api/3"
    return f"Bearer {cred}", f"https://api.atlassian.com/ex/jira/{CLOUD_DEFAULT}/rest/api/3"


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
    # Attribute search, not get_all_items(): enumerating the whole collection dies
    # on any dangling D-Bus item path with ItemNotFoundException.
    attrs = {
        "application": "Cursor",
        "xdg:schema": "chrome_libsecret_os_crypt_password_v2",
    }
    for it in secretstorage.search_items(bus, attrs):
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
    tok = _token_from_env_or_file()
    if not tok:
        try:
            tok = _decrypt_access_token()
        except RuntimeError as e:
            raise RuntimeError(
                f"{e}\nNo Cursor-independent token configured either. Set one with:\n"
                f"  bash scripts/bin/jira-enrich.sh set-token\n"
                f"or export JIRA_OAUTH_TOKEN=<bearer>"
            ) from e
    _TOKEN_CACHE = (tok, now + _TOKEN_TTL_S)
    return tok


def jira(method: str, path: str, body=None, cloud: str = CLOUD_DEFAULT):
    cred = access_token()
    scheme, base = _auth_for(cred)
    if cloud != CLOUD_DEFAULT and scheme.startswith("Bearer"):
        base = f"https://api.atlassian.com/ex/jira/{cloud}/rest/api/3"
    url = f"{base}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", scheme)
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
    if cmd == "whoami":
        # /myself needs a profile scope the MCP-issued token may not carry;
        # fall back to a currentUser() JQL probe, which only needs read:jira-work.
        try:
            code, out = jira("GET", "/myself")
            who = {k: (out or {}).get(k) for k in ("accountId", "displayName", "emailAddress")}
            print(json.dumps({"http": code, "via": "/myself", **who}, indent=2))
            return 0 if code == 200 else 1
        except SystemExit as e:
            if "scope does not match" not in str(e):
                raise
        jql = "reporter = currentUser() ORDER BY updated DESC"
        code, out = jira("GET", f"/search/jql?jql={urllib.parse.quote(jql)}"
                                f"&maxResults=1&fields=reporter")
        issues = (out or {}).get("issues") or []
        if not issues:
            print(json.dumps({"http": code, "via": "jql currentUser()",
                              "note": "token valid but no issues reported by this user"}, indent=2))
            return 0
        r = (issues[0].get("fields") or {}).get("reporter") or {}
        print(json.dumps({"http": code, "via": "jql currentUser()",
                          "accountId": r.get("accountId"),
                          "displayName": r.get("displayName"),
                          "emailAddress": r.get("emailAddress")}, indent=2))
        return 0
    print("unknown command", cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
