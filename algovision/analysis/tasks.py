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
        log_debug("STDOUT pip freeze:\n" + result.stdout)

        REQUIREMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        REQUIREMENTS_PATH.write_text(result.stdout)
        log_debug("Archivo requirements_global.txt actualizado correctamente.")

    except Exception as e:
        log_debug(f"ERROR en actualizar_requirements_global: {str(e)}")


@shared_task
def install_requirements_task():
    # Reinicia el log cada vez
    with open(DEBUG_LOG_PATH, 'w', encoding='utf-8') as logf:
        logf.write("=== NUEVA EJECUCIÓN install_requirements_task ===\n")

    log_debug(f"REQUIREMENTS_PATH: {REQUIREMENTS_PATH}")

    shared_venv = Path(settings.MEDIA_ROOT) / 'envs' / '.algenv'
    python_exec = shared_venv / \
        ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")
    log_debug(f"Detectado SO: {platform.system()}")
    log_debug(f"Python ejecutable: {python_exec}")

    if not python_exec.exists():
        log_debug(f"ERROR: No se encontró Python en {python_exec}")
        return

    # Leer paquetes normales del requirements (excluyendo object-detection)
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

    # Crear un archivo temporal para pip
    tmp_requirements_path = REQUIREMENTS_PATH.parent / "tmp_requirements.txt"
    tmp_requirements_path.write_text("\n".join(normal_requirements))

    # Instalar paquetes normales
    try:
        log_debug(
            f"Instalando paquetes normales: {python_exec} -m pip install -r {tmp_requirements_path}")
        subprocess.run([str(python_exec), "-m", "pip", "install", "-r", str(tmp_requirements_path)],
                       check=True, text=True)
        log_debug("Paquetes normales instalados correctamente.")
    except Exception as e:
        log_debug(f"ERROR al instalar paquetes normales: {str(e)}")

    # Instalar Object Detection API desde GitHub
    try:
        if "object-detection" in special_packages:
            tf_models_dir = Path(settings.MEDIA_ROOT) / "envs" / "models"
            if not tf_models_dir.exists():
                log_debug("Clonando TensorFlow Models...")
                subprocess.run([str(python_exec), "-m", "git", "clone", special_packages["object-detection"], str(tf_models_dir)],
                               check=True)
            research_dir = tf_models_dir / "research"
            if research_dir.exists():
                log_debug("Instalando Object Detection API (editable)...")
                subprocess.run([str(python_exec), "-m", "pip", "install", "-e", str(research_dir)],
                               check=True)
                log_debug("Object Detection API instalada correctamente.")
            else:
                log_debug(
                    "ERROR: No se encontró la carpeta research en tensorflow/models")
    except Exception as e:
        log_debug(f"EXCEPCIÓN al instalar Object Detection API: {str(e)}")

    # Actualizar requirements_global.txt
    actualizar_requirements_global.delay()
    log_debug("Instalación completada correctamente.")
