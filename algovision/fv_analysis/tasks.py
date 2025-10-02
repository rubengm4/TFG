# analysis/tasks.py

from celery import shared_task  # type: ignore
import os
import zipfile
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from django.conf import settings
from .models import File, Algorithm, Execution, Output  # ajusta según tu estructura
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
        now = datetime.now()
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
