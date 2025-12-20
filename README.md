# TFG

Trabajo de Fin de Grado

## Autor: Rubén Argenta García

## ¿Cómo añadir un nuevo proyecto?

1. Make sure to have a administrator account created in a project, with created permissions for every project (TODO: Make script)
2. Log in with this administrator account in a project (obviously, one with permissions)
3. Click Manage Projects on the initial dashboard.
4. Click Add Project (name, description and start date) to add a project to the database.
5. Once it has been added, go to Manage Projects again and then to Manage Permissions from Projects.
6. There, you can manage the permissions for every user. It is not recommended to add a user to more than one project: (1 User - 1 Project). The exception would be the administrators, which should have access for every project.
7. In _accounts/views.py_, you need to add this text to the clase **SetSourceAndRedirectToLogin** (inside the function _post(self, request: HttpRequest):_). You need to substitute _example_project_ by the new project name (**maintaining the _-home_ suffix**):

   ```python
    elif source == 'example-project':
        return redirect('example_project_home')
   ```

8. In _algovision/urls.py_, add the following line, substituting _example_project_ by the new project name (**maintaining the _-home_ suffix**):
   ```python
   path('example-project-home/', LoginHomeView.as_view(), name='example_project_home'),
   ```
9. In _analysis/templates/index.html_, add a similar element to the following to create a button with a link to the new project, changing Example and _value="example-project"_ by the new project's name.

   ```html
   <div class="col-auto">
     <form method="post" action="{% url 'accounts:set_source' %}">
       {% csrf_token %}
       <input type="hidden" name="source" value="example-project" />
       <button type="submit" class="btn btn-primary px-4">Example</button>
     </form>
   </div>
   ```

10. (Opcional pero recomendable) Añadir el proyecto a la sidebar en _analysis/templates/index.html_. El icono se modifica editando la clase del elemento _<i>_, y habría que modificar el _value_ poniendo el nombre del proyecto en vez de _example_analysis_ y cambiando Example también (aunque ese cambio es visual)

    ```html
    <li>
      <form method="post" action="{% url 'accounts:set_source' %}">
        {% csrf_token %}
        <input type="hidden" name="source" value="example-analysis" />
        <button
          type="submit"
          class="block py-2.5 px-4 rounded-lg transition-all hover:bg-gray-800 hover:text-white text-left w-full"
        >
          <i class="fas fa-solar-panel text-teal-600"></i> Example
        </button>
      </form>
    </li>
    ```

11. Now our project will be configured correctly and appearing in the frontend, so we can now access with our administrator or create a new user. But the project can be accessed from now on.

---

## ¿Cómo crear scripts y subir algoritmos?

1. Deberíamos de tener un script con el algoritmo o a ejecutar, o varios en caso de que haya más de uno. Uno por cada algoritmo.

   - En caso de tener solo un script es sencillo, puesto que podríamos subir un archivo comprimido (.zip) que contenga solo ese archivo, y al crear el algoritmo, en _entrypoint_ poner el nombre del script, que podría ser por ejemplo: _ejemplo_algoritmo.py_. También podríamos crear un archivo _main.py_ en el que se ejecute el algoritmo. Más abajo se explica el formato que debería tener este archivo para que funcione correctamente
   - En caso de tener varios archivos, (porque queramos combinar dos algoritmos que están en scripts separados, por ejemplo), deberemos de crear un _main.py_ obligatoriamente, para gestionar el orden en el que ejecutarlos.

