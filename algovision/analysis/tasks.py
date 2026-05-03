# analysis/tasks.py

from celery import shared_task  # type: ignore
import logging
import os
import shutil
import tempfile
import zipfile
import platform
import subprocess

from .algorithm_paths import algorithm_extract_disk_path
from .models import File, Algorithm, Execution, Output

from django.conf import settings
from django.utils import timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _wrap_single_image_input_as_dir(path_str: str, django_file: File) -> tuple[str, list[str]]:
    """Return a path suitable for argv and temp dirs to delete after the subprocess.

    TF Object Detection-style scripts often pass ``-i`` to ``os.listdir()`` (directory).
    Django supplies a single file path for image uploads — copy into a temp folder.

    Algorithms expecting ``(N,H,W,3)`` tensors mis-feed grayscale uploads unless we convert to RGB.
    """
    cleanup_dirs: list[str] = []
    p = Path(path_str)
    if not p.is_file():
        return path_str, cleanup_dirs
    try:
        code = django_file.type.code
    except Exception:
        return path_str, cleanup_dirs
    if code != "image":
        return path_str, cleanup_dirs
    td = tempfile.mkdtemp(prefix="algovision_img_input_")
    cleanup_dirs.append(td)
    dest = Path(td) / p.name
    try:
        from PIL import Image

        with Image.open(p) as im:
            im.convert("RGB").save(dest, format=None)
    except Exception:
        shutil.copy2(p, dest)
        logger.warning(
            "_wrap_single_image_input_as_dir: PIL failed, copied raw %s -> %s",
            path_str,
            dest,
            exc_info=True,
        )
    else:
        logger.info("_wrap_single_image_input_as_dir: %s -> %s/ (RGB)", path_str, td)
    return td, cleanup_dirs


def _algorithm_visible_children(base: Path) -> list[Path]:
    skip = frozenset({"__MACOSX", ".DS_Store"})
    return [p for p in base.iterdir() if p.name not in skip]


def resolve_algorithm_script(base: Path, entrypoint: str) -> Optional[Path]:
    """Locate entrypoint under extracted algorithm folder.

    Supports ZIPs that wrap files in a single top-level directory (common layout).
    """
    if not base.is_dir():
        return None
    rel = Path(entrypoint.strip().replace("\\", "/"))
    # extract_path is MEDIA/algorithms/pkg/<pk>/extract; entrypoint may wrongly repeat that folder.
    if len(rel.parts) > 1 and rel.parts[0] == base.name:
        rel = Path(*rel.parts[1:])

    direct = base / rel
    if direct.is_file():
        return direct.resolve()

    visible = _algorithm_visible_children(base)
    dirs_only = [p for p in visible if p.is_dir()]
    files_only = [p for p in visible if p.is_file()]
    if len(dirs_only) == 1 and len(files_only) == 0:
        nested = dirs_only[0] / rel
        if nested.is_file():
            return nested.resolve()

    matches = [
        p for p in base.rglob(rel.name)
        if p.is_file() and "__MACOSX" not in p.parts
    ]
    rel_norm = rel.as_posix()
    for m in sorted(matches, key=lambda p: len(p.parts)):
        try:
            if m.relative_to(base).as_posix() == rel_norm:
                return m.resolve()
        except ValueError:
            continue
    if len(matches) == 1:
        return matches[0].resolve()
    if matches:
        chosen = min(matches, key=lambda p: len(p.parts))
        if len(matches) > 1:
            logger.warning(
                "resolve_algorithm_script: varios candidatos para %r en %s; "
                "usando %s (otros: %s)",
                rel.name,
                base,
                chosen,
                [str(m) for m in matches if m != chosen],
            )
        return chosen.resolve()
    return None


def _zip_signature(zip_path: Path) -> str:
    st = zip_path.stat()
    return f"{st.st_mtime_ns}:{st.st_size}"


