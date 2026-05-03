import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from analysis.tasks import resolve_algorithm_script


class ResolveAlgorithmScriptTests(SimpleTestCase):
    def test_finds_main_at_root(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "main.py").write_text("print(1)", encoding="utf-8")
            got = resolve_algorithm_script(base, "main.py")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got, (base / "main.py").resolve())

    def test_nested_single_directory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            inner = base / "proj"
            inner.mkdir()
            (inner / "main.py").write_text("print(1)", encoding="utf-8")
            got = resolve_algorithm_script(base, "main.py")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got, (inner / "main.py").resolve())

    def test_strips_redundant_prefix_matching_base_name(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "myalgo"
            base.mkdir()
            (base / "main.py").write_text("print(1)", encoding="utf-8")
            got = resolve_algorithm_script(base, "myalgo/main.py")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got, (base / "main.py").resolve())

    def test_ambiguous_multiple_main_logs_and_picks_shortest(self):
        # Two nested main.py files; entrypoint "main.py" does not match a unique relative path.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name in ("pkg_a", "pkg_b"):
                d = base / name
                d.mkdir()
                (d / "main.py").write_text("x", encoding="utf-8")
            with self.assertLogs("analysis.tasks", level="WARNING") as cm:
                got = resolve_algorithm_script(base, "main.py")
            self.assertTrue(any("varios candidatos" in x for x in cm.output))
            self.assertIsNotNone(got)
            assert got is not None
            candidates = {(base / "pkg_a" / "main.py").resolve(), (base / "pkg_b" / "main.py").resolve()}
            self.assertIn(got, candidates)

    def test_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertIsNone(resolve_algorithm_script(base, "main.py"))
