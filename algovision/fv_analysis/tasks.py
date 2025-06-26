# analysis/tasks.py

from celery import shared_task
import os
import zipfile
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.files.storage import default_storage
from .models import File, Algorithm, Execution, Output  # ajusta según tu estructura


@shared_task
def ejecutar_algoritmo_task(file_id, algorithm_id, user_id, exec_id):
    try:
        file = File.objects.get(id=file_id)
        algorithm = Algorithm.objects.get(id=algorithm_id)
        exec = Execution.objects.get(id=exec_id)
        input_file = file.file.path

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

        subprocess.run([str(python_exec), str(script_path),
                       input_file, output_zip], check=True)

        exec.status = "COMPLETED"
        exec.save(update_fields=['status'])

        Output.objects.create(
            execution=exec,
            file=f"outputs/{user_id_folder}/{output_filename}",
            output_date=now
        )

    except Exception as e:
        exec.status = "FAILED"
        exec.save(update_fields=['status'])
        raise e