@shared_task
def ejecutar_algoritmo_task(file_id: int, algorithm_id: int, exec_id: int, second_file_id: Optional[int] = None) -> None:
    exec: Optional[Execution] = None
    try:
        file = File.objects.get(id=file_id)
        second_file: Optional[File] = None
        second_input_path: Optional[str] = None
        if second_file_id:
            second_file = File.objects.get(id=second_file_id)
            second_input_path = second_file.file.path
        algorithm = Algorithm.objects.get(id=algorithm_id)

        if not algorithm.archive or not algorithm.archive.name:
            raise ValueError(
                "El algoritmo no tiene archivo ZIP asociado en la base de datos."
            )

        input_file = file.file.path
        exec = Execution.objects.get(id=exec_id)
        if not Path(input_file).is_file():
            raise FileNotFoundError(
                f"No existe el archivo de entrada del usuario: {input_file}"
            )
        if second_file_id and second_input_path is not None:
            if not Path(second_input_path).is_file():
                raise FileNotFoundError(
                    f"No existe el segundo archivo de entrada: {second_input_path}"
                )

        rel_path = os.path.relpath(input_file, settings.MEDIA_ROOT)
        parts = rel_path.split(os.sep)
        if len(parts) < 2:
            raise ValueError(
                f"Ruta de archivo inesperada respecto a MEDIA_ROOT (se esperaba "
                f"al menos dos segmentos): {rel_path!r}"
            )
        user_id_folder = parts[1]

        filename, _ = os.path.splitext(parts[-1])
        now = timezone.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            settings.MEDIA_ROOT, 'outputs', user_id_folder)
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{filename}_{algorithm.name}_{timestamp}_out.zip"
        output_zip = os.path.join(output_dir, output_filename)

        algorithm_zip_path = Path(algorithm.archive.path)
        extract_path = algorithm_extract_disk_path(settings.MEDIA_ROOT, algorithm.pk)
        sig_path = extract_path / ".archive_sig"

        logger.info(
            "ejecutar_algoritmo_task: exec_id=%s algorithm_id=%s zip=%s exists=%s extract=%s",
            exec_id,
            algorithm_id,
            algorithm_zip_path,
            algorithm_zip_path.is_file(),
            extract_path,
        )

        if not algorithm_zip_path.is_file():
            hint = (
                f"No existe el archivo ZIP del algoritmo ({algorithm_zip_path}). "
                "En Docker, web y celery comparten el volumen media: el .zip debe estar en "
                f"algorithms/pkg/{algorithm.pk}/archive.zip."
            )
            if extract_path.is_dir():
                hint += (
                    f" Carpeta extraída en {extract_path}: revisa que "
                    f"{algorithm.entrypoint!r} coincida con la ruta real dentro del proyecto."
                )
            raise FileNotFoundError(hint)

        sig = _zip_signature(algorithm_zip_path)
        stored_sig = ""
        if sig_path.is_file():
            try:
                stored_sig = sig_path.read_text().strip()
            except OSError:
                stored_sig = ""

        script_path = (
            resolve_algorithm_script(extract_path, algorithm.entrypoint)
            if extract_path.is_dir()
            else None
        )
        needs_refresh = stored_sig != sig or script_path is None

        if needs_refresh:
            if extract_path.exists():
                shutil.rmtree(extract_path)
            extract_path.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(algorithm_zip_path, "r") as zip_ref:
                    zip_ref.extractall(extract_path)
            except zipfile.BadZipFile as e:
                raise RuntimeError(
                    f"ZIP del algoritmo corrupto o no es un archivo ZIP válido: "
                    f"{algorithm_zip_path}"
                ) from e
            sig_path.write_text(sig)
            script_path = resolve_algorithm_script(extract_path, algorithm.entrypoint)

        if script_path is None:
            raise FileNotFoundError(
                f"No se encontró {algorithm.entrypoint!r} tras extraer el algoritmo en {extract_path}."
            )

        shared_venv = Path(settings.MEDIA_ROOT) / "envs" / ".algenv"
        python_exec = shared_venv / (
            "Scripts/python.exe" if platform.system() == "Windows" else "bin/python"
        )
        if not python_exec.is_file():
            raise FileNotFoundError(
                f"No existe el intérprete del entorno de algoritmos ({python_exec}). "
                "Comprueba que algenv se instaló (docker-entrypoint / install_requirements_task)."
            )

        cleanup_input_dirs: list[str] = []
        primary_argv, c1 = _wrap_single_image_input_as_dir(input_file, file)
        cleanup_input_dirs.extend(c1)

        command = [str(python_exec), str(script_path), primary_argv]

        if second_file and second_input_path is not None:
            sec_argv, c2 = _wrap_single_image_input_as_dir(
                second_input_path, second_file
            )
            cleanup_input_dirs.extend(c2)
            command.append(sec_argv)

        command.append(output_zip)

        logger.info(
            "ejecutar_algoritmo_task: running script=%s cwd=%s",
            script_path,
            extract_path,
        )
        # TF Object Detection vendored *_pb2.py often breaks with protobuf>=4 unless protos are regenerated.
        algo_env = os.environ.copy()
        algo_env.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
        try:
            proc = subprocess.run(
                command,
                check=False,
                cwd=str(extract_path),
                capture_output=True,
                text=True,
                env=algo_env,
            )
        finally:
            for td in cleanup_input_dirs:
                shutil.rmtree(td, ignore_errors=True)

        if proc.returncode != 0:
            err_tail = (proc.stderr or "")[-4000:]
            out_tail = (proc.stdout or "")[-2000:]
            logger.error(
                "ejecutar_algoritmo_task: script failed rc=%s stderr_tail=%r stdout_tail=%r",
                proc.returncode,
                err_tail,
                out_tail,
            )
            raise subprocess.CalledProcessError(
                proc.returncode,
                command,
                output=proc.stdout,
                stderr=proc.stderr,
            )

        logger.info("ejecutar_algoritmo_task: finished OK exec_id=%s", exec_id)

        exec.status = "FINISHED"
        exec.save(update_fields=['status'])

        Output.objects.create(
            execution=exec,
            file=f"outputs/{user_id_folder}/{output_filename}",
            output_date=now
        )

    except Exception as e:
        if exec:
            exec.status = "FAILED"
            exec.save(update_fields=['status'])
            raise e


