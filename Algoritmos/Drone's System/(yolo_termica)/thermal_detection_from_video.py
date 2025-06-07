from huggingface_hub import hf_hub_download
from ultralytics import YOLO
from supervision import Detections
import cv2
import os
import datetime
import time
import numpy as np
import csv

# Se elimina el código relacionado con la adquisición en tiempo real (sensor, gpio, SPI, etc.)
# y se define la ruta del video de entrada.
input_video = "drone_isaac_termico.mp4"

model_path = hf_hub_download(
    repo_id="pitangent-ds/YOLOv8-human-detection-thermal",
    filename="model.pt"
)
model = YOLO(model_path)

backup_folder = "thermal_backup_videos"
os.makedirs(backup_folder, exist_ok=True)

csv_filename = "detections_thermal.csv"
with open(csv_filename, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "Frame_Number", "X_min", "Y_min", "X_max", "Y_max", "Object_ID", "Class", "Confidence", "People_Count"])

def capture_and_inference(output_path, duration):
    # Abrir el video de entrada en lugar de capturar en tiempo real
    cap = cv2.VideoCapture(input_video)
    
    fps = 3
    frame_size = (320, 248)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
    start_time = time.time()
    frame_count = 0
    
    while cap.isOpened() and (time.time() - start_time < duration):
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp = time.time()
        frame_count += 1

        # Redimensionar el frame al tamaño deseado para el análisis
        frame_resized = cv2.resize(frame, frame_size, interpolation=cv2.INTER_LINEAR)

        results = model(frame_resized, conf=0.4, verbose=False)
        detections = Detections.from_ultralytics(results[0])
        thermal_count = len(detections.xyxy)
        
        with open(csv_filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            for i, (x1, y1, x2, y2) in enumerate(detections.xyxy):
                class_id = detections.class_id[i]
                confidence = detections.confidence[i]
                writer.writerow([timestamp, frame_count, int(x1), int(y1), int(x2), int(y2), i, results[0].names[class_id], f"{confidence:.2f}", thermal_count])

        
        for i in range(len(detections.xyxy)):
            x1, y1, x2, y2 = detections.xyxy[i]
            # Dibujar el recuadro en verde
            cv2.rectangle(frame_resized, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            # Crear la etiqueta con el formato "human, confidence"
            label = f"human, {detections.confidence[i]:.2f}"
            # Calcular el tamaño del texto
            (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            # Ubicar el texto a la izquierda del cuadro
            text_x = int(x1) - text_width - 5
            if text_x < 0:
                text_x = 0
            text_y = int(y1) + text_height // 2
            cv2.putText(frame_resized, label, (text_x, text_y + 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Mostrar el contador de personas en la imagen
        cv2.putText(frame_resized, f"Personas: {thermal_count}", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        colored = cv2.applyColorMap(frame_resized, cv2.COLORMAP_JET)
        video_writer.write(colored)
        
        # Aumentar el tamaño de la preview (por ejemplo, escala al 200%)
        preview = cv2.resize(frame_resized, (int(frame_resized.shape[1]*2.0), int(frame_resized.shape[0]*2.0)))
        cv2.imshow("Thermal Detection", preview)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_writer.release()
    cap.release()
    cv2.destroyAllWindows()

# Flujo principal
duration = 120
video_filename = f"output_termico_isaac.mp4"
output_path = os.path.join(backup_folder, video_filename)

capture_and_inference(output_path, duration)
