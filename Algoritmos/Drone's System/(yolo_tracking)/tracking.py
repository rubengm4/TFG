import os
import cv2
import csv
import time
import numpy as np
import torch
from picamera2 import Picamera2
from ultralytics.nn.autobackend import AutoBackend
from ultralytics.yolo.utils.plotting import Annotator, colors
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
save_path = "output_csi.mp4"

# Inicializar la cámara
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": imgsz, "format": "RGB888"}))
picam2.start()

# Inicializar CSV para guardar detecciones
csv_file = open("detections_csi.csv", mode="w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["Timestamp", "Frame", "X_min", "Y_min", "X_max", "Y_max", "Object_ID", "Class", "Confidence", "People_Count"])

vid_writer = None
frame_id = 0

while True:
    timestamp = time.time()
    frame = picam2.capture_array()
    im0 = frame.copy()
    im = cv2.resize(frame, imgsz).transpose(2, 0, 1)
    im = torch.from_numpy(np.ascontiguousarray(im)).float() / 255.0
    im = torch.unsqueeze(im, 0)

    # Inferencia
    result = model(im)
    p = non_max_suppression(result, conf_thres, iou_thres, None, False, max_det=1000)
    
    person_count = 0
    detections = []
    
    for det in p:
        if det is not None and len(det):
            det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()
        
        track_result = tracker.update(det.cpu(), im0)
        annotator = Annotator(im0, line_width=2, example=str(names))
        
        for output in track_result:
            bbox, obj_id, cls, conf = output[:4], int(output[4]), int(output[5]), output[6]
            x_min, y_min, x_max, y_max = map(int, bbox)
            
            if names[cls] == "person":  # Contar solo personas
                person_count += 1
            
            detections.append([timestamp, frame_id, x_min, y_min, x_max, y_max, obj_id, names[cls], conf])
            
            label = f"{obj_id} {names[cls]} {conf:.2f}"
            annotator.box_label(bbox, label, color=colors(cls, True))

    # Escribir en CSV incluyendo el conteo de personas
    for det in detections:
        csv_writer.writerow(det + [person_count])
    
    # Mostrar el conteo de personas en pantalla
    cv2.putText(im0, f"Personas: {person_count}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Camera", im0)

    frame_id += 1  # Incrementar el contador de frames
    
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
picam2.stop()
cv2.destroyAllWindows()