2. Para la creación de este archivo _main.py_, se sugiere que se modifique el siguiente template:

   ```python

   import sys
   import subprocess
   import shutil
   import tempfile
   import zipfile
   from pathlib import Path


   def zip_directory(folder_path: Path, zip_path: Path):
      """Comprime recursivamente el contenido de una carpeta en un archivo ZIP."""
      with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
         for file in folder_path.rglob('*'):
               if file.is_file():
                  zipf.write(file, arcname=file.relative_to(folder_path))


   def run_script(script_path: Path, args: list[str], cwd: Path = None):
      """Ejecuta un script de Python con los argumentos dados, y lanza error si falla."""
      subprocess.run([sys.executable, str(script_path)] + args, check=True, cwd=cwd)


   def main():
      # === CONFIGURACIÓN DEL USUARIO (personalizable por cada ejecución) ===
      expected_args = 4  # Cambiar este valor según los inputs esperados
      usage_message = "Uso: python main.py <thermal_video> <normal_video> <output_zip>" # Cambiar según el uso esperado

      if len(sys.argv) != expected_args:
         print(usage_message)
         sys.exit(1)


      # EJEMPLO: PERSONALIZAR EN FUNCIÓN DEL ALGORITMO/S A EJECUTAR
      thermal_video = Path(sys.argv[1])
      normal_video = Path(sys.argv[2])
      output_zip = Path(sys.argv[3])
      base_path = Path(__file__).parent

      with tempfile.TemporaryDirectory() as temp_dir:
         temp_dir_path = Path(temp_dir)

         # ===== PASOS PERSONALIZABLES =====

         # 1. Ejecutar thermal_detection_from_video.py
         run_script(
               base_path / "thermal_detection_from_video.py",
               [str(thermal_video), str(temp_dir_path)]
         )

         # 2. Ejecutar tracking_from_video.py
         run_script(
               base_path / "tracking_from_video.py",
               [str(normal_video), str(temp_dir_path)]
         )

         # 3. Ejecutar compare_cvs.py (requiere 4 argumentos: csv, csv, video, video)
         shutil.copy(base_path / "compare_cvs.py", temp_dir_path)  # Copiar al entorno temporal

         run_script(
               temp_dir_path / "compare_cvs.py",
               [
                  str(temp_dir_path / "detections_csi.csv"),
                  str(temp_dir_path / "detections_thermal.csv"),
                  str(temp_dir_path / "output.mp4"),
                  str(temp_dir_path / "output_termico.mp4"),
               ],
               cwd=temp_dir_path
         )

         # 4. En este caso, comprime solo la carpeta 'incident_frames'
         incident_frames_dir = temp_dir_path / "incident_frames"
         incident_zip_path = temp_dir_path / "incident_frames.zip"

         if not incident_frames_dir.exists() or not incident_frames_dir.is_dir():
               print("No se encontró la carpeta 'incident_frames'. Nada que empaquetar.")
               sys.exit(0)

         zip_directory(incident_frames_dir, incident_zip_path)
         print(f"Carpeta 'incident_frames/' comprimida en: {incident_zip_path}")

         # 5. Crear el archivo ZIP final
         with zipfile.ZipFile(output_zip, 'w') as zipf:
               zipf.write(incident_zip_path, arcname="incident_frames.zip")

         print(f"Archivo ZIP final creado en: {output_zip}")


         # Esto es imprescindible si queremos que se ejecute al poner python main.py <args>
         if __name__ == "__main__":
            main()
   ```

   En este _main.py_ de ejemplo:

   - Se ejecuta primero el algoritmo _thermal_detection.py_, con un video (recogido de los argumentos del main) y una carpeta donde guardar el resultado (en este caso una carpeta temporal) como argumentos.
   - Más tarde, se ejecuta _tracking_from_video.py_, con otro video (recogido de los argumentos del main) y la carpeta donde guardar el resultado (en este caso, la misma carpeta temporal) como argumentos
   - Ejecuta el algoritmo _compare_cvs.py_ con las salidas de los algoritmos anteriores como argumentos. Al haberse guardado en el directorio temporal, porque no nos interesan esos archivos intermedios, es muy fácil acceder a ellos, aunque hemos realizado al principio una copia de este algoritmo en el directorio temporal. Una vez ejecutado esto, se genera la carpeta _/incident_frames_ en el directorio temporal
   - Se crea un zip que contendrá todos los incident frames, y se usa una función para crear esta carpeta comprimida.
   - Se crea el archivo final zip que contendrá, en este caso, solo esta carpeta comprimida con los incident_frames

   Por supuesto, todos los scripts se encuentran en la misma carpeta que el script _main.py_, que se ha subido como archivo del algoritmo. De lo contrario, sería imposible su ejecución, como es lógico.

3. Para subir el algoritmo deberemos comprimir, como ya se ha indicado, todos los scripts en una carpeta junto al script que será el entrypoint. Deberemos estar logueados en la aplicación como administradores y entrar al proyecto en cuestión. Ahí, le tendremos que dar al botón de gestionar algoritmos, donde se nos aparecerá la lista de algoritmos disponibles para ese proyecto.

