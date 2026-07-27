#!/usr/bin/env python3
"""
build_kafka.py — topic nodes + emits/consumes edges (Upgrade 10).

Sources (all extractor-based):
  1. deploy/**/messagebroker/MessageBroker.xml  — <topicPrefix>, consumer <bean>
  2. Java string literals: pushDataToKafkaQueue(..., "topic"), @KafkaListener(topics=...)
  3. .cursor/event-registry.md / cursor-bundle/brain/**/event-registry.md — ### `topic` headings

Usage: build_kafka.py <accumulated_raw.jsonl> <repoDir> [...]
"""
import os, re, sys, json, glob

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

def repo_name(p):
    for seg in os.path.abspath(p).split(os.sep):
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return os.path.basename(p.rstrip(os.sep))

KNOWN_PROC = set()
KNOWN_SVC = set()

def load_known(tmp):
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") != "node":
            continue
        if o.get("kind") == "processor":
            KNOWN_PROC.add(o["id"][len("processor:"):])
        elif o.get("kind") == "service":
            KNOWN_SVC.add(o["id"])

TOPIC_PREFIX_RE = re.compile(r'<topicPrefix>\s*([^<\s]+)\s*</topicPrefix>', re.I)
BEAN_RE = re.compile(r'<bean>\s*([^<\s]+)\s*</bean>', re.I)
PUSH_RE = re.compile(r'pushDataToKafkaQueue\s*\(\s*[^,]+,\s*"([^"]+)"')
KAFKA_LISTENER_RE = re.compile(
    r'@KafkaListener\s*\([^)]*topics\s*=\s*(?:\{([^}]+)\}|"([^"]+)")',
    re.S,
)
REGISTRY_H_RE = re.compile(r'^###\s+`([a-zA-Z0-9_]+)`\s*$', re.M)

def topic_id(prefix: str) -> str:
    p = prefix.rstrip("_")
    return f"topic:{p}"

def main():
    tmp = sys.argv[1]
    repos = sys.argv[2:]
    load_known(tmp)
    seen_topics = set()
    edges = set()

    def ensure_topic(prefix, repo, src, note=""):
        tid = topic_id(prefix)
        if tid not in seen_topics:
            seen_topics.add(tid)
            emit({
                "t": "node", "id": tid, "kind": "topic", "label": prefix.rstrip("_"),
                "repo": repo, "src": src, "note": note or "kafka_topic_prefix",
            })
        return tid

    # MessageBroker.xml
    for repo_dir in repos:
        repo = repo_name(repo_dir)
        for xml in glob.glob(os.path.join(repo_dir, "**", "MessageBroker.xml"), recursive=True):
            if "/build/" in xml:
                continue
            try:
                txt = open(xml, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            rel = os.path.relpath(xml, start=os.getcwd())
            # split consumers roughly by <Consumer> blocks
            for block in re.split(r'<Consumer>', txt, flags=re.I)[1:]:
                tp = TOPIC_PREFIX_RE.search(block)
                bean = BEAN_RE.search(block)
                if not tp:
                    continue
                prefix = tp.group(1).strip()
                tid = ensure_topic(prefix, repo, f"{rel}", "MessageBroker.xml")
                svc = f"service:{repo}"
                if svc in KNOWN_SVC or True:
                    key = (svc, "consumes", tid)
                    if key not in edges:
                        edges.add(key)
                        emit({"t": "edge", "from": svc, "to": tid, "rel": "consumes",
                              "note": bean.group(1).strip() if bean else "", "src": rel})
                if bean:
                    b = bean.group(1).strip()
                    if b.lower() in ("beanname", "bean"):
                        continue
                    # Emit consumer bean as a first-class node (T5)
                    cid = f"consumer:{b}"
                    emit({
                        "t": "node", "id": cid, "kind": "consumer", "label": b,
                        "repo": repo, "src": rel, "note": "MessageBroker.xml bean",
                    })
                    emit({"t": "edge", "from": cid, "to": tid, "rel": "consumes", "src": rel})
                    emit({"t": "edge", "from": f"service:{repo}", "to": cid, "rel": "owns",
                          "src": rel, "note": "kafka_consumer"})
                    # bean often camelCase consumer class name without Processor suffix
                    cand = b[0].lower() + b[1:] if b and b[0].isupper() else b
                    for name in (b, cand, b + "Processor", cand):
                        if name in KNOWN_PROC:
                            key = (f"processor:{name}", "consumes", tid)
                            if key not in edges:
                                edges.add(key)
                                emit({"t": "edge", "from": f"processor:{name}", "to": tid,
                                      "rel": "consumes", "src": rel})
                            break

    # Java producers / listeners
    for repo_dir in repos:
        repo = repo_name(repo_dir)
        for jf in glob.glob(os.path.join(repo_dir, "src", "main", "java", "**", "*.java"), recursive=True):
            try:
                txt = open(jf, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "Kafka" not in txt and "pushDataToKafkaQueue" not in txt and "topicPrefix" not in txt:
                continue
            rel = os.path.relpath(jf, start=os.getcwd())
            for m in PUSH_RE.finditer(txt):
                prefix = m.group(1)
                tid = ensure_topic(prefix, repo, f"{rel}", "pushDataToKafkaQueue")
                # best-effort: enclosing class → bean
                cm = re.search(r'\b(?:public\s+)?class\s+(\w+)', txt)
                bean = None
                if cm:
                    cls = cm.group(1)
                    bean = cls[0].lower() + cls[1:] if cls[0].isupper() else cls
                src_id = f"processor:{bean}" if bean and bean in KNOWN_PROC else f"service:{repo}"
                key = (src_id, "emits", tid)
                if key not in edges:
                    edges.add(key)
                    emit({"t": "edge", "from": src_id, "to": tid, "rel": "emits", "src": rel})
            for m in KAFKA_LISTENER_RE.finditer(txt):
                raw = m.group(1) or m.group(2) or ""
                for part in re.findall(r'"([^"]+)"', raw) or ([raw] if raw and '"' not in raw else []):
                    tid = ensure_topic(part, repo, f"{rel}", "@KafkaListener")
                    key = (f"service:{repo}", "consumes", tid)
                    if key not in edges:
                        edges.add(key)
                        emit({"t": "edge", "from": f"service:{repo}", "to": tid,
                              "rel": "consumes", "src": rel})

    # event-registry markdown
    roots = [
        os.path.join(os.getcwd(), ".cursor", "event-registry.md"),
        os.path.join(os.getcwd(), "cursor-bundle", "brain", "platform", "event-registry.md"),
    ]
    for path in roots:
        if not os.path.isfile(path):
            continue
        txt = open(path, encoding="utf-8", errors="replace").read()
        rel = os.path.relpath(path, start=os.getcwd())
        for m in REGISTRY_H_RE.finditer(txt):
            prefix = m.group(1)
            ensure_topic(prefix, None, f"{rel}", "event-registry")

if __name__ == "__main__":
    main()
