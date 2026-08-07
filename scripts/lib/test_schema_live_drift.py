"""Column-binding false positives found by audit, and the regression the gate must still catch.

`schema_live_drift.py` is fed by `column_binding.py`'s Java parser. An audit found three
parser defects that turned real, already-present columns into reported drift: multi-line
`@Column`/`@JoinColumn` annotations fall back to the raw field name; Postgres folds unquoted
mixed-case identifiers to lowercase at DDL time but the parser kept the annotation's literal
case; and fields declared inside a nested enum/class were attributed to the outer entity's
table. Each class has its own test below, pinned to the real cases the audit named.

The last test is the other direction: a synthetic entity/table pair with a column that is
genuinely absent must still be reported. A false-positive fix that also silences true drift
is a worse outcome than the noise it was meant to remove.

    python3 scripts/lib/test_schema_live_drift.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import column_binding  # noqa: E402
import schema_live_drift  # noqa: E402


def parse(java_source: str) -> list[dict]:
    with tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "lib") as tmp:
        path = pathlib.Path(tmp) / "SyntheticEntity.java"
        path.write_text(java_source, encoding="utf-8")
        return column_binding.parse_entities([path], "mfi_synthetic", "trustt-platform-synthetic")


def columns(rows: list[dict]) -> dict[str, str]:
    return {r["field"]: r["column"] for r in rows}


class MultiLineColumnTest(unittest.TestCase):

    def test_column_name_split_across_two_lines(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "address")
            public class AddressEntity {
                @Column(
                    name = "address_line_1")
                private String address1;
            }
            """
        )
        self.assertEqual(columns(rows)["address1"], "address_line_1")

    def test_join_column_split_across_two_lines(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "corporate__sub_client_mapping")
            public class CorporateSubclientcodeMappingEntity {
                @OneToOne(
                    fetch = FetchType.LAZY)
                @JoinColumn(
                    name = "sub_client_code_id")
                private SubclientcodeDetailsEntity subClientCodeDetails;
            }
            """
        )
        self.assertEqual(columns(rows)["subClientCodeDetails"], "sub_client_code_id")

    def test_column_annotation_split_across_three_lines_with_extra_attribute(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "key_store")
            public class KeyEntity {
                @Column(
                    name = "purpose",
                    unique = true)
                private String purpose;
            }
            """
        )
        self.assertEqual(columns(rows)["purpose"], "purpose")

    def test_single_line_column_still_works(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "trial_balance")
            public class TrialBalanceEntity {
                @Column(name = "gl_code")
                private String glCode;
            }
            """
        )
        self.assertEqual(columns(rows)["glCode"], "gl_code")


class PostgresIdentifierFoldTest(unittest.TestCase):

    def test_unquoted_mixed_case_column_folds_to_lowercase(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "alm_active_loan_staging_table")
            public class AlmActiveLoanStagingTableEntity {
                @Column(name="ub_Cr")
                private BigDecimal ubCr;
            }
            """
        )
        self.assertEqual(columns(rows)["ubCr"], "ub_cr")

    def test_unquoted_mixed_case_column_folds_regardless_of_spacing(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "csc_vle_staging_info")
            public class CscVleStagingEntity {
                @Column(name = "bet_Counter")
                private String betCounter;
            }
            """
        )
        self.assertEqual(columns(rows)["betCounter"], "bet_counter")


class NestedTypeFieldTest(unittest.TestCase):

    def test_enum_constant_field_not_attributed_to_outer_table(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "loan_account_events_queue")
            public class LoanAccountEventsQueueEntity {
                public enum EventType {
                    CLB("Child Loan Booking"),
                    FCL("Foreclosure");

                    private final String description;
                    EventType(String description) {
                        this.description = description;
                    }
                }

                @Column(name = "event_type")
                private String eventType;
            }
            """
        )
        bound = columns(rows)
        self.assertNotIn("description", bound)
        self.assertEqual(bound["eventType"], "event_type")

    def test_field_after_nested_enum_still_parsed(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "loan_account_events_queue")
            public class LoanAccountEventsQueueEntity {
                public enum EventStatus {
                    P("PENDING"),
                    C("COMPLETED");

                    private final String description;
                    EventStatus(String description) {
                        this.description = description;
                    }
                }

                @Column(name = "parent_account_id")
                private Long parentAccountId;
            }
            """
        )
        self.assertEqual(columns(rows)["parentAccountId"], "parent_account_id")

    def test_two_nested_enums_then_real_columns(self) -> None:
        rows = parse(
            """
            @Entity
            @Table(name = "loan_account_events_queue")
            public class LoanAccountEventsQueueEntity {
                public enum EventType {
                    CLB("Child Loan Booking");
                    private final String description;
                    EventType(String description) { this.description = description; }
                }

                public enum EventStatus {
                    P("PENDING");
                    private final String description;
                    EventStatus(String description) { this.description = description; }
                }

                @Column(name = "data")
                private String data;
                @Column(name = "event_id")
                private Long eventId;
            }
            """
        )
        bound = columns(rows)
        self.assertNotIn("description", bound)
        self.assertEqual(bound["data"], "data")
        self.assertEqual(bound["eventId"], "event_id")


class TruePositiveRegressionTest(unittest.TestCase):
    """A genuinely absent column must still be reported after the false-positive fixes.

    Mirrors the shape of the historical si_presentation_loan_account_details.external_call_status
    case (Flyway V000200, applied since) without relying on that row still being absent locally.
    """

    def test_genuinely_missing_column_is_reported(self) -> None:
        bindings = [
            {
                "schema": "mfi_accounting",
                "table": "synthetic_regression_table",
                "column": "genuinely_missing_column",
                "entity": "SyntheticRegressionEntity",
                "repo": "trustt-platform-accounting",
                "source": "synthetic",
                "java_type": "String",
                "field": "genuinelyMissingColumn",
            }
        ]
        live = {("mfi_accounting", "synthetic_regression_table"): {"id", "other_column"}}
        drift = schema_live_drift.compute_drift(bindings, live, None)
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["column"], "genuinely_missing_column")

    def test_present_column_is_not_reported(self) -> None:
        bindings = [
            {
                "schema": "mfi_accounting",
                "table": "synthetic_regression_table",
                "column": "id",
                "entity": "SyntheticRegressionEntity",
                "repo": "trustt-platform-accounting",
                "source": "synthetic",
                "java_type": "Long",
                "field": "id",
            }
        ]
        live = {("mfi_accounting", "synthetic_regression_table"): {"id", "other_column"}}
        drift = schema_live_drift.compute_drift(bindings, live, None)
        self.assertEqual(drift, [])

    def test_transient_field_not_reported_even_if_absent(self) -> None:
        bindings = [
            {
                "schema": "mfi_accounting",
                "table": "synthetic_regression_table",
                "column": "computed_only",
                "entity": "SyntheticRegressionEntity",
                "repo": "trustt-platform-accounting",
                "source": "synthetic",
                "java_type": "transient String",
                "field": "computedOnly",
            }
        ]
        live = {("mfi_accounting", "synthetic_regression_table"): {"id"}}
        drift = schema_live_drift.compute_drift(bindings, live, None)
        self.assertEqual(drift, [])


if __name__ == "__main__":
    unittest.main()