4. Ahí encontraremos también un botón de **Crear nuevo algoritmo**. Le daremos y deberemos de rellenar información sobre el algoritmo, añadiendo el zip que hemos creado y marcando cuál será el entrypoint (o archivo principal a ejecutar por el ordenador). Como opciones más importantes, deberemos asegurarnos de qué tipos de archivo admite y de si este algoritmo debe recibir uno o dos archivos.

## ¿Cómo hacer que funcione la aplicación?

- Lanzar aplicación

python manage.py runserver

- Lanzar celery

celery -A algovision worker --loglevel=info

- Lanzar redis

redis-server

- Lanzar monitoreo web Celery

celery -A algovision flower --port=5555

## How to test if my script is executable with the virtual environment I've created?

This guide walks you through **how to check if your Python script can execute**, even on a brand-new system, by creating a virtual environment, installing dependencies, and verifying imports.

---

## 🧩 1. Create a project folder and save files

This guide assumes **nothing is installed**. It shows how to:

1. Install Python (if needed)
2. Create a virtual environment (`.venv`)
3. Install dependencies from `requirements.txt`
4. Verify imports dynamically
5. Test-run your script safely

---

## 📁 Files to Prepare

Inside a folder you will create (e.g., `thermal_test/`), you eed to place these two files:

### `requirements.txt`

You'll need to download it from the webpage to see the actual one (or take the default requirements.txt is included in the source code)

To download it:

1. You need to log into a project with an administrator user.
2. This will open the dashboard, and you have to click on Gestionar Algoritmos.
3. Click on Editar Requerimientos Globales
4. Click on Descargar archivo

### `thermal_script.py`

> Your actual script (the one you want to test if it has the correct packages installed).
> For this example, it will be used as python thermal_script.py video_name folder.zip

## 🐧 A — macOS / Linux Step-by-Step

```bash
# 1) (Optional) Install system Python if missing
# macOS: use installer from python.org or Homebrew
# Linux (Debian/Ubuntu):

sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# 2) Create project folder
mkdir -p ~/thermal_test && cd ~/thermal_test

# (Place requirements.txt, and thermal_script.py here)

# 3) Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4) Confirm Python path
python -V
which python

# 5) Upgrade pip/tools
python -m pip install --upgrade pip setuptools wheel

# 6) (Optional) Dry-run dependency resolution
pip install --dry-run -r requirements.txt || true

# 7) Install requirements
pip install -r requirements.txt

# 8) Check environment
pip check
pip freeze | sed -n '1,20p'

# 9) Run your script (example)
python thermal_script.py /path/to/input.ext ./outdir

# 10) If an error appears, just add it to .venv using

ModuleNotFoundError: No module named 'tensorflow'

## Note: Maybe you will need to search in the internet for the error and it will tell you what package do you need to install, executing:
pip install package_name

## Repeat this until all packages needed are installed and script executes perfectly. Once it does, go to TODO

```

---

## 🪟 B — Windows (PowerShell)

```powershell
# 1) Install Python: https://www.python.org/downloads (check "Add Python to PATH")

# 2) Create project folder
mkdir C:\thermal_test
Set-Location C:\thermal_test

# 3) Create and activate venv
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
# If blocked:
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force

# 4) Confirm Python
python -V
Get-Command python | Select-Object -ExpandProperty Source

# 5) Upgrade pip/tools
python -m pip install --upgrade pip setuptools wheel

# 6) (Optional) Dry-run dependencies
pip install --dry-run -r requirements.txt 2>$null ; if ($LASTEXITCODE -ne 0) { Write-Host "dry-run failed or unsupported" }

# 7) Install requirements
pip install -r requirements.txt

# 8) Check environment
pip check
pip freeze | Select-Object -First 20

# 9) Run your script
python thermal_script.py C:\path\to\input.mp4 .\outdir

# 10) If an error appears, just add it to .venv using
pip install package_name

# Maybe you will need to search in the internet for the error and it will tell you what package do you need to install
```

### Once your script is ready to run

You have run your script and it works. You now need to upload your new requirements to the virtual environment of the webapp. For this:

1. Execute pip freeze > requirements.txt with the virtual environment activated to generate the new file.
2. As for the download, log in as administrator in a project.
3. This will open the dashboard, and you have to click on Gestionar Algoritmos.
4. Click on Editar Requerimientos Globales.
5. Click on Subir archivo.
6. Now the webapp should be able to execute your script.

---

## 🔧 Troubleshooting

