import datetime as dt
import tempfile
import unittest
from pathlib import Path

from tools import dependency_audit


ROOT = Path(__file__).resolve().parents[1]


class DependencyAuditTests(unittest.TestCase):
    def test_repository_pins_are_discovered(self):
        checks = {check.name: check for check in dependency_audit.build_checks(ROOT)}

        self.assertEqual(checks["AWS CLI"].current, "2.35.23")
        self.assertEqual(checks["Trivy"].current, "0.70.0")
        self.assertEqual(checks["actionlint"].current, "1.7.12")
        self.assertEqual(checks["Checkov"].current, "3.3.8")
        self.assertEqual(checks["pre-commit"].current, "4.6.0")

    def test_all_source_types_resolve_versions(self):
        responses = {
            "https://api.github.com/repos/example/release/releases/latest": {
                "tag_name": "v2.1.0"
            },
            "https://api.github.com/repos/example/tags/tags?per_page=100": [
                {"name": "3.2.1rc1"},
                {"name": "3.2.0"},
                {"name": "3.10.1"},
            ],
            "https://pypi.org/pypi/example/json": {"info": {"version": "4.0.0"}},
        }

        self.assertEqual(
            dependency_audit.resolve_latest(
                "github-release:example/release", responses.__getitem__
            ),
            "2.1.0",
        )
        self.assertEqual(
            dependency_audit.resolve_latest(
                "github-tag:example/tags", responses.__getitem__
            ),
            "3.10.1",
        )
        self.assertEqual(
            dependency_audit.resolve_latest("pypi:example", responses.__getitem__),
            "4.0.0",
        )

    def test_audit_reports_updates_and_source_errors(self):
        checks = [
            dependency_audit.Check(
                "Current", "1.0.0", "pypi:current", "https://example/current"
            ),
            dependency_audit.Check(
                "Old", "1.0.0", "pypi:old", "https://example/old"
            ),
            dependency_audit.Check(
                "Broken", "1.0.0", "pypi:broken", "https://example/broken"
            ),
        ]

        def fetcher(url):
            if url.endswith("/broken/json"):
                raise OSError("offline")
            version = "2.0.0" if url.endswith("/old/json") else "1.0.0"
            return {"info": {"version": version}}

        results, errors = dependency_audit.audit(checks, fetcher)

        self.assertFalse(results[0].update_available)
        self.assertTrue(results[1].update_available)
        self.assertEqual(errors, ["Broken: offline"])

    def test_snapshot_becomes_stale_after_fourteen_days(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Dockerfile").write_text(
                "ARG UBUNTU_SNAPSHOT=20260101T000000Z\n"
            )
            current = dependency_audit.snapshot_result(
                root,
                dt.datetime(2026, 1, 15, tzinfo=dt.timezone.utc),
            )
            stale = dependency_audit.snapshot_result(
                root,
                dt.datetime(2026, 1, 15, 0, 0, 1, tzinfo=dt.timezone.utc),
            )

        self.assertFalse(current.update_available)
        self.assertTrue(stale.update_available)

    def test_report_includes_evidence_and_next_step(self):
        results = [
            dependency_audit.Result(
                "Example",
                "1.0.0",
                "2.0.0",
                "https://example/releases",
            )
        ]
        report = dependency_audit.render_report(
            results,
            [],
            dt.datetime(2026, 7, 16, tzinfo=dt.timezone.utc),
        )

        self.assertIn("`1.0.0`", report)
        self.assertIn("`2.0.0`", report)
        self.assertIn("[upstream](https://example/releases)", report)
        self.assertIn("full native image test and scan", report)


if __name__ == "__main__":
    unittest.main()
