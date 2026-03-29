import os
import requests
import random
import time

COCO_URL = "http://images.cocodataset.org/val2017/"
IMG_FOLDER = "bench_images"
NUM_IMAGES = 50

os.makedirs(IMG_FOLDER, exist_ok=True)


def download_coco_samples():
    print(f"[*] Starting sequential download for {NUM_IMAGES} images...")

    count = 16
    current_id = 3676  # Starting point

    while count < NUM_IMAGES:
        print(current_id)
        file_name = f"{str(current_id).zfill(12)}.jpg"
        url = f"{COCO_URL}{file_name}"

        try:
            # We use a short timeout so we skip 404s quickly
            response = requests.get(url, timeout=2)

            if response.status_code == 200:
                with open(os.path.join(IMG_FOLDER, file_name), 'wb') as f:
                    f.write(response.content)
                count += 1
                print(f"    [{count}/{NUM_IMAGES}] SUCCESS: {file_name}")
            # If 404, we just silently move to the next ID

        except Exception:
            # If the internet hiccups, wait a second
            time.sleep(1)

        current_id += 1

        # Safety break if we go way too far
        if current_id > 100000:
            break

    print(f"\n[+] Done! You now have {count} images in '{IMG_FOLDER}'.")


if __name__ == "__main__":
    download_coco_samples()
