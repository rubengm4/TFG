# analysis/tasks.py

from celery import shared_task  # type: ignore
import os
import zipfile
import platform
import subprocess

from .models import File, Algorithm, Execution, Output  # ajusta según tu estructura

from django.conf import settings
from django.utils import timezone
from pathlib import Path
from typing import Optional


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

        input_file = file.file.path
        exec = Execution.objects.get(id=exec_id)
        rel_path = os.path.relpath(input_file, settings.MEDIA_ROOT)
        parts = rel_path.split(os.sep)
        user_id_folder = parts[1]

        filename, _ = os.path.splitext(parts[-1])
        now = timezone.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            settings.MEDIA_ROOT, 'outputs', user_id_folder)
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{filename}_{algorithm.name}_{timestamp}_out.zip"
        output_zip = os.path.join(output_dir, output_filename)

        # Descomprimir ZIP del algoritmo si no está ya
        algorithm_zip = algorithm.archive.path
        algorithm_stem = Path(algorithm_zip).stem
        extract_path = os.path.join(
            settings.MEDIA_ROOT, 'algorithms', algorithm_stem)

        if not os.path.exists(extract_path):
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(algorithm_zip, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

        script_path = os.path.join(extract_path, algorithm.entrypoint)
        shared_venv = Path(script_path).parents[2] / "envs" / ".algenv"
        python_exec = shared_venv / \
            ("Scripts/python.exe" if platform.system()
             == "Windows" else "bin/python")

        command = [str(python_exec), str(script_path), input_file]

        if second_file and second_input_path is not None:
            command.append(second_input_path)

        command.append(output_zip)

        subprocess.run(command, check=True)

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


GIT_REQUIREMENTS = {
    "object-detection": "git+https://github.com/tensorflow/models.git@master#egg=models"
}


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
        # Ejecuta pip freeze
        cmd = [str(python_exec), "-m", "pip", "freeze"]
        log_debug(f"Ejecutando: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        freeze_lines = result.stdout.splitlines()
        log_debug("STDOUT pip freeze:\n" + result.stdout)

        # Leer requisitos previos
        existing_text = ""
        if REQUIREMENTS_PATH.exists():
            existing_text = REQUIREMENTS_PATH.read_text()

        # Mantener Git packages
        git_lines = []
        for line in existing_text.splitlines():
            if line.startswith("git+"):
                git_lines.append(line)

        # Sobrescribir requirements_global.txt con pip freeze + Git packages
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
    # Reinicia el log cada vez
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

    # Leer requirements_global.txt y separar object-detection
    normal_requirements = []
    special_packages = {}
    if REQUIREMENTS_PATH.exists():
        for line in REQUIREMENTS_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "object-detection" in line:
                special_packages["object-detection"] = "https://github.com/tensorflow/models.git"
            else:
                normal_requirements.append(line)

    # Sobrescribir temporal requirements
    tmp_requirements_path = REQUIREMENTS_PATH.parent / "tmp_requirements.txt"
    tmp_requirements_path.write_text("\n".join(normal_requirements))

    # Instalar paquetes normales y escribir log siempre
    try:
        log_debug(
            f"Instalando paquetes normales: {python_exec} -m pip install -r {tmp_requirements_path}")
        subprocess.run(
            [str(python_exec), "-m", "pip", "install",
             "--upgrade", "-r", str(tmp_requirements_path)],
            check=True, text=True
        )
        log_debug("Paquetes normales instalados correctamente.")
    except Exception as e:
        log_debug(f"ERROR al instalar paquetes normales: {str(e)}")

    # Instalar Object Detection API
    try:
        if "object-detection" in special_packages:
            # Asegurarse de que gitpython esté instalado
            subprocess.run([str(python_exec), "-m", "pip",
                           "install", "gitpython"], text=True)

            tf_models_dir = Path(settings.MEDIA_ROOT) / "envs" / "models"
            if not tf_models_dir.exists():
                log_debug("Clonando TensorFlow Models...")
                subprocess.run(
                    [str(python_exec), "-m", "git", "clone",
                     special_packages["object-detection"], str(tf_models_dir)],
                    check=True, text=True
                )

            research_dir = tf_models_dir / "research"
            if research_dir.exists():
                log_debug("Instalando Object Detection API (editable)...")
                subprocess.run([str(python_exec), "-m", "pip", "install", "-e", str(research_dir)],
                               check=True, text=True)
                log_debug("Object Detection API instalada correctamente.")
            else:
                log_debug(
                    "ERROR: No se encontró la carpeta research en tensorflow/models")
    except Exception as e:
        log_debug(f"EXCEPCIÓN al instalar Object Detection API: {str(e)}")

    # Actualizar requirements_global.txt
    actualizar_requirements_global.delay()

    # **Asegurar que los paquetes Git estén presentes manualmente**
    append_git_requirements()
    log_debug("Git packages asegurados en requirements_global.txt")
    log_debug("Instalación completada correctamente.")
