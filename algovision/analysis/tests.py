import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import AnonymousUser, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from analysis.models import Algorithm, File, FileType

from analysis.tasks import resolve_algorithm_script
from analysis.views import MediaForwardAuthView, _media_rel_path_from_forwarded_uri


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


class MediaForwardAuthTests(SimpleTestCase):
    """RequestFactory + in-memory User instances (no DB)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = MediaForwardAuthView.as_view()
        self.user_a = User(pk=10, username="ua")
        self.user_b = User(pk=20, username="ub")
        self.staff = User(pk=30, username="st", is_staff=True)

    def _get(self, forwarded_uri: str, user):
        req = self.factory.get(
            "/_caddy/media-auth",
            HTTP_X_FORWARDED_URI=forwarded_uri,
        )
        req.user = user
        return self.view(req)

    def test_rel_path_strips_media_prefix(self):
        self.assertEqual(
            _media_rel_path_from_forwarded_uri("/media/uploads/1/x.png"),
            "uploads/1/x.png",
        )

    def test_rel_path_rejects_dotdot(self):
        self.assertIsNone(
            _media_rel_path_from_forwarded_uri("/media/uploads/1/../2/x.png")
        )

    def test_anonymous_uploads_forbidden(self):
        r = self._get("/media/uploads/1/x.png", AnonymousUser())
        self.assertEqual(r.status_code, 403)

    def test_user_cannot_read_other_uploads(self):
        r = self._get(
            f"/media/uploads/{self.user_b.pk}/x.png",
            self.user_a,
        )
        self.assertEqual(r.status_code, 403)

    def test_user_can_read_own_uploads(self):
        r = self._get(
            f"/media/uploads/{self.user_a.pk}/x.png",
            self.user_a,
        )
        self.assertEqual(r.status_code, 200)

    def test_user_can_read_own_outputs(self):
        r = self._get(
            f"/media/outputs/{self.user_a.pk}/out.zip",
            self.user_a,
        )
        self.assertEqual(r.status_code, 200)

    def test_staff_can_read_any_uploads(self):
        r = self._get(
            f"/media/uploads/{self.user_b.pk}/x.png",
            self.staff,
        )
        self.assertEqual(r.status_code, 200)

    def test_extract_path_forbidden_even_staff(self):
        r = self._get(
            "/media/algorithms/pkg/3/extract/main.py",
            self.staff,
        )
        self.assertEqual(r.status_code, 403)

    def test_envs_forbidden(self):
        r = self._get("/media/envs/foo", self.staff)
        self.assertEqual(r.status_code, 403)

    def test_dotdot_forbidden(self):
        r = self._get(
            f"/media/uploads/{self.user_a.pk}/../{self.user_b.pk}/x.png",
            self.user_a,
        )
        self.assertEqual(r.status_code, 403)

    def test_algo_zip_staff_ok(self):
        r = self._get("/media/algorithms/pkg/5/archive.zip", self.staff)
        self.assertEqual(r.status_code, 200)

    def test_algo_zip_non_staff_forbidden(self):
        r = self._get("/media/algorithms/pkg/5/archive.zip", self.user_a)
        self.assertEqual(r.status_code, 403)

    def test_unknown_path_forbidden(self):
        r = self._get("/media/secrets.txt", self.user_a)
        self.assertEqual(r.status_code, 403)

    def test_forwarded_uri_without_media_prefix(self):
        r = self._get(f"/uploads/{self.user_a.pk}/x.png", self.user_a)
        self.assertEqual(r.status_code, 200)


class FileOwnershipAccessTests(TestCase):
    """File delete and analysis must not access other users' rows (IDOR)."""

    def test_cannot_delete_another_users_file(self):
        media = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(media, ignore_errors=True))
        with self.settings(MEDIA_ROOT=media):
            ua = User.objects.create_user("idor_del_a", "idor_del_a@test.com", "pw")
            ub = User.objects.create_user("idor_del_b", "idor_del_b@test.com", "pw")
            ft = FileType.objects.create(code="idor_del_csv", name="CSV")
            f_b = File.objects.create(
                user=ub,
                file=SimpleUploadedFile("b.txt", b"x"),
                type=ft,
                upload_date=timezone.now(),
            )
            self.client.force_login(ua)
            r = self.client.post(
                reverse("file_manager"),
                {"delete_file": str(f_b.pk)},
            )
            self.assertEqual(r.status_code, 404)
            self.assertTrue(File.objects.filter(pk=f_b.pk).exists())

    def test_cannot_run_analysis_on_another_users_file(self):
        media = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(media, ignore_errors=True))
        with self.settings(MEDIA_ROOT=media):
            ua = User.objects.create_user("idor_an_a", "idor_an_a@test.com", "pw")
            ub = User.objects.create_user("idor_an_b", "idor_an_b@test.com", "pw")
            ft = FileType.objects.create(code="idor_an_csv", name="CSV")
            f_b = File.objects.create(
                user=ub,
                file=SimpleUploadedFile("b.txt", b"y"),
                type=ft,
                upload_date=timezone.now(),
            )
            algo = Algorithm.objects.create(
                name="idor_algo",
                project=None,
                version="1",
                description="t",
            )
            algo.supported_types.add(ft)
            self.client.force_login(ua)
            r = self.client.post(
                reverse("analysis"),
                {
                    "file_id": str(f_b.pk),
                    "algorithm": str(algo.pk),
                },
            )
            self.assertEqual(r.status_code, 404)
