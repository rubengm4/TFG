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

10. Now our project will be configured correctly and appearing in the frontend, so we can now access with our administrator or create a new user. But the project can be accessed from now on.

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
