import cv2
import os
import time
import datetime
import numpy as np
from senxor.mi48 import MI48, DATA_READY
from senxor.utils import data_to_frame
from senxor.interfaces import SPI_Interface, I2C_Interface
from gpiozero import DigitalInputDevice, DigitalOutputDevice
from smbus import SMBus
from spidev import SpiDev

# === Configuración de interfaces ===
i2c = I2C_Interface(SMBus(1), 0x40)
spi = SPI_Interface(SpiDev(0, 0), xfer_size=160)
spi.device.mode = 0b00
spi.device.max_speed_hz = 31200000
spi.device.bits_per_word = 8
spi.device.lsbfirst = False
spi.cshigh = True
spi.no_cs = True

mi48_spi_cs_n = DigitalOutputDevice("BCM7", active_high=False, initial_value=False)
mi48_data_ready = DigitalInputDevice("BCM24", pull_up=False)
mi48_reset_n = DigitalOutputDevice("BCM23", active_high=False, initial_value=True)

class MI48_reset:
    def __init__(self, pin, assert_seconds=0.000035, deassert_seconds=0.050):
        self.pin = pin
        self.assert_time = assert_seconds
        self.deassert_time = deassert_seconds
        print("[Grabación térmica iniciada]")

    def __call__(self):
        self.pin.on()
        time.sleep(self.assert_time)
        self.pin.off()
        time.sleep(self.deassert_time)

# === Inicializar cámara térmica ===
mi48 = MI48([i2c, spi], data_ready=mi48_data_ready, reset_handler=MI48_reset(pin=mi48_reset_n))
mi48.start(stream=True)

# === Solicitar nombre de archivo por terminal ===
nombre_archivo = input("Introduce el nombre del archivo de vídeo (sin extensión): ").strip()
if not nombre_archivo:
    nombre_archivo = datetime.datetime.now().strftime("thermal_%Y-%m-%d_%H-%M-%S")

backup_folder = "experimentos"
os.makedirs(backup_folder, exist_ok=True)
video_path = os.path.join(backup_folder, f"{nombre_archivo}.mp4")

# === Configuración del vídeo ===
fps = 3
frame_size = (320, 248)
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
video_writer = cv2.VideoWriter(video_path, fourcc, fps, frame_size)

# === Duración (puedes cambiarlo o pedirlo también por terminal) ===
duracion_segundos = 60
start_time = time.time()

print(f"Grabando vídeo térmico durante {duracion_segundos} segundos... Pulsa 'q' para salir antes.")

# === Grabación del vídeo sin mostrar ===
while time.time() - start_time < duracion_segundos:
    if mi48_data_ready is not None:
        mi48_data_ready.wait_for_active()
    else:
        while True:
            status = mi48.get_status()
            if status & DATA_READY:
                break
            time.sleep(0.001)

    mi48_spi_cs_n.on()
    time.sleep(0.0001)
    data, _ = mi48.read()
    mi48_spi_cs_n.off()

    if data is None:
        continue

    img = data_to_frame(data, mi48.fpa_shape).astype(np.uint8)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    cv2.normalize(img, img, 0, 255, cv2.NORM_MINMAX)
    frame_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    frame_resized = cv2.resize(frame_bgr, frame_size, interpolation=cv2.INTER_LINEAR)
    colored = cv2.applyColorMap(frame_resized, cv2.COLORMAP_JET)

    video_writer.write(colored)

video_writer.release()
print(f"Vídeo guardado en: {video_path}")
