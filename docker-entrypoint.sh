#!/bin/sh
set -e
# Runs as the image user (appuser, UID 1000). Named volumes are chowned once by
# web-init in docker-compose.prod.yml before web/celery start.
mkdir -p /app/media /app/static /app/media/envs

# analysis.tasks.ejecutar_algoritmo_task expects MEDIA_ROOT/envs/.algenv/bin/python
# (same layout as OneDrive media). Create a venv here if missing so the path exists.
if [ ! -x /app/media/envs/.algenv/bin/python ]; then
  /usr/local/bin/python3 -m venv /app/media/envs/.algenv
fi

DEST=/app/media/envs/requirements_global.txt
STAMP=/app/media/envs/.requirements_global.sha256
LOCK=/app/media/envs/.pip-install.lock
SEED_DIR=/app/algovision/analysis/seeds/algenv
BASE_SEED="$SEED_DIR/base.txt"
OD_SEED="$SEED_DIR/object_detection.txt"
YOLO_SEED="$SEED_DIR/yolo.txt"

if [ -f "$BASE_SEED" ] && [ -f "$OD_SEED" ] && [ -f "$YOLO_SEED" ]; then
  CURRENT=$(cat "$BASE_SEED" "$OD_SEED" "$YOLO_SEED" | sha256sum | awk '{print $1}')
else
  echo "docker-entrypoint: error: missing algenv seeds under $SEED_DIR (base/object_detection/yolo)." >&2
  exit 1
fi

# Skip with SKIP_ALGENV_PIP=1 (CI / debugging).
if [ -z "${SKIP_ALGENV_PIP:-}" ]; then
  (
    flock 9
    PREVIOUS=""
    if [ -f "$STAMP" ]; then
      PREVIOUS=$(cat "$STAMP")
    fi
    if [ "$CURRENT" = "$PREVIOUS" ]; then
      exit 0
    fi
    cat "$BASE_SEED" "$OD_SEED" "$YOLO_SEED" > "$DEST"

    # pycocotools builds read Cython from the venv; pip build isolation hides it unless disabled.
    /app/media/envs/.algenv/bin/pip install \
      --no-cache-dir --upgrade pip setuptools wheel "Cython>=3.0"
    # yolox metadata expects torch already installed before resolver sees yolo.txt.
    TORCH_PKGS=$(grep -E '^(torch|torchvision|triton)==' "$BASE_SEED" | tr '\n' ' ')
    if [ -n "$TORCH_PKGS" ]; then
      # shellcheck disable=SC2086
      /app/media/envs/.algenv/bin/pip install \
        --no-cache-dir --retries 5 --timeout 180 $TORCH_PKGS
    fi
    /app/media/envs/.algenv/bin/pip install \
      --no-cache-dir --no-build-isolation --retries 5 --timeout 180 -r "$BASE_SEED"
    /app/media/envs/.algenv/bin/pip install \
      --no-cache-dir --retries 5 --timeout 180 -r "$OD_SEED"
    # yolox setup imports torch during metadata; default build isolation hides the venv.
    /app/media/envs/.algenv/bin/pip install \
      --no-cache-dir --no-build-isolation --retries 5 --timeout 180 -r "$YOLO_SEED"
    # PyPI yolox pins onnxruntime==1.8.0 (no cp311); install Megvii tag without dependency pins.
    /app/media/envs/.algenv/bin/pip install \
      --no-cache-dir --no-build-isolation --retries 5 --timeout 300 --no-deps \
      "yolox @ git+https://github.com/Megvii-BaseDetection/YOLOX.git@0.3.0"

    /app/media/envs/.algenv/bin/pip check >&2 || true

    echo "$CURRENT" > "$STAMP"
  ) 9>>"$LOCK"
fi

exec "$@"
