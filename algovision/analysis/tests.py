import json
import shutil
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from analysis.models import Algorithm, Execution, File, FileType, Output, Project

from analysis.tasks import ejecutar_algoritmo_task, resolve_algorithm_script
from analysis.views import MediaForwardAuthView, _media_rel_path_from_forwarded_uri


# Minimal valid 1×1 PNG (libmagic identifies as image/png when complete).
_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _libmagic_available() -> bool:
    try:
        import magic

        return magic.from_buffer(_MINI_PNG, mime=True) == "image/png"
    except Exception:
        return False


class EjecutarAlgoritmoTaskIdempotencyTests(TestCase):
    """Redelivered tasks must not duplicate Output rows after FINISHED."""

    def test_skips_when_already_finished_with_output(self):
        user = User.objects.create_user("idem", "idem@test.com", "pw")
        ft, _ = FileType.objects.get_or_create(code="csv", defaults={"name": "CSV"})
        project, _ = Project.objects.get_or_create(
            title="stats-analysis",
            defaults={
                "description": "test",
                "start_date": timezone.now().date(),
            },
        )
        algo = Algorithm.objects.create(
            name="CSV simple",
            project=project,
            version="1.0",
            description="test",
            entrypoint="main.py",
        )
        algo.supported_types.add(ft)
        execution = Execution.objects.create(
            user=user,
            algorithm=algo,
            file=None,
            execution_date=timezone.now(),
            status="FINISHED",
            snapshot_file_name="sample.csv",
            snapshot_alg_name="CSV simple",
        )
        Output.objects.create(
            execution=execution,
            file="outputs/1/sample_out.zip",
            output_date=timezone.now(),
        )
        before = Output.objects.filter(execution=execution).count()
        ejecutar_algoritmo_task(0, algo.pk, execution.pk)
        self.assertEqual(Output.objects.filter(execution=execution).count(), before)
        self.assertEqual(execution.status, "FINISHED")

    def test_task_uses_late_ack(self):
        self.assertTrue(ejecutar_algoritmo_task.acks_late)
        self.assertTrue(getattr(ejecutar_algoritmo_task, "reject_on_worker_lost", False))


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


