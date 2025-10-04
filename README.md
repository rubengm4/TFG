# TFG

Trabajo de Fin de Grado

## Autor: Rubén Argenta García

## ¿Cómo añadir un nuevo proyecto?

1. Añadirlo a la base de datos
2. En _accounts/views.py_, añadir en la clase **SetSourceAndRedirectToLogin**, dentro de la función _post(self, request: HttpRequest):_ sustituyendo _example_project_ por nuestro nombre de proyecto (**manteniendo el sufijo _-home_**):

   ```python
    elif source == 'example-project':
        return redirect('example_project_home')
   ```

3. En _algovision/urls.py_, añadir la siguiente línea, sustituyendo _example_project_ por nuestro nombre de proyecto (**manteniendo el sufijo _-home_**):
   ```python
   path('example-project-home/', LoginHomeView.as_view(), name='example_project_home'),
   ```
4. En _fv_analysis/templates/index.html_, añadir un elemento similar al siguiente, para crear un botón con un enlace al nuevo proyecto, cambiando Example y _value="example-project"_ por el nombre del proyecto:

   ```html
   <div class="col-auto">
     <form method="post" action="{% url 'accounts:set_source' %}">
       {% csrf_token %}
       <input type="hidden" name="source" value="example-project" />
       <button type="submit" class="btn btn-primary px-4">Example</button>
     </form>
   </div>
   ```

5. Es importante crear un usuario para este nuevo proyecto o dar permisos a un administrador. En caso negativo, no nos dejará entrar al proyecto.

El resto de la funcionalidad es común a cualquier proyecto, por lo que con estos simples pasos debería ser suficiente para añadir un nuevo proyecto. Es muy importante ser lo más fiel posible a la nomenclatura reflejada en estos pasos.

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
