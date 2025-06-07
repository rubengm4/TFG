import time
import csv
import os
import cv2
import numpy as np
from ultralytics import YOLO

# ——————————————————————
#  Parámetros
# ——————————————————————
INPUT_IMAGE   = "image2.JPG"      # tu imagen
CSV_FILE      = "detections_image.csv" # salida CSV
OUTPUT_IMAGE  = "image1_with_detections.jpg"  # imagen anotada
MODEL_PATH    = "yolov8n.pt"           # tu modelo
CONF_THRESH   = 0.25
IOU_THRESH    = 0.45

# ——————————————————————
#  Prepara CSV (cabecera)
# ——————————————————————
with open(CSV_FILE, mode="w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Timestamp",
        "X_min", "Y_min", "X_max", "Y_max",
        "Class",
        "Confidence",
        "People_Count"
    ])

# ——————————————————————
#  Carga y comprueba imagen
# ——————————————————————
img = cv2.imread(INPUT_IMAGE)
if img is None:
    raise FileNotFoundError(f"No se encontró: {INPUT_IMAGE}")

# ——————————————————————
#  Inferencia
# ——————————————————————
model   = YOLO(MODEL_PATH)
res     = model(img, conf=CONF_THRESH, iou=IOU_THRESH)[0]
boxes   = res.boxes.xyxy.cpu().numpy().astype(int)  # [[x1,y1,x2,y2],…]
cls_ids = res.boxes.cls.cpu().numpy().astype(int)
confs   = res.boxes.conf.cpu().numpy()

timestamp    = time.time()
people_count = 0
rows         = []

# ——————————————————————
#  Filtra “person”, dibuja y acumula filas
# ——————————————————————
for (x1, y1, x2, y2), cid, conf in zip(boxes, cls_ids, confs):
    name = res.names[cid]
    if name != "person":
        continue
    people_count += 1

    # añade fila al CSV
    rows.append([
        timestamp,
        x1, y1, x2, y2,
        name,
        f"{conf:.2f}",
        people_count
    ])

    # dibuja bounding‐box
    cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,0), 2)
    label = f"{name} {conf:.2f}"
    cv2.putText(img, label, (x1, y1-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)

# ——————————————————————
#  Escribe detecciones en CSV
# ——————————————————————
with open(CSV_FILE, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(rows)

# ——————————————————————
#  Overlay con el contador
# ——————————————————————
cv2.putText(img,
            f"Personas: {people_count}",
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2, (0,255,0), 3)

# ——————————————————————
#  Guarda la imagen anotada
# ——————————————————————
cv2.imwrite(OUTPUT_IMAGE, img)
print(f"Imagen anotada guardada en: {OUTPUT_IMAGE}")