class RequirementsEndpointsAuthTests(TestCase):
    """requirements/download and /upload must be superuser-only (not public)."""

    def setUp(self):
        req_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(req_root, ignore_errors=True))
        self._requirements_path = req_root / "envs" / "requirements_global.txt"
        self._requirements_path.parent.mkdir(parents=True, exist_ok=True)
        self._requirements_path.write_text("pkg==1.0\n", encoding="utf-8")
        patcher = patch("analysis.views.REQUIREMENTS_PATH", self._requirements_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_download_anonymous_redirects(self):
        r = self.client.get(reverse("download_requirements"))
        self.assertRedirects(
            r,
            reverse("index"),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=False,
        )

    def test_download_staff_forbidden(self):
        u = User.objects.create_user(
            "req_dl_staff", "req_dl_staff@test.com", "pw", is_staff=True
        )
        self.client.force_login(u)
        r = self.client.get(reverse("download_requirements"))
        self.assertEqual(r.status_code, 403)

    def test_download_superuser_ok(self):
        u = User.objects.create_superuser("req_dl_su", "req_dl_su@test.com", "pw")
        self.client.force_login(u)
        r = self.client.get(reverse("download_requirements"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"pkg==1.0", r.content)

    @patch("analysis.views.install_requirements_task.delay")
    def test_upload_anonymous_redirects(self, mock_delay):
        r = self.client.post(
            reverse("upload_requirements"),
            {"requirements_file": SimpleUploadedFile("req.txt", b"evil")},
        )
        self.assertRedirects(
            r,
            reverse("index"),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=False,
        )
        mock_delay.assert_not_called()

    @patch("analysis.views.install_requirements_task.delay")
    def test_upload_staff_forbidden(self, mock_delay):
        u = User.objects.create_user(
            "req_ul_staff", "req_ul_staff@test.com", "pw", is_staff=True
        )
        self.client.force_login(u)
        r = self.client.post(
            reverse("upload_requirements"),
            {"requirements_file": SimpleUploadedFile("req.txt", b"x")},
        )
        self.assertEqual(r.status_code, 403)
        mock_delay.assert_not_called()

    @patch("analysis.views.install_requirements_task.delay")
    def test_upload_superuser_ok(self, mock_delay):
        u = User.objects.create_superuser("req_ul_su", "req_ul_su@test.com", "pw")
        self.client.force_login(u)
        r = self.client.post(
            reverse("upload_requirements"),
            {"requirements_file": SimpleUploadedFile("req.txt", b"foo==2\n")},
        )
        self.assertEqual(r.status_code, 200)
        mock_delay.assert_called_once()
        self.assertEqual(self._requirements_path.read_text(), "foo==2\n")


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


class RenameFileCsrfTests(TestCase):
    """POST /files/rename/<id>/ must validate CSRF (not csrf_exempt)."""

    def test_post_without_csrf_token_returns_403(self):
        client = Client(enforce_csrf_checks=True)
        u = User.objects.create_user("rename_csrf_u", "rename_csrf_u@test.com", "pw")
        client.force_login(u)
        r = client.post(
            reverse("rename_file", kwargs={"file_id": 1}),
            data=json.dumps({"new_name": "x.txt"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)

    def test_post_with_csrf_header_renames_file(self):
        media = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(media, ignore_errors=True))
        client = Client(enforce_csrf_checks=True)
        u = User.objects.create_user("rename_ok_u", "rename_ok_u@test.com", "pw")
        ft = FileType.objects.create(code="rename_csrf_csv", name="CSV")
        with self.settings(MEDIA_ROOT=media):
            f = File.objects.create(
                user=u,
                file=SimpleUploadedFile("oldname.txt", b"content"),
                type=ft,
                upload_date=timezone.now(),
            )
            client.force_login(u)
            client.get(reverse("file_manager"))
            csrf = client.cookies["csrftoken"].value
            r = client.post(
                reverse("rename_file", kwargs={"file_id": f.pk}),
                data=json.dumps({"new_name": "newname.txt"}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf,
            )
        self.assertEqual(r.status_code, 200)
        payload = json.loads(r.content.decode())
        self.assertEqual(payload.get("new_name"), "newname")
        f.refresh_from_db()
        self.assertEqual(f.display_name, "newname.txt")
        self.assertIn("oldname.txt", f.file.name)


@skipUnless(_libmagic_available(), "requires python-magic and libmagic")
class FileUploadContentSniffTests(TestCase):
    """Uploads are validated by file content, not the browser Content-Type."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.media, ignore_errors=True))

    def test_rejects_non_image_bytes_with_spoofed_image_content_type(self):
        FileType.objects.get_or_create(code="image", defaults={"name": "Imagen"})
        u = User.objects.create_user("up_spoof", "up_spoof@test.com", "pw")
        before = File.objects.count()
        body = b"<html><body>alert(1)</body></html>"
        forged = SimpleUploadedFile(
            "innocent.png",
            body,
            content_type="image/png",
        )
        with self.settings(MEDIA_ROOT=self.media):
            self.client.force_login(u)
            self.client.get(reverse("file_manager"))
            csrf = self.client.cookies["csrftoken"].value
            r = self.client.post(
                reverse("file_manager"),
                {"csrfmiddlewaretoken": csrf, "files": forged},
            )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(File.objects.count(), before)

    def test_accepts_png_by_magic_even_if_content_type_is_wrong(self):
        FileType.objects.get_or_create(code="image", defaults={"name": "Imagen"})
        u = User.objects.create_user("up_ok", "up_ok@test.com", "pw")
        honest = SimpleUploadedFile(
            "data.bin",
            _MINI_PNG,
            content_type="application/octet-stream",
        )
        with self.settings(MEDIA_ROOT=self.media):
            self.client.force_login(u)
            self.client.get(reverse("file_manager"))
            csrf = self.client.cookies["csrftoken"].value
            r = self.client.post(
                reverse("file_manager"),
                {"csrfmiddlewaretoken": csrf, "files": honest},
            )
        self.assertEqual(r.status_code, 302)
        f = File.objects.filter(user=u).order_by("-id").first()
        self.assertIsNotNone(f)
        assert f is not None
        self.assertEqual(f.type.code, "image")
        base = Path(self.media) / "uploads" / str(u.pk)
        stored = list(base.glob("*.png"))
        self.assertEqual(len(stored), 1)
        self.assertRegex(stored[0].name, r"^[0-9a-f]{32}\.png$")