REQUIREMENTS_PATH = Path(settings.MEDIA_ROOT) / \
    'envs' / 'requirements_global.txt'
DEBUG_LOG_PATH = Path(settings.MEDIA_ROOT) / 'envs' / 'debug_install.log'


def log_debug(msg: str):
    """Registra eventos con timestamp en el archivo de debug"""
    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as logf:
        logf.write(f"[{timestamp}] {msg}\n")


TF_MODELS_OBJECT_DETECTION_REV = "971ded9e166816d6172cdec474b6bffc5f0cc0ec"

TF_MODELS_OBJECT_DETECTION_VCS_LINE = (
    f"git+https://github.com/tensorflow/models.git@{TF_MODELS_OBJECT_DETECTION_REV}"
    "#egg=object_detection&subdirectory=research/object_detection/packages/tf2"
)

GIT_REQUIREMENTS = {
    "object-detection": TF_MODELS_OBJECT_DETECTION_VCS_LINE,
}

ALGENV_SEED_DIR = Path(settings.BASE_DIR) / "analysis" / "seeds" / "algenv"
ALGENV_BASE_SEED = ALGENV_SEED_DIR / "base.txt"
ALGENV_OD_SEED = ALGENV_SEED_DIR / "object_detection.txt"
ALGENV_YOLO_SEED = ALGENV_SEED_DIR / "yolo.txt"


def algenv_seed_paths() -> tuple[Path, Path, Path] | None:
    trio = (ALGENV_BASE_SEED, ALGENV_OD_SEED, ALGENV_YOLO_SEED)
    if all(p.is_file() for p in trio):
        return trio
    return None


def sync_requirements_global_from_algenv() -> bool:
    """Merge algenv seeds into MEDIA_ROOT (parity with docker-entrypoint merged view)."""
    got = algenv_seed_paths()
    if not got:
        return False
    REQUIREMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = "\n".join(p.read_text(encoding="utf-8").rstrip() for p in got) + "\n"
    REQUIREMENTS_PATH.write_text(merged, encoding="utf-8")
    return True


def _torch_pins_from_base_seed() -> list[str]:
    if not ALGENV_BASE_SEED.is_file():
        return []
    pins: list[str] = []
    for line in ALGENV_BASE_SEED.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith(("torch==", "torchvision==", "triton==")):
            pins.append(s)
    return pins


