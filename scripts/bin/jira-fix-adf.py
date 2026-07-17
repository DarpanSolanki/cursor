#!/usr/bin/env python3
"""Build ADF payloads for SDCP field handoff and TDPQA comment handoff. No API calls."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def text_node(text: str, *, bold: bool = False) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": text}
    if bold:
        node["marks"] = [{"type": "strong"}]
    return node


def paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [text_node(text)]}


def heading_paragraph(text: str) -> dict[str, Any]:
    """Bold single-line section label for comment handoffs (TDPQA)."""
    return {"type": "paragraph", "content": [text_node(text, bold=True)]}

def bullet_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [paragraph(item)],
            }
            for item in items
        ],
    }


def ordered_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "orderedList",
        "content": [
            {
                "type": "listItem",
                "content": [paragraph(item)],
            }
            for item in items
        ],
    }


def doc(*blocks: dict[str, Any]) -> dict[str, Any]:
    return {"type": "doc", "version": 1, "content": list(blocks)}


def rca_doc(situation: str, cause: str, resolution: str) -> dict[str, Any]:
    return doc(paragraph(situation), paragraph(cause), paragraph(resolution))


def impact_doc(bullets: list[str]) -> dict[str, Any]:
    return doc(bullet_list(bullets))


def dev_scenarios_doc(scenarios: list[str]) -> dict[str, Any]:
    return doc(ordered_list(scenarios))


def pre_post_doc(
    pre: str = "NA", post: str = "NA"
) -> dict[str, Any]:
    return doc(
        paragraph(f"Pre deployment: {pre}"),
        paragraph(f"Post deployment: {post}"),
    )


def micro_service_field(option_ids: list[str]) -> list[dict[str, str]]:
    return [{"id": oid} for oid in option_ids]


_MENTIONS_CACHE: dict[str, str] | None = None
_OWNERS_CACHE: dict[str, Any] | None = None


def load_mentions() -> dict[str, str]:
    global _MENTIONS_CACHE
    if _MENTIONS_CACHE is not None:
        return _MENTIONS_CACHE
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / ".cursor/skills/jira-fix-update/mentions.json"
    )
    raw = json.loads(path.read_text())
    _MENTIONS_CACHE = {k: v for k, v in raw.items() if not k.startswith("_")}
    return _MENTIONS_CACHE


def mention_node(account_id: str, text: str) -> dict[str, Any]:
    return {"type": "mention", "attrs": {"id": account_id, "text": text}}


def _paragraph_with_mentions(line: str, mentions: dict[str, str]) -> dict[str, Any]:
    """Turn '@Name ...' tokens into ADF mention nodes. Longest name first so
    'Sudheer Pandey' wins over 'Sudheer'. Unknown @tokens stay plain text."""
    names = sorted(mentions.keys(), key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(r"@(" + alt + r")\b", re.IGNORECASE)
    lower = {k.lower(): v for k, v in mentions.items()}

    content: list[dict[str, Any]] = []
    pos = 0
    for m in pattern.finditer(line):
        if m.start() > pos:
            content.append(text_node(line[pos : m.start()]))
        name = m.group(1)
        content.append(mention_node(lower[name.lower()], f"@{name}"))
        content.append(text_node(" "))
        pos = m.end()
        if pos < len(line) and line[pos] == " ":
            pos += 1
    if pos < len(line):
        content.append(text_node(line[pos:]))
    if not content:
        content = [text_node(line)]
    return {"type": "paragraph", "content": content}


def comment_doc(text: str, mentions: dict[str, str] | None = None) -> dict[str, Any]:
    """Build a comment ADF doc. Blank lines separate paragraphs; @Name tokens
    that match the mentions map become real mention nodes (markdown @ does not tag)."""
    if mentions is None:
        mentions = load_mentions()
    blocks: list[dict[str, Any]] = []
    buf: list[str] = []
    for ln in text.splitlines():
        if ln.strip() == "":
            if buf:
                blocks.append(_paragraph_with_mentions(" ".join(buf).strip(), mentions))
                buf = []
            continue
        buf.append(ln.rstrip())
    if buf:
        blocks.append(_paragraph_with_mentions(" ".join(buf).strip(), mentions))
    return doc(*(blocks or [paragraph(text)]))


# Projects without SDCP RCA/Impact/Dev custom fields → comment handoff mode.
COMMENT_HANDOFF_PROJECTS = frozenset({"TDPQA", "HSQA", "AUT"})


def project_mode(issue_key: str) -> dict[str, Any]:
    """Route SDCP field handoff vs TDPQA-style comment handoff from issue key."""
    key = (issue_key or "").strip().upper()
    prefix = key.split("-", 1)[0] if "-" in key else key
    if prefix == "SDCP":
        mode = "field_handoff"
    else:
        # TDPQA / HSQA / AUT / unknown: no SDCP RCA fields — comment is canonical.
        mode = "comment_handoff"
    return {
        "issue_key": key,
        "project": prefix,
        "mode": mode,
        "owners_cmd": "owners" if mode == "field_handoff" else "owners_tdpqa",
        "note": (
            "Fill customfield_11137/11138/11901 + short ping comment"
            if mode == "field_handoff"
            else "Put RCA+Impact+Dev+Pre/Post in ONE handoff comment; set project owners only"
        ),
    }


def load_tdpqa_owners() -> dict[str, Any]:
    """TDPQA simplified project — Dev Owner / QA Owner people fields only."""
    return {
        "customfield_11952": [{"accountId": "5e9d51241067100c195f7b12"}],  # Dev Owner
        "customfield_11953": [{"accountId": "5efab45c61665e0b9ed294bd"}],  # QA Owner
    }


def handoff_comment_doc(payload: dict[str, Any]) -> dict[str, Any]:
    """Canonical QA-release comment for projects without RCA/Impact/Dev fields.

    Expected payload keys:
      lead_in: str (with @mentions)
      rca: {situation, cause, resolution} OR situation/cause/resolution top-level
      impact: list[str]
      dev: list[str]
      pre / post: str (default NA)
      service: str optional (e.g. Accounting)
      result: str optional
      aitdp_percent: float — 0–1 fraction (0.75) OR whole percent (75); required for handoff
      aitdp_remarks: str — 2–4 sentences how AI helped; required; never Cursor brand
    """
    mentions = load_mentions()
    blocks: list[dict[str, Any]] = []

    lead = (payload.get("lead_in") or "").strip()
    if lead:
        blocks.append(_paragraph_with_mentions(lead, mentions))

    rca = payload.get("rca") or {}
    situation = (rca.get("situation") or payload.get("situation") or "").strip()
    cause = (rca.get("cause") or payload.get("cause") or "").strip()
    resolution = (rca.get("resolution") or payload.get("resolution") or "").strip()
    if situation or cause or resolution:
        blocks.append(heading_paragraph("RCA"))
        for part in (situation, cause, resolution):
            if part:
                blocks.append(paragraph(part))

    impact = [str(x).strip() for x in (payload.get("impact") or []) if str(x).strip()]
    if impact:
        blocks.append(heading_paragraph("Impact"))
        blocks.append(bullet_list(impact))

    dev = [str(x).strip() for x in (payload.get("dev") or []) if str(x).strip()]
    if dev:
        blocks.append(heading_paragraph("Dev test / QA retest"))
        blocks.append(ordered_list(dev))

    result = (payload.get("result") or "").strip()
    if result:
        blocks.append(heading_paragraph("Test result"))
        blocks.append(paragraph(result))

    service = (payload.get("service") or "").strip()
    if service:
        blocks.append(heading_paragraph("Service"))
        blocks.append(paragraph(service))

    pre = payload.get("pre", "NA")
    post = payload.get("post", "NA")
    blocks.append(heading_paragraph("Pre / Post deployment"))
    blocks.append(paragraph(f"Pre deployment: {pre}"))
    blocks.append(paragraph(f"Post deployment: {post}"))

    # AITDP — mandatory on TDPQA comment handoff (no custom fields on that project)
    pct_raw = payload.get("aitdp_percent", payload.get("aitdp_effectiveness"))
    remarks = (
        payload.get("aitdp_remarks")
        or payload.get("aitdp_remark")
        or ""
    ).strip()
    if pct_raw is not None and str(pct_raw).strip() != "":
        try:
            pct_f = float(pct_raw)
        except (TypeError, ValueError) as e:
            raise ValueError(f"aitdp_percent must be a number, got {pct_raw!r}") from e
        # Accept 0–1 fraction OR whole percent (75). Display always as UI %.
        if 0 <= pct_f <= 1:
            display_pct = int(round(pct_f * 100)) if pct_f * 100 == int(pct_f * 100) else round(pct_f * 100, 1)
        else:
            display_pct = int(pct_f) if float(pct_f) == int(pct_f) else pct_f
        blocks.append(heading_paragraph("AITDP"))
        blocks.append(paragraph(f"JIRA as per AI TDP: Yes"))
        blocks.append(paragraph(f"AITDP effectiveness: {display_pct}%"))
        if remarks:
            blocks.append(paragraph(remarks))

    return doc(*blocks)


def require_aitdp_in_handoff(payload: dict[str, Any]) -> None:
    """Fail closed — TDPQA handoff without AITDP % + remarks is incomplete."""
    pct = payload.get("aitdp_percent", payload.get("aitdp_effectiveness"))
    remarks = (
        payload.get("aitdp_remarks")
        or payload.get("aitdp_remark")
        or ""
    ).strip()
    missing: list[str] = []
    if pct is None or str(pct).strip() == "":
        missing.append("aitdp_percent (0–1 fraction, e.g. 0.75)")
    if not remarks:
        missing.append("aitdp_remarks (2–4 sentences, no Cursor brand)")
    if missing:
        raise ValueError(
            "TDPQA handoff_comment requires AITDP in the comment: missing "
            + "; ".join(missing)
        )

# Option ids — keep in sync with fields-reference.md
MICRO = {
    "accounting": "11843",
    "los": "11844",
    "payments": "11842",
    "actor": "11845",
    "batch": "11850",
    "lib": "11848",
    "task": "11840",
    "api_gateway": "11851",
    "approval": "11852",
    "audit": "11853",
    "authorization": "11854",
    "reporting": "11847",
    "bpmn": "11846",
    "android": "11849",
    "initial_setup": "11841",
}


def load_default_owners() -> dict[str, Any]:
    global _OWNERS_CACHE
    if _OWNERS_CACHE is not None:
        return dict(_OWNERS_CACHE)
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / ".cursor/skills/jira-fix-update/owners-defaults.json"
    raw = json.loads(path.read_text())
    out: dict[str, Any] = {}
    for key, val in raw.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            out[key] = [{"accountId": u["accountId"]} for u in val]
        elif isinstance(val, dict):
            out[key] = {"accountId": val["accountId"]}
    _OWNERS_CACHE = out
    return dict(out)


CLOUD_ID = "2f9bec17-0fa3-45d7-8399-209b8a496a61"
DEFAULT_ASSIGNEE = {"accountId": "5e9d51241067100c195f7b12"}
AITDP_YES = [{"id": "12039"}]


def normalize_aitdp_fraction(pct_raw: Any) -> float:
    pct_f = float(pct_raw)
    if pct_f > 1:
        return pct_f / 100.0
    return pct_f


def flatten_handoff_text(payload: dict[str, Any]) -> str:
    """Collect all user-visible strings for one forbidden-token scan."""
    flat_parts: list[str] = []
    for key in ("lead_in", "ping_comment", "comment", "result", "service", "pre", "post"):
        if payload.get(key) is not None:
            flat_parts.append(str(payload[key]))
    rca = payload.get("rca") or {}
    for k in ("situation", "cause", "resolution"):
        v = rca.get(k) or payload.get(k)
        if v:
            flat_parts.append(str(v))
    for lst_key in ("impact", "dev", "scenario_titles"):
        flat_parts.extend(str(x) for x in (payload.get(lst_key) or []))
    for k in ("test_result", "aitdp_remarks", "aitdp_remark"):
        if payload.get(k) is not None:
            flat_parts.append(str(payload[k]))
    return "\n".join(flat_parts)


_SDCP_SECTION_HEADER = re.compile(
    r"^\s*(RCA|Impact|Dev test(?:\s*/\s*QA retest)?|Pre\s*/\s*Post(?:\s+deployment)?|AITDP)\s*:?\s*$"
    r"|\b(RCA:|Impact:|Dev test\s*/|Pre deployment:|AITDP effectiveness:)",
    re.IGNORECASE | re.MULTILINE,
)
_SDCP_PING_MAX_CHARS = 500
_SDCP_PING_MAX_SENTENCES = 4


def _sentence_count(text: str) -> int:
    parts = [p.strip() for p in re.split(r"[.!?]+", text or "") if p.strip()]
    return len(parts)


def validate_mode_comment(mode: str, payload: dict[str, Any]) -> None:
    """Project-aware comment shape — fail closed before ADF build.

    SDCP (field_handoff): comment optional; if present → short retest ping only.
    TDPQA (comment_handoff): one structured handoff (rca + impact + dev); no ping-only.
    """
    if mode == "field_handoff":
        ping = (payload.get("ping_comment") or payload.get("comment") or "").strip()
        if not ping:
            return
        errors: list[str] = []
        if len(ping) > _SDCP_PING_MAX_CHARS:
            errors.append(f"SDCP ping length {len(ping)} > {_SDCP_PING_MAX_CHARS}")
        sc = _sentence_count(ping)
        if sc > _SDCP_PING_MAX_SENTENCES:
            errors.append(f"SDCP ping has {sc} sentences (max {_SDCP_PING_MAX_SENTENCES})")
        if _SDCP_SECTION_HEADER.search(ping):
            errors.append(
                "SDCP ping must not contain structured handoff section headers "
                "(put RCA/Impact/Dev in custom fields)"
            )
        hits = scan_forbidden(ping)
        if hits:
            errors.append("FORBIDDEN in SDCP ping: " + ", ".join(hits))
        if errors:
            raise ValueError("; ".join(errors))
        return

    # comment_handoff (TDPQA / HSQA / AUT / unknown)
    rca = payload.get("rca") or {}
    situation = (rca.get("situation") or payload.get("situation") or "").strip()
    cause = (rca.get("cause") or payload.get("cause") or "").strip()
    resolution = (rca.get("resolution") or payload.get("resolution") or "").strip()
    impact = [str(x).strip() for x in (payload.get("impact") or []) if str(x).strip()]
    dev = [str(x).strip() for x in (payload.get("dev") or []) if str(x).strip()]
    missing: list[str] = []
    if not (situation and cause and resolution):
        missing.append("rca.situation/cause/resolution")
    if not impact:
        missing.append("impact[]")
    if not dev:
        missing.append("dev[]")
    if missing:
        raise ValueError(
            "TDPQA comment_handoff requires structured handoff ("
            + ", ".join(missing)
            + ") — not a one-liner ping"
        )
    # ping_comment alone is never enough on comment_handoff
    if (payload.get("ping_comment") or "").strip() and not (
        situation and cause and resolution and impact and dev
    ):
        raise ValueError(
            "TDPQA comment_handoff ignores ping_comment as the handoff; "
            "provide rca/impact/dev (edit existing comment in place)"
        )


def require_aitdp_fields(payload: dict[str, Any], *, label: str = "handoff") -> float:
    pct = payload.get("aitdp_percent", payload.get("aitdp_effectiveness"))
    remarks = (
        payload.get("aitdp_remarks")
        or payload.get("aitdp_remark")
        or ""
    ).strip()
    missing: list[str] = []
    if pct is None or str(pct).strip() == "":
        missing.append("aitdp_percent (0–1 fraction, e.g. 0.75)")
    if not remarks:
        missing.append("aitdp_remarks (2–4 sentences, no Cursor brand)")
    if missing:
        raise ValueError(
            f"{label} requires AITDP: missing " + "; ".join(missing)
        )
    return normalize_aitdp_fraction(pct)


def build_handoff_pack(issue_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One-shot handoff: mode routing, owners, ADF fields, comment, single scan."""
    mode_info = project_mode(issue_key)
    mode = mode_info["mode"]
    flat = flatten_handoff_text(payload)
    hits = scan_forbidden(flat)
    if hits:
        raise ValueError("FORBIDDEN in pack: " + ", ".join(hits))
    validate_mode_comment(mode, payload)

    edit_fields: dict[str, Any] = {"assignee": dict(DEFAULT_ASSIGNEE)}
    comment_adf: dict[str, Any] | None = None
    comment_id = (
        str(payload.get("comment_id") or payload.get("existing_comment_id") or "").strip()
        or None
    )

    if mode == "field_handoff":
        aitdp_frac = require_aitdp_fields(payload, label="SDCP pack")
        edit_fields.update(load_default_owners())

        rca = payload.get("rca") or {}
        situation = (rca.get("situation") or payload.get("situation") or "").strip()
        cause = (rca.get("cause") or payload.get("cause") or "").strip()
        resolution = (rca.get("resolution") or payload.get("resolution") or "").strip()
        if situation or cause or resolution:
            edit_fields["customfield_11137"] = rca_doc(situation, cause, resolution)

        impact = [str(x).strip() for x in (payload.get("impact") or []) if str(x).strip()]
        if impact:
            edit_fields["customfield_11138"] = impact_doc(impact)

        dev = [str(x).strip() for x in (payload.get("dev") or []) if str(x).strip()]
        if dev:
            edit_fields["customfield_11901"] = dev_scenarios_doc(dev)

        scenario_titles = [
            str(x).strip()
            for x in (payload.get("scenario_titles") or [])
            if str(x).strip()
        ]
        if not scenario_titles and dev:
            scenario_titles = [
                s.split(". Result:")[0].split(" Result:")[0].strip() for s in dev
            ]
        if scenario_titles:
            edit_fields["customfield_11937"] = dev_scenarios_doc(scenario_titles)

        test_result = (
            payload.get("test_result") or "All listed developer scenarios: Pass."
        ).strip()
        edit_fields["customfield_11938"] = doc(paragraph(test_result))

        micro_keys = [str(k).strip().lower() for k in (payload.get("micro") or [])]
        if micro_keys:
            unknown = [k for k in micro_keys if k not in MICRO]
            if unknown:
                raise ValueError(f"unknown micro service keys: {unknown}")
            edit_fields["customfield_11337"] = micro_service_field([MICRO[k] for k in micro_keys])

        pre = payload.get("pre", "NA")
        post = payload.get("post", "NA")
        edit_fields["customfield_11336"] = pre_post_doc(str(pre), str(post))
        edit_fields["customfield_11477"] = AITDP_YES
        edit_fields["customfield_11676"] = aitdp_frac
        remarks = (
            payload.get("aitdp_remarks") or payload.get("aitdp_remark") or ""
        ).strip()
        edit_fields["customfield_11677"] = doc(paragraph(remarks))

        ping = (payload.get("ping_comment") or payload.get("comment") or "").strip()
        if ping:
            comment_adf = comment_doc(ping)
    else:
        require_aitdp_in_handoff(payload)
        edit_fields.update(load_tdpqa_owners())
        comment_adf = handoff_comment_doc(payload)

    return {
        **mode_info,
        "issue_key": mode_info["issue_key"],
        "cloud_id": CLOUD_ID,
        "edit_fields": edit_fields,
        "comment_adf": comment_adf,
        "comment_id": comment_id,
        "prefer_edit_in_place": bool(comment_id) if mode == "comment_handoff" else False,
        "scan": "OK",
        "mcp_hint": {
            "editJiraIssue": {
                "cloudId": "novopay.atlassian.net",
                "issueIdOrKey": mode_info["issue_key"],
                "contentFormat": "adf",
                "fields": "<edit_fields>",
            },
            "addCommentToJiraIssue": (
                {
                    "cloudId": "novopay.atlassian.net",
                    "issueIdOrKey": mode_info["issue_key"],
                    "contentFormat": "adf",
                    "commentBody": "<comment_adf json string>",
                }
                if comment_adf and not comment_id
                else None
            ),
            "editComment": (
                {
                    "cloudId": "novopay.atlassian.net",
                    "issueIdOrKey": mode_info["issue_key"],
                    "commentId": comment_id,
                    "contentFormat": "adf",
                    "commentBody": "<comment_adf json string>",
                }
                if comment_adf and comment_id
                else None
            ),
        },
    }


