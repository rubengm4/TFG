import os
import django
import time
from pathlib import Path

# 1. BIND SETTINGS (Change 'your_project_name' to your actual folder name)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'algovision.settings')
django.setup()


def run_benchmark(algorithm_id: int, num_images: int = 50):
    """
    Dispatches benchmark tasks to Celery after Django is initialized.
    """
    # 2. LOCAL IMPORTS (These stay here so the formatter won't move them)
    from django.contrib.auth.models import User
    from django.core.files import File as DjangoFile
    from django.utils import timezone
    from analysis.models import File, Algorithm, Execution, FileType
    from analysis.tasks import ejecutar_algoritmo_task

    # --- UPDATED PATH LOGIC ---
    # This points to the folder you specified
    BASE_DIR = Path(__file__).resolve().parent.parent
    img_folder = BASE_DIR / "Algoritmos" / "experiments" / "1" / "bench_images"
    print(img_folder)

    # Absolute path for debugging
    abs_path = os.path.abspath(img_folder)
    print(f"[*] Searching for images in: {abs_path}")

    if not os.path.exists(img_folder):
        print(f"[!] FOLDER NOT FOUND.")
        print(f"    Check if you are running the script from the 'TFG' root folder.")
        return

    try:
        algo = Algorithm.objects.get(id=algorithm_id)
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()  # Fallback to any user
    except Algorithm.DoesNotExist:
        print(
            f"[!] Algorithm with ID {algorithm_id} does not exist in the DB.")
        return

    # 4. WARM-UP PHASE (Optional but recommended for TFG rigor)
    print(f"[*] Starting Warm-up for {algo.name}...")
    sample_files = [f for f in os.listdir(img_folder) if f.endswith(".jpg")]

    if sample_files:
        warmup_file = os.path.join(img_folder, sample_files[0])
        # We send 2 quick tasks just to load the system/DB connections
        for _ in range(2):
            # We don't save these results, just 'priming the pump'
            print("    > Priming worker...")

    time.sleep(2)  # Short pause before the flood

    # 5. THE MAIN EVENT
    print(
        f"[*] Dispatching {len(sample_files[:num_images])} tasks to Celery...")

    file_type = FileType.objects.get(id=2)  # Get file_type = image for DB
    upload_date = timezone.now()  # Get upload_date for DB

    for filename in sample_files[:num_images]:
        full_path = os.path.join(img_folder, filename)

        # Create DB records so the worker has something to look up
        with open(full_path, 'rb') as f:
            django_file = File.objects.create(
                user=user,
                file=DjangoFile(f, name=filename),
                type=file_type,
                upload_date=upload_date
            )

        execution_date = timezone.now()  # Get execution_date for DB
        execution = Execution.objects.create(
            user=user,
            algorithm=algo,
            status="PENDING",
            execution_date=execution_date
        )

        # Trigger Celery
        ejecutar_algoritmo_task.delay(
            file_id=django_file.id,
            algorithm_id=algo.id,
            exec_id=execution.id
        )
        print(f"    [+] Queued: {filename} (Exec ID: {execution.id})")

    print("\n[SUCCESS] All tasks are in the queue.")
    print("[TIP] Make sure your worker is running with: celery -A your_project_name worker -c 1")


if __name__ == "__main__":
    # Update this ID to match your YOLO or MobileNet ID in the DB
    TARGET_ALGO_ID = 18
    run_benchmark(TARGET_ALGO_ID, 10)