```bash
# If pip fails (Linux)
sudo apt install -y build-essential libgl1-mesa-dev libjpeg-dev

# Force reinstall a package
pip install --force-reinstall opencv-python

# Show detailed logs
pip install -r requirements.txt -v

# Check dependency conflicts
pip check
```

## Creating algorithms for the photovoltaic menu: scripts, structure, files...

### Choose a model and download the files, the structure should be something like this (after you have cloned the [Tensorflow models folder from github](placeholder-link) and eliminated all folders which are not the research/, as it contains the utils we use to analyze images):

```markdown
X_detector/
├── models/
│ └── research/
│ └── object_detection/
│ └── detection.py # Key file
│
├── workspace_X/ # You should have as many of this as models of detectors you want (hotspots, panels, hotspots + panels...etc)
│ ├── data/
│ │ └── L2/
│ │ └── label_map.pbtxt
│ │
│ └── saved_models/
│ ├── checkpoint/
│ ├── frozen_inference_graph.rb
│ ├── model.ckpt.data-00000-of-00001
│ ├── model.ckpt.index
│ ├── model.ckpt.meta
│ ├── pipeline.config
│ └── saved_model/
│ ├── variables/
│ └── saved_model.pb
│
└── main.py # Key file
```

I'll break down the folders in next steps, but it is crucial for you to have a similar structure to this.

### detection.py: It contains the code you need to detect objects in your images. THe structure should be something like this file, which is the detection file used for hotspot detection:

```python
import os
import numpy as np
from PIL import Image
import tensorflow as tf
from object_detection.utils import label_map_util, visualization_utils as vis_util #IMPORTANT: Maintain this path
import argparse
from PIL.ExifTags import TAGS

# ----------------------------- ARGUMENTS -----------------------------

parser = argparse.ArgumentParser(
    description="Hotspot detection using TensorFlow frozen model")
parser.add_argument("-hs_m", "--hotspots_saved_model_dir",
                    type=str, help="Hotspot model directory")
parser.add_argument("-hs_l", "--hotspots_label_map",
                    type=str, help="Hotspot label map path")
parser.add_argument("-i", "--input_image", type=str, help="Input image path")
parser.add_argument("-o", "--outputs_dir", type=str, help="Output directory")
parser.add_argument("--hotspot_thresh", type=float,
                    default=0.3, help="Hotspot detection threshold")
args = parser.parse_args()

# ----------------------------- UTILS -----------------------------


def load_graph(frozen_graph_path):
    graph = tf.Graph()
    with graph.as_default():
        graph_def = tf.compat.v1.GraphDef()
        with tf.io.gfile.GFile(frozen_graph_path, 'rb') as f:
            graph_def.ParseFromString(f.read())
            tf.import_graph_def(graph_def, name='')
    return graph


def load_image_np(image_path):
    return np.array(Image.open(image_path)).astype(np.uint8)


def get_exif_gps(image):
    try:
        exif = image._getexif()
        if not exif:
            return "N/A"
        decoded = {TAGS.get(k, k): v for k, v in exif.items()}
        gps = decoded.get('GPSInfo')
        if not gps:
            return "N/A"
        return '{0} {1} {2} {3}, {4} {5} {6} {7}'.format(
            gps[2][0], gps[2][1], gps[2][2], gps[1],
            gps[4][0], gps[4][1], gps[4][2], gps[3]
        )
    except:
        return "N/A"

# ----------------------------- LOAD MODEL -----------------------------


hotspots_graph = load_graph(os.path.join(
    args.hotspots_saved_model_dir, 'frozen_inference_graph.pb'))
hotspots_category_index = label_map_util.create_category_index_from_labelmap(
    args.hotspots_label_map, use_display_name=True
)

os.makedirs(args.outputs_dir, exist_ok=True)
csv_path = os.path.join(args.outputs_dir, "outputs.csv")
csv = open(csv_path, "w")
csv.write("image,GPS\n")

# ----------------------------- PROCESS SINGLE IMAGE -----------------------------

img_path = args.input_image
img_name = os.path.basename(img_path)
base_name = os.path.splitext(img_name)[0]

image_np = load_image_np(img_path)
image_expanded = np.expand_dims(image_np, axis=0)

gps = get_exif_gps(Image.open(img_path))
csv.write(f"{base_name},{gps}\n")

with hotspots_graph.as_default():
    with tf.compat.v1.Session(graph=hotspots_graph) as sess:
        image_tensor = hotspots_graph.get_tensor_by_name('image_tensor:0')
        boxes = hotspots_graph.get_tensor_by_name('detection_boxes:0')
        scores = hotspots_graph.get_tensor_by_name('detection_scores:0')
        classes = hotspots_graph.get_tensor_by_name('detection_classes:0')
        num_detections = hotspots_graph.get_tensor_by_name('num_detections:0')

        out_boxes, out_scores, out_classes, out_num = sess.run(
            [boxes, scores, classes, num_detections],
            feed_dict={image_tensor: image_expanded}
        )

        out_boxes = np.squeeze(out_boxes)
        out_scores = np.squeeze(out_scores)
        out_classes = np.squeeze(out_classes).astype(int)

        valid = np.where(out_scores >= args.hotspot_thresh)[0]

        if len(valid) == 0:
            csv.close()
            print("No hotspots detected.")
            exit(0)

        output_dir = os.path.join(args.outputs_dir, base_name)
        os.makedirs(output_dir, exist_ok=True)

        # Crop each detected hotspot
        h, w = image_np.shape[:2]
        hotspot_num = 0

        for i in valid:
            hotspot_num += 1
            ymin, xmin, ymax, xmax = out_boxes[i]
            ymin, xmin, ymax, xmax = int(
                ymin * h), int(xmin * w), int(ymax * h), int(xmax * w)
            crop = image_np[ymin:ymax, xmin:xmax]
            Image.fromarray(crop).save(os.path.join(
                output_dir, f"{base_name}_hs{hotspot_num}.jpg"))

        # Draw detections on full image
        vis_util.visualize_boxes_and_labels_on_image_array(
            image_np,
            out_boxes[valid],
            out_classes[valid],
            out_scores[valid],
            hotspots_category_index,
            use_normalized_coordinates=True,
            line_thickness=3,
            min_score_thresh=args.hotspot_thresh
        )

        Image.fromarray(image_np).save(
            os.path.join(output_dir, f"{base_name}.jpg"))

csv.close()
print(f"Hotspot detections saved in: {args.outputs_dir}")
```

