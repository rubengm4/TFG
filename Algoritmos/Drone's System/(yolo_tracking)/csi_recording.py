import os
import cv2
import time
import datetime
from picamera2 import Picamera2

# === Pedir nombre de archivo por terminal ===
nombre_archivo = input("Introduce el nombre del archivo de vídeo (sin extensión): ").strip()
if not nombre_archivo:
    nombre_archivo = datetime.datetime.now().strftime("csi_%Y-%m-%d_%H-%M-%S")

backup_folder = "experimentos"
os.makedirs(backup_folder, exist_ok=True)
video_path = os.path.join(backup_folder, f"{nombre_archivo}.mp4")

# === Inicializar Picamera2 ===
picam2 = Picamera2()
resolucion = (640, 480)  # Puedes cambiarla según tus necesidades
fps = 10  # Tasa de fotogramas deseada
picam2.configure(picam2.create_video_configuration(main={"size": resolucion, "format": "RGB888"}))
picam2.start()

# === Configurar VideoWriter ===
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
video_writer = cv2.VideoWriter(video_path, fourcc, fps, resolucion)

# === Tiempo de grabación en segundos ===
duracion = 60  # Puedes cambiarlo o pedirlo también por terminal
print(f"Grabando vídeo CSI durante {duracion} segundos...")

start_time = time.time()

while time.time() - start_time < duracion:
    frame = picam2.capture_array()
    video_writer.write(frame)
    time.sleep(1 / fps)  # Control de tasa de grabación

# === Finalizar ===
video_writer.release()
picam2.stop()

print(f"Vídeo guardado en: {video_path}")
