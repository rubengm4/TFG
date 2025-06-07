from huggingface_hub import hf_hub_download
from ultralytics import YOLO
from supervision import Detections
import cv2
import os
import datetime
import time
import numpy as np
import csv
from gpiozero import DigitalInputDevice, DigitalOutputDevice
from senxor.mi48 import MI48, DATA_READY
from senxor.utils import data_to_frame
from senxor.interfaces import SPI_Interface, I2C_Interface
from smbus import SMBus
from spidev import SpiDev

RPI_GPIO_I2C_CHANNEL = 1
i2c = I2C_Interface(SMBus(RPI_GPIO_I2C_CHANNEL), 0x40)
RPI_GPIO_SPI_BUS = 0
RPI_GPIO_SPI_CE_MI48 = 0
SPI_XFER_SIZE_BYTES = 160
spi = SPI_Interface(SpiDev(RPI_GPIO_SPI_BUS, RPI_GPIO_SPI_CE_MI48), xfer_size=SPI_XFER_SIZE_BYTES)
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
        print("[Thermal human detection]")

    def __call__(self):
        self.pin.on()
        time.sleep(self.assert_time)
        self.pin.off()
        time.sleep(self.deassert_time)

mi48 = MI48([i2c, spi], data_ready=mi48_data_ready, reset_handler=MI48_reset(pin=mi48_reset_n))
mi48.start(stream=True)

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
    writer.writerow(["Timestamp", "Frame", "X_min", "Y_min", "X_max", "Y_max", "Object_ID", "Class", "Confidence", "People_Count"])

def capture_and_inference(output_path, duration):
    fps = 3
    frame_size = (320, 248)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
    start_time = time.time()
    frame_count = 0
    
    while time.time() - start_time < duration:
        timestamp = time.time()
        frame_count += 1
        
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
            cv2.rectangle(frame_resized, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            label = f"{results[0].names[detections.class_id[i]]}: {detections.confidence[i]:.2f}"
            cv2.putText(frame_resized, label, (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
        
        colored = cv2.applyColorMap(frame_resized, cv2.COLORMAP_JET)
        cv2.putText(frame_resized, f"Personas: {thermal_count}", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        video_writer.write(colored)
        cv2.imshow("Thermal Detection", frame_resized)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_writer.release()
    cv2.destroyAllWindows()

# Flujo principal
duration = 120
current_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
video_filename = f"thermal_detection_{current_date}.mp4"
output_path = os.path.join(backup_folder, video_filename)

capture_and_inference(output_path, duration)