As you can see, there are several modules:

- Argument module: It loads everything related to location of the files
- Utils: Auxiliar functions which are used later
- Load model: It loads the model from the paths defined in the arguments (Ideally, the ones from step 1)
- Process image: This is the part of image processing and savinf the data in outputs.

This detection.py could work on itself by executing it, but for commodity and standarization of the app, I've decided to create a main.py file, explained in the next section, that controls with which arguments this file is called.

_Note: Some little tweaks should be made in order to have the correct naming for panel detection instead of hotspots, but technically you could load the panel model, and put the panel files in those folders with those names and you could make it work. For convenience, I recommend NOT to do it, and create that structure for every algorithm and change a bit the namings in detection.py / main.py, for exportability and standarization reasons_

### main.py

```python
import sys
import subprocess
import tempfile
from pathlib import Path
import zipfile
import os


def main():
    if len(sys.argv) != 3:
        print("Uso: python main.py <input_image> <output_zip>")
        sys.exit(1)

    input_image = Path(sys.argv[1])
    output_zip = Path(sys.argv[2])
    base_path = Path(__file__).parent

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        outputs_dir = temp_dir / "detections"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run([
                sys.executable,
                "-m", "object_detection.detection",
                "-hs_m", str(base_path / "workspace_hotspots/saved_models"),
                "-hs_l", str(base_path /
                             "workspace_hotspots/data/L2/label_map.pbtxt"),
                "-i", str(input_image),
                "-o", str(outputs_dir)
            ],
                check=True,
                env={**os.environ,
                     "PYTHONPATH": str(base_path / "models/research")}
            )

            with zipfile.ZipFile(output_zip, 'w') as zipf:
                for file in outputs_dir.rglob('*'):
                    zipf.write(file, arcname=file.relative_to(outputs_dir))

            print(f"ZIP de salida creado: {output_zip}")

        except subprocess.CalledProcessError as e:
            print(f"Error ejecutando detection.py: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

```

This `main.py` file is similar to the ones described on the general one but including the paths of the image to analyze and the detection module.

### workspace_X/: This folder contains two subfolders

- data/L2: This contains the file `label_map.pbtxt`, which has in it the labels for the distinct hotspots/panels
- saved_models/: This is where your model should be contained

### Once you have these files and folders, you can compile these three (`workspace_X/`, `models/`, `main.py`) into a _.zip_ file and upload them as an algorithm into the application.
