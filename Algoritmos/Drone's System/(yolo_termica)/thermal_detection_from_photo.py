from huggingface_hub import hf_hub_download
from ultralytics import YOLO
import cv2
import os
import time
import csv
import numpy as np

# ——————————————————————————————————————
#  Parámetros
# ——————————————————————————————————————
INPUT_IMAGE    = "image2.JPG"                      # tu imagen térmica RAW
CSV_FILE       = "detections_thermal_image1.csv"  # CSV de salida
OUTPUT_IMAGE   = "image1_with_detections.jpg"     # imagen anotada
MODEL_REPO     = "pitangent-ds/YOLOv8-human-detection-thermal"
MODEL_FILE     = "model.pt"
CONF_THRESH    = 0.4
IOU_THRESH     = 0.45
IMG_SIZE       = 320

# ——————————————————————————————————————
#  Descarga y carga el modelo
# ——————————————————————————————————————
model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
model = YOLO(model_path)

# ——————————————————————————————————————
#  Prepara CSV
# ——————————————————————————————————————
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp",
            "X_min", "Y_min", "X_max", "Y_max",
            "Object_ID", "Class", "Confidence", "People_Count"
        ])

# ——————————————————————————————————————
#  Lee la imagen en gris y duplica canales
# ——————————————————————————————————————
gray = cv2.imread(INPUT_IMAGE, cv2.IMREAD_GRAYSCALE)
if gray is None:
    raise FileNotFoundError(f"No se encontró: {INPUT_IMAGE}")
# para el modelo necesitamos 3 canales:
frame_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

# ——————————————————————————————————————
#  Inferencia (YOLO hace resize/letterbox)
# ——————————————————————————————————————
ts      = time.time()
results = model(frame_bgr, imgsz=IMG_SIZE, conf=CONF_THRESH, iou=IOU_THRESH)[0]

# extrae coordenadas, clases y confianzas
boxes   = results.boxes.xyxy.cpu().numpy().astype(int)  # [[x1,y1,x2,y2],...]
cls_ids = results.boxes.cls.cpu().numpy().astype(int)
confs   = results.boxes.conf.cpu().numpy()

# ——————————————————————————————————————
#  Filtra “person” y escribe filas
# ——————————————————————————————————————
people_count = 0
rows = []
for idx, ((x1, y1, x2, y2), cid, conf) in enumerate(zip(boxes, cls_ids, confs)):
    name = results.names[cid]
    if name != "person":
        continue
    people_count += 1
    rows.append([
        ts, x1, y1, x2, y2,
        idx, name, f"{conf:.2f}", people_count
    ])

# vuelca al CSV
with open(CSV_FILE, "a", newline="") as f:
    csv.writer(f).writerows(rows)

# ——————————————————————————————————————
#  Genera colormap, dibuja boxes y texto
# ——————————————————————————————————————
# aplica JET al canal original
colored = cv2.applyColorMap(gray, cv2.COLORMAP_JET)

for x1, y1, x2, y2, obj_id, name, conf_str, _ in rows:
    # bounding box
    cv2.rectangle(colored, (x1, y1), (x2, y2), (0, 255, 0), 2)
    # etiqueta
    label = f"{name} {conf_str}"
    cv2.putText(colored, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

# overlay contador
cv2.putText(colored,
            f"Personas: {people_count}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2, (0, 255, 0), 3)

# ——————————————————————————————————————
#  Guarda la imagen anotada y acaba
# ——————————————————————————————————————
os.makedirs(os.path.dirname(OUTPUT_IMAGE) or ".", exist_ok=True)
cv2.imwrite(OUTPUT_IMAGE, colored)
print(f"Detecciones guardadas en CSV: {CSV_FILE}")
print(f"Imagen anotada guardada en:  {OUTPUT_IMAGE}")