def _run_pip(python_exec: Path, args: list[str]) -> None:
    cmd = [str(python_exec), "-m", "pip"] + args
    log_debug(f"Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, text=True)


def _pip_check_and_log(python_exec: Path) -> None:
    result = subprocess.run(
        [str(python_exec), "-m", "pip", "check"],
        capture_output=True,
        text=True,
    )
    log_debug(
        "pip check "
        f"(código {result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def append_git_requirements():
    """Ensure git packages are present in requirements_global.txt"""
    if not REQUIREMENTS_PATH.exists():
        REQUIREMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        REQUIREMENTS_PATH.write_text("")

    existing = REQUIREMENTS_PATH.read_text()
    new_lines = []

    for name, git_line in GIT_REQUIREMENTS.items():
        if git_line not in existing:
            new_lines.append(f"# Git package for {name}\n{git_line}\n")

    if new_lines:
        with open(REQUIREMENTS_PATH, "a", encoding="utf-8") as f:
            f.writelines(new_lines)
        log_debug(
            f"Added git packages to requirements_global.txt: {', '.join(GIT_REQUIREMENTS.keys())}")


@shared_task
def actualizar_requirements_global():
    log_debug("=== INICIO actualizar_requirements_global ===")

    shared_venv = Path(settings.MEDIA_ROOT) / 'envs' / '.algenv'
    python_exec = shared_venv / \
        ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")
    log_debug(f"Python ejecutable (freeze): {python_exec}")

    try:
        cmd = [str(python_exec), "-m", "pip", "freeze"]
        log_debug(f"Ejecutando: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        freeze_lines = result.stdout.splitlines()
        log_debug("STDOUT pip freeze:\n" + result.stdout)

        # Reads previous requirements to preserve Git packages
        existing_text = ""
        if REQUIREMENTS_PATH.exists():
            existing_text = REQUIREMENTS_PATH.read_text()

        # Keeps Git packages by filtering lines that start with "git+" from the existing requirements_global.txt
        git_lines = []
        for line in existing_text.splitlines():
            if line.startswith("git+"):
                git_lines.append(line)

        # Overwrites requirements_global.txt with pip freeze + Git packages
        REQUIREMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REQUIREMENTS_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(freeze_lines) + "\n")
            if git_lines:
                f.write("\n".join(git_lines) + "\n")

        log_debug(
            "Archivo requirements_global.txt actualizado correctamente con Git packages preservados.")

    except Exception as e:
        log_debug(f"ERROR en actualizar_requirements_global: {str(e)}")


@shared_task
def install_requirements_task():
    # Resets the debug log at the start of each run to avoid confusion with old logs
    REQUIREMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_LOG_PATH, 'w', encoding='utf-8') as logf:
        logf.write("=== NUEVA EJECUCIÓN install_requirements_task ===\n")

    log_debug(f"Usando REQUIREMENTS_PATH: {REQUIREMENTS_PATH}")

    shared_venv = Path(settings.MEDIA_ROOT) / 'envs' / '.algenv'
    python_exec = shared_venv / \
        ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")
    log_debug(f"Detectado SO: {platform.system()}")
    log_debug(f"Python ejecutable: {python_exec}")

    if not python_exec.exists():
        log_debug(f"ERROR: No se encontró Python en {python_exec}")
        return

    seeds = algenv_seed_paths()
    if not seeds:
        log_debug(
            "ERROR: Faltan seeds en analysis/seeds/algenv/ "
            "(base.txt, object_detection.txt, yolo.txt)."
        )
        return

    base_p, od_p, yolo_p = seeds
    sync_requirements_global_from_algenv()
    log_debug(
        "requirements_global.txt sincronizado desde "
        "analysis/seeds/algenv/*.txt"
    )

    try:
        _run_pip(
            python_exec,
            [
                "install",
                "--no-cache-dir",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
                "Cython>=3.0",
            ],
        )
        torch_pins = _torch_pins_from_base_seed()
        if torch_pins:
            _run_pip(
                python_exec,
                [
                    "install",
                    "--no-cache-dir",
                    "--retries",
                    "5",
                    "--timeout",
                    "180",
                    *torch_pins,
                ],
            )
        _run_pip(
            python_exec,
            [
                "install",
                "--no-cache-dir",
                "--no-build-isolation",
                "--retries",
                "5",
                "--timeout",
                "180",
                "-r",
                str(base_p),
            ],
        )
        _run_pip(
            python_exec,
            [
                "install",
                "--no-cache-dir",
                "--retries",
                "5",
                "--timeout",
                "180",
                "-r",
                str(od_p),
            ],
        )
        _run_pip(
            python_exec,
            [
                "install",
                "--no-cache-dir",
                "--no-build-isolation",
                "--retries",
                "5",
                "--timeout",
                "180",
                "-r",
                str(yolo_p),
            ],
        )
        _run_pip(
            python_exec,
            [
                "install",
                "--no-cache-dir",
                "--no-build-isolation",
                "--retries",
                "5",
                "--timeout",
                "300",
                "--no-deps",
                "yolox @ git+https://github.com/Megvii-BaseDetection/YOLOX.git@0.3.0",
            ],
        )
        log_debug("Instalación por fases (algenv) correcta.")
    except subprocess.CalledProcessError as e:
        log_debug(f"ERROR durante pip install por fases: {e}")

    _pip_check_and_log(python_exec)

    actualizar_requirements_global.delay()
    append_git_requirements()
    log_debug("Git packages asegurados en requirements_global.txt")
    log_debug("Instalación completada.")
