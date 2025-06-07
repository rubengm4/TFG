import os
import cv2
import csv
import time
import numpy as np
import torch
from ultralytics.nn.autobackend import AutoBackend
from ultralytics.yolo.utils.plotting import colors  # (ya no se utiliza para la caja)
from bytetrack.byte_tracker import BYTETracker
from ultralytics.yolo.utils.ops import non_max_suppression, scale_boxes

# Configuración inicial del modelo
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
model = AutoBackend("yolov8n.pt")
model.warmup()
stride, names, pt = model.stride, model.names, model.pt

# Configuración del tracker
bytetracker = BYTETracker(track_thresh=0.6, match_thresh=0.8, track_buffer=120, frame_rate=30)
tracker = bytetracker

conf_thres = 0.25
iou_thres = 0.45
imgsz = (640, 640)
save_vid = True
save_path = "output_normal_isaac.mp4"
input_video = "drone_isaac_normal.mp4"  # Ruta al video de entrada

# Inicializar VideoCapture para leer el archivo de video
cap = cv2.VideoCapture(input_video)

# Inicializar CSV para guardar detecciones
csv_file = open("detections_csi.csv", mode="w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["Timestamp", "Frame_Number", "X_min", "Y_min", "X_max", "Y_max", "Object_ID", "Class", "Confidence", "People_Count"])

vid_writer = None
frame_id = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    timestamp = time.time()
    im0 = frame.copy()
    im = cv2.resize(frame, imgsz).transpose(2, 0, 1)
    im = torch.from_numpy(np.ascontiguousarray(im)).float() / 255.0
    im = torch.unsqueeze(im, 0)

    # Inicia el contador de detección
    detection_start = time.time()
    # Inferencia
    result = model(im)
    p = non_max_suppression(result, conf_thres, iou_thres, None, False, max_det=1000)
    detection_time = time.time() - detection_start

    person_count = 0
    detections = []
    
    for det in p:
        if det is not None and len(det):
            det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()
        
        track_result = tracker.update(det.cpu(), im0)
        
        for output in track_result:
            bbox, obj_id, cls, conf = output[:4], int(output[4]), int(output[5]), output[6]
            x_min, y_min, x_max, y_max = map(int, bbox)
            
            if names[cls] == "person":  # Contar solo personas
                person_count += 1
            
            detections.append([timestamp, frame_id, x_min, y_min, x_max, y_max, obj_id, names[cls], conf])
            
            label = f"{obj_id} {names[cls]} {conf:.2f}"
            # Dibujar la caja de detección en verde con mayor grosor
            cv2.rectangle(im0, (x_min, y_min), (x_max, y_max), (0, 255, 0), thickness=6)
            
            # Calcular el tamaño del texto para la etiqueta gigante
            (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 6, 10)
            # Posicionar el texto a la izquierda del cuadro, con margen y desplazado más abajo para evitar el contador
            text_x = x_min - text_width - 5
            if text_x < 0:
                text_x = 0
            text_y = y_min + text_height + 300 
            
            cv2.putText(im0, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 6, (0, 255, 0), 10, cv2.LINE_AA)

    # Escribir en CSV incluyendo el conteo de personas
    for det in detections:
        csv_writer.writerow([timestamp, frame_id, x_min, y_min, x_max, y_max, obj_id, names[cls], conf, person_count])

    # Mostrar el contador de personas en pantalla, bajado en el eje Y y con mayor grosor
    cv2.putText(im0, f"Personas: {person_count}", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 6, (0, 255, 0), 10, cv2.LINE_AA)
    
    # Redimensionar la imagen para la preview (por ejemplo, al 50% de su tamaño original)
    preview = cv2.resize(im0, (im0.shape[1] // 2, im0.shape[0] // 2))
    cv2.imshow("Video", preview)

    frame_id += 1
    
    if cv2.waitKey(1) == ord("q"):
        break
    
    # Guardar video
    if save_vid:
        if not vid_writer:
            h, w, _ = im0.shape
            vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*"mp4v"), 5, (w, h))
        vid_writer.write(im0)

# Liberar recursos
csv_file.close()
if vid_writer:
    vid_writer.release()
cap.release()
cv2.destroyAllWindows()
