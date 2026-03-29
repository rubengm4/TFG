from django.core.management.base import BaseCommand
from analysis.models import Algorithm, Project
from django.conf import settings
import os
from typing import Any


class Command(BaseCommand):
    help = 'Crear un algoritmo nuevo preguntando por name, version, description, file y proyecto asociado.'

    def handle(self, *args: Any, **options: Any):
        self.stdout.write("Creando un nuevo algoritmo.\n")

        name = input("Nombre: ").strip()
        version = input("Versión (por defecto 1.0): ").strip() or '1.0'
        description = input("Descripción: ").strip()
        file_path = input(
            "Ruta del archivo (relativa a MEDIA_ROOT/algorithms, o dejar vacío si no tiene archivo): ").strip()

        # Lists available projects
        proyectos = Project.objects.all()
        if not proyectos.exists():
            self.stderr.write(
                "No hay proyectos disponibles. Crea uno antes de continuar.")
            return

        self.stdout.write("\nProyectos disponibles:")
        for proyecto in proyectos:
            self.stdout.write(f"{proyecto.id}: {proyecto.title}")

        project_id = input("\nID del proyecto asociado: ").strip()
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            self.stderr.write("Proyecto no encontrado. Abortando.")
            return

        # Creates the algorithm with the provided data, associating the file if a path is given (but not uploading it, just associating its relative path to MEDIA_ROOT)
        algo = Algorithm(
            name=name,
            version=version,
            description=description,
            project=project
        )

        if file_path:
            full_path = os.path.join(
                settings.MEDIA_ROOT, 'algorithms', file_path)
            if not os.path.exists(full_path):
                self.stderr.write(
                    f"Advertencia: el archivo '{full_path}' no existe en el sistema.")
            # This doesn't upload the file, it just associates its relative path to MEDIA_ROOT
            algo.file.name = f"algorithms/{file_path}"

        algo.save()
        self.stdout.write(self.style.SUCCESS(
            f'\nAlgoritmo "{algo.name}" creado correctamente con ID {algo.id}.'))
