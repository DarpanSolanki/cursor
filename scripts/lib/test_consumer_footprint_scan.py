"""The consumer footprint scanner, pinned to the four ways it could over-attribute.

A missing consumer write is a gap you notice. A wrong one is a gap you trust — GAP-098
measured seven table-writes the KG answered with the wrong writer. Every test here is a
defect that would produce a confident wrong answer rather than a blank:

    a pattern-1 consumer emitted     doubles an edge the Request already carries correctly
    a shared bean counted per topic  credits one code path as twenty verified consumers
    a DAO resolved by frequency      turns a read (findOne) into a write
    a facade DAO resolved per class  pools four bureaus into whichever caller reached it

Fixtures are written to a temp tree rather than pinned to repo source, so a refactor in
LOS cannot make this suite lie about the scanner.

    python3 scripts/lib/test_consumer_footprint_scan.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

import consumer_footprint_scan as scan

ENTITY = """package t;
import jakarta.persistence.Table;
@Entity
@Table(name = "%s")
public class %s { }
"""

DAO = """package t;
import org.springframework.stereotype.Service;
@Service
public class %s {
    @Autowired
    private %sRepository repository;
    public void save(%s e) { repository.save(e); }
    public %s findOne(Long id) { return repository.findOne(id); }
}
"""


def write(root: pathlib.Path, name: str, body: str) -> None:
    path = root / f"{name}.java"
    path.write_text(body, encoding="utf-8")


def scan_tree(root: pathlib.Path, consumer: str) -> dict:
    tables = scan.table_map(root)
    daos = scan.dao_entities(root, tables)
    index = scan.class_index(root)
    walker = scan.Walker(root, index, tables, daos)
    events: list = []
    writes: dict = {}
    unresolved: list = []
    walker.walk(index[consumer], "computeRecords", 0, set(), events, writes, unresolved)
    return {
        "pattern": events[0]["kind"] if events else scan.PATTERN_NONE,
        "tables": sorted({t for t, r in writes if r == "writes"}),
        "unresolved": unresolved,
    }


class WalkTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        write(self.root, "FooEntity", ENTITY % ("foo", "FooEntity"))
        write(self.root, "BarEntity", ENTITY % ("bar", "BarEntity"))
        write(self.root, "FooDaoService", DAO % ("FooDaoService", "Foo", "FooEntity",
                                                 "FooEntity"))

    def test_orchestrated_consumer_is_classified_and_yields_no_edge(self) -> None:
        write(self.root, "OrchConsumer", """package t;
@Component("orchConsumer")
public class OrchConsumer {
    @Autowired
    private FooDaoService fooDaoService;
    public void computeRecords(ConsumerRecords records, PlatformTenant tenant) {
        getServiceOrchestrator().executeProcessors("createFoo", executionContext);
    }
}
""")
        got = scan_tree(self.root, "OrchConsumer")
        self.assertEqual(scan.PATTERN_ORCHESTRATED, got["pattern"])
        self.assertEqual([], got["tables"])

    def test_dao_direct_consumer_resolves_to_the_physical_table(self) -> None:
        write(self.root, "DaoConsumer", """package t;
@Component("daoConsumer")
public class DaoConsumer {
    @Autowired
    private FooDaoService fooDaoService;
    public void computeRecords(ConsumerRecords records, PlatformTenant tenant) {
        fooDaoService.save(new FooEntity());
    }
}
""")
        got = scan_tree(self.root, "DaoConsumer")
        self.assertEqual(scan.PATTERN_DAO, got["pattern"])
        self.assertEqual(["foo"], got["tables"])

    def test_a_read_on_the_same_dao_is_not_a_write(self) -> None:
        write(self.root, "ReadConsumer", """package t;
@Component("readConsumer")
public class ReadConsumer {
    @Autowired
    private FooDaoService fooDaoService;
    public void computeRecords(ConsumerRecords records, PlatformTenant tenant) {
        FooEntity e = fooDaoService.findOne(1L);
    }
}
""")
        got = scan_tree(self.root, "ReadConsumer")
        self.assertEqual(scan.PATTERN_NONE, got["pattern"])
        self.assertEqual([], got["tables"])

    def test_a_dao_naming_two_entities_is_left_unresolved_not_guessed(self) -> None:
        write(self.root, "MixedDaoService", """package t;
@Service
public class MixedDaoService {
    public void save(Object e) { }
    public FooEntity load() { return new FooEntity(); }
    public BarEntity loadBar() { return new BarEntity(); }
}
""")
        write(self.root, "MixedConsumer", """package t;
