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

    # Leer paquetes actuales del entorno
    current_packages = set()
    try:
        result = subprocess.run(
            [str(python_exec), "-m", "pip", "freeze"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.strip():
                current_packages.add(line.strip().split('==')[0])
        log_debug(f"Paquetes actualmente en entorno: {current_packages}")
    except Exception as e:
        log_debug(f"ERROR al listar paquetes actuales: {str(e)}")

    # Leer paquetes nuevos del archivo
    new_packages = set()
    if REQUIREMENTS_PATH.exists():
        for line in REQUIREMENTS_PATH.read_text().splitlines():
            line = line.strip()
            if line:
                new_packages.add(line.split('==')[0])
    log_debug(
        f"Paquetes deseados según requirements_global.txt: {new_packages}")

    # Desinstalar los paquetes que ya no deberían estar
    to_remove = current_packages - new_packages
    for pkg in to_remove:
        log_debug(f"Desinstalando paquete eliminado: {pkg}")
        subprocess.run([str(python_exec), "-m", "pip", "uninstall",
                       "-y", pkg], capture_output=True, text=True)

    # Instalar paquetes del requirements
    cmd = [str(python_exec), "-m", "pip", "install",
           "-r", str(REQUIREMENTS_PATH)]
    log_debug(f"Ejecutando comando instalación: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        log_debug("STDOUT pip install:\n" + result.stdout)
        log_debug("STDERR pip install:\n" + result.stderr)

        if result.returncode == 0:
            log_debug("Instalación completada correctamente.")
            actualizar_requirements_global.delay()
        else:
            log_debug(f"ERROR: pip install retornó código {result.returncode}")

    except Exception as e:
        log_debug(f"EXCEPCIÓN durante instalación: {str(e)}")
