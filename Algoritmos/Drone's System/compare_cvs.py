import pandas as pd
import cv2
import matplotlib.pyplot as plt
import os

def load_frame(video_path, frame_number):
    """Carga un frame específico de un video."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    if ret:
        # Convertir BGR a RGB (útil para guardar con plt.imsave)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None

def compare_detections(csv_visible, csv_thermal, video_visible, video_thermal, 
                       threshold=1, tolerance=2, min_consecutive_differences=1, 
                       confidence_threshold=0.3, min_confidence_frames=1):
    # Cargar CSVs
    df_visible = pd.read_csv(csv_visible)
    df_thermal = pd.read_csv(csv_thermal)

    # Convertir Timestamps a datetime (aunque en este caso se usará el Frame_Number para emparejar)
    df_visible['Timestamp'] = pd.to_datetime(df_visible['Timestamp'].astype(float), unit='s')
    df_thermal['Timestamp'] = pd.to_datetime(df_thermal['Timestamp'].astype(float), unit='s')

    # Ordenar por Timestamp (opcional, para tener los datos en orden)
    df_visible = df_visible.sort_values(by='Timestamp')
    df_thermal = df_thermal.sort_values(by='Timestamp')

    # Asegurar tipos correctos en People_Count y Confidence
    df_visible['People_Count'] = df_visible['People_Count'].fillna(0).astype(int)
    df_thermal['People_Count'] = df_thermal['People_Count'].fillna(0).astype(int)
    df_visible['Confidence'] = df_visible['Confidence'].fillna(0).astype(float)
    df_thermal['Confidence'] = df_thermal['Confidence'].fillna(0).astype(float)

    # Renombrar columnas para diferenciar Frame_Number y Timestamp
    df_visible.rename(columns={'Timestamp': 'Timestamp_visible', 'Frame_Number': 'Frame_Number_visible'}, inplace=True)
    df_thermal.rename(columns={'Timestamp': 'Timestamp_thermal', 'Frame_Number': 'Frame_Number_thermal'}, inplace=True)

    # Fusionar los DataFrames usando merge en la columna Frame_Number (se emparejan solo registros con el mismo frame)
    merged_df = pd.merge(
        df_visible, df_thermal,
        left_on='Frame_Number_visible', right_on='Frame_Number_thermal',
        suffixes=('_visible', '_thermal')
    )

    # Calcular la diferencia en el conteo de personas entre ambas cámaras
    merged_df['Difference'] = abs(merged_df['People_Count_visible'] - merged_df['People_Count_thermal'])

    # Se requiere que la diferencia sea exactamente 1 y que al menos uno de los sensores tenga
    # un nivel de confidence >= confidence_threshold. Además, se agrupan frames consecutivos
    # y se confirma el bloque si tiene al menos "required_frames" consecutivos.
    required_frames = max(min_consecutive_differences, min_confidence_frames)

    confirmed_incidents = []
    consecutive_count = 0
    start_index = None

    for index, row in merged_df.iterrows():
        if (row['Difference'] == threshold) and ((row['Confidence_visible'] >= confidence_threshold) or (row['Confidence_thermal'] >= confidence_threshold)):
            if consecutive_count == 0:
                start_index = index
            consecutive_count += 1
        else:
            if consecutive_count >= required_frames:
                confirmed_incidents.extend(merged_df.iloc[start_index:index].to_dict('records'))
            consecutive_count = 0
            start_index = None

    # Verificar si al final quedaron bloques pendientes
    if consecutive_count >= required_frames:
        confirmed_incidents.extend(merged_df.iloc[start_index:].to_dict('records'))

    if confirmed_incidents:
        print(f"\n{len(confirmed_incidents)} POSSIBLE EMERGENCIES DETECTED!\n")
        # Crear carpeta para guardar las imágenes si no existe
        output_dir = "incident_frames"
        os.makedirs(output_dir, exist_ok=True)
        
        for incident in confirmed_incidents:
            print(f"Timestamp Visible: {incident['Timestamp_visible']}"
                  f"\nTimestamp Thermal: {incident['Timestamp_thermal']}"
                  f"\nPeople Count Visible: {incident['People_Count_visible']}"
                  f"\nPeople Count Thermal: {incident['People_Count_thermal']}"
                  f"\nPeople Difference: {incident['Difference']}\n")
            
            # Cargar frames según el número indicado en cada CSV
            frame_visible = load_frame(video_visible, incident['Frame_Number_visible'])
            frame_thermal = load_frame(video_thermal, incident['Frame_Number_thermal'])
            
            if frame_visible is not None:
                filename_visible = os.path.join(output_dir, f"incident_visible_frame_{incident['Frame_Number_visible']}.png")
                plt.imsave(filename_visible, frame_visible)
                print(f"Saved {filename_visible}")
            else:
                print(f"Frame visible not found at frame {incident['Frame_Number_visible']}")
            
            if frame_thermal is not None:
                filename_thermal = os.path.join(output_dir, f"incident_thermal_frame_{incident['Frame_Number_thermal']}.png")
                plt.imsave(filename_thermal, frame_thermal)
                print(f"Saved {filename_thermal}")
            else:
                print(f"Frame thermal not found at frame {incident['Frame_Number_thermal']}")
    else:
        print("\nOK: NO confirmed incidents!")

    return pd.DataFrame(confirmed_incidents)

# Rutas de los videos y CSVs
csv_visible = "detections_csi.csv"
csv_thermal = "detections_thermal.csv"
video_visible = "output_normal_isaac.mp4"
video_thermal = "output_termico_isaac.mp4"

# Ejecutar la comparación y guardar las imágenes de los incidentes confirmados
emergencies = compare_detections(csv_visible, csv_thermal, video_visible, video_thermal)