# Forbidden tokens for JIRA-visible text (RCA / Impact / Dev / comments).
# Keep in sync with .cursor/skills/jira-fix-update/SKILL.md pre-flight scan.
_FORBIDDEN_RE = re.compile(
    r"(?i)("
    r"mfi_integration|mfi_release|feature/"
    r"|ntest\b|registry\.json|registry case"
    r"|\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,40}\b"  # commit SHA — hex with ≥1 letter (not pure digit LANs)
    r"|Processor\b|DAOService|\bapiName\b"
    r"|N\s*=\s*1\s*\.\.\s*20|member counts?\s+1\s*[–-]\s*20|1\s*[–-]\s*20\s*\("
    r"|\be2e\b|\bunit test\b|\bfixture\b|poisoned rows"
    r"|\b3\.\d+\.\d+(?:\.\d+)?\b"  # version like 3.4.2.2 / 3.7.1
    r"|loan_due_details|loan_installment_details|\bis_deleted\b|paid_amount|waived_amount"
    r"|RSCH_[A-Z_]+|\b134\d{3}\b"
    # Brand "Cursor" / "Cursor IDE" only (capital C) — do not ban verb "cursor"
    r"|(?-i:\bCursor(?:\s+IDE)?\b)"
    r")"
)


def scan_forbidden(text: str) -> list[str]:
    """Return list of forbidden token matches. Empty = clean."""
    return [m.group(0) for m in _FORBIDDEN_RE.finditer(text or "")]


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: jira-fix-adf.py <rca|impact|dev|scenario_titles|test_result|"
            "prepost|micro|owners|owners_tdpqa|project_mode|handoff_comment|"
            "pack|comment|aitdp_remarks|scan|assignee> ...",
            file=sys.stderr,
        )
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "rca" and len(sys.argv) == 5:
        print(json.dumps(rca_doc(sys.argv[2], sys.argv[3], sys.argv[4])))
    elif cmd == "impact":
        bullets = sys.argv[2:]
        if not bullets:
            print("Usage: jira-fix-adf.py impact <bullet> ...", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(impact_doc(bullets)))
    elif cmd == "dev":
        scenarios = sys.argv[2:]
        if not scenarios:
            print("Usage: jira-fix-adf.py dev <scenario> ...", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(dev_scenarios_doc(scenarios)))
    elif cmd == "scenario_titles":
        titles = sys.argv[2:]
        print(json.dumps(dev_scenarios_doc(titles)))
    elif cmd == "test_result":
        text = sys.argv[2] if len(sys.argv) > 2 else "All dev scenarios: Pass."
        print(json.dumps(doc(paragraph(text))))
    elif cmd == "aitdp_remarks":
        text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(json.dumps(doc(paragraph(text))))
    elif cmd == "prepost":
        pre = sys.argv[2] if len(sys.argv) > 2 else "NA"
        post = sys.argv[3] if len(sys.argv) > 3 else "NA"
        print(json.dumps(pre_post_doc(pre, post)))
    elif cmd == "micro":
        keys = sys.argv[2:]
        ids = [MICRO[k] for k in keys]
        print(json.dumps(micro_service_field(ids)))
    elif cmd == "owners":
        print(json.dumps(load_default_owners(), indent=2))
    elif cmd == "owners_tdpqa":
        print(json.dumps(load_tdpqa_owners(), indent=2))
    elif cmd == "project_mode":
        key = sys.argv[2] if len(sys.argv) > 2 else ""
        if not key:
            print("Usage: jira-fix-adf.py project_mode <ISSUE-KEY>", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(project_mode(key), indent=2))
    elif cmd in ("handoff_comment", "pack"):
        if cmd == "pack":
            if len(sys.argv) < 3:
                print("Usage: jira-fix-adf.py pack <ISSUE-KEY> [payload.json]", file=sys.stderr)
                sys.exit(1)
            issue_key = sys.argv[2]
            if len(sys.argv) > 3:
                raw = Path(sys.argv[3]).read_text()
            else:
                raw = sys.stdin.read()
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError as e:
                print(f"pack expects JSON payload: {e}", file=sys.stderr)
                sys.exit(1)
            try:
                print(json.dumps(build_handoff_pack(issue_key, payload), indent=2))
            except ValueError as e:
                print(str(e), file=sys.stderr)
                sys.exit(2)
            return
        raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"handoff_comment expects JSON payload: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            require_aitdp_in_handoff(payload)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
        hits = scan_forbidden(flatten_handoff_text(payload))
        if hits:
            print("FORBIDDEN in handoff_comment:", ", ".join(hits), file=sys.stderr)
            sys.exit(2)
        try:
            print(json.dumps(handoff_comment_doc(payload)))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
    elif cmd == "assignee":
        # Default fixer — Darpan Solanki (mentions.json)
        print(json.dumps({"accountId": "5e9d51241067100c195f7b12"}))
    elif cmd == "scan":
        raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        hits = scan_forbidden(raw)
        if hits:
            print("FORBIDDEN:", ", ".join(hits), file=sys.stderr)
            sys.exit(2)
        print("OK")
    elif cmd == "comment":
        raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        hits = scan_forbidden(raw)
        if hits:
            print("FORBIDDEN in comment:", ", ".join(hits), file=sys.stderr)
            sys.exit(2)
        print(json.dumps(comment_doc(raw)))
    else:
        print("See .cursor/skills/jira-fix-update/SKILL.md", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