@Component("mixedConsumer")
public class MixedConsumer {
    @Autowired
    private MixedDaoService mixedDaoService;
    public void computeRecords(ConsumerRecords records, PlatformTenant tenant) {
        mixedDaoService.save(new FooEntity());
    }
}
""")
        tables = scan.table_map(self.root)
        daos = scan.dao_entities(self.root, tables)
        self.assertNotIn("MixedDaoService", daos)
        got = scan_tree(self.root, "MixedConsumer")
        self.assertEqual([], got["tables"])

    def test_processor_direct_consumer_reaches_the_processor_own_write(self) -> None:
        write(self.root, "FooProcessor", """package t;
@Processor
public class FooProcessor extends AbstractProcessor {
    @Autowired
    private FooDaoService fooDaoService;
    protected void process(ExecutionContext context) {
        fooDaoService.save(new FooEntity());
    }
}
""")
        write(self.root, "ProcConsumer", """package t;
@Component("procConsumer")
public class ProcConsumer {
    @Autowired
    private FooProcessor fooProcessor;
    public void computeRecords(ConsumerRecords records, PlatformTenant tenant) {
        fooProcessor.execute(executionContext);
    }
}
""")
        got = scan_tree(self.root, "ProcConsumer")
        self.assertEqual(scan.PATTERN_PROCESSOR, got["pattern"])
        self.assertEqual(["foo"], got["tables"])

    def test_a_facade_is_resolved_per_method_not_per_class(self) -> None:
        write(self.root, "FacadeService", """package t;
@Service
public class FacadeService {
    @Autowired
    private FooDaoService fooDaoService;
    @Autowired
    private BarDaoService barDaoService;
    public void processFoo(String v) { fooDaoService.save(new FooEntity()); }
    public void processBar(String v) { barDaoService.save(new BarEntity()); }
}
""")
        write(self.root, "BarDaoService", DAO % ("BarDaoService", "Bar", "BarEntity",
                                                 "BarEntity"))
        write(self.root, "FacadeConsumer", """package t;
@Component("facadeConsumer")
public class FacadeConsumer {
    @Autowired
    private FacadeService consumerService;
    public void computeRecords(ConsumerRecords records, PlatformTenant tenant) {
        consumerService.processFoo("x");
    }
}
""")
        got = scan_tree(self.root, "FacadeConsumer")
        self.assertEqual(["foo"], got["tables"])


class SharedBeanTest(unittest.TestCase):

    def test_many_topics_on_one_bean_collapse_to_one_scanned_consumer(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        xml = pathlib.Path(tmp.name) / "MessageBroker.xml"
        consumers = "".join(
            f"<Consumer><topicPrefix>bureau_{i}_</topicPrefix>"
            f"<consumersGroupIdPrefix>g_{i}_</consumersGroupIdPrefix>"
            "<bean>factivaConsumer</bean></Consumer>" for i in range(20))
        xml.write_text(f"<MessageBroker>{consumers}</MessageBroker>", encoding="utf-8")
        rows = scan.parse_consumers([xml])
        self.assertEqual(20, len(rows))
        self.assertEqual({"factivaConsumer"}, {r["bean"] for r in rows})


class CuratedTest(unittest.TestCase):

    def test_only_pattern_two_and_three_reach_the_overlay(self) -> None:
        rows = [
            {"bean": "orchConsumer", "pattern": scan.PATTERN_ORCHESTRATED,
             "class": "a.java", "tables_written": ["foo"], "tables_deleted": []},
            {"bean": "daoConsumer", "pattern": scan.PATTERN_DAO,
             "class": "b.java", "tables_written": ["bar"], "tables_deleted": []},
        ]
        lines, skipped = scan.curated_lines(rows)
        beans = {line.split('"from": "consumer:')[1].split('"')[0] for line in lines}
        self.assertNotIn("orchConsumer", beans)
        self.assertIn(("orchConsumer", scan.PATTERN_ORCHESTRATED), skipped)

    def test_one_edge_per_bean_and_table_however_many_topics(self) -> None:
        rows = [{"bean": "daoConsumer", "pattern": scan.PATTERN_DAO, "class": "b.java",
                 "tables_written": ["bar", "bar"], "tables_deleted": []}]
        lines, _ = scan.curated_lines(rows)
        self.assertEqual(len(lines), len(set(lines)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
