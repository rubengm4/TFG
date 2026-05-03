from pathlib import Path

from django.conf import settings
from django.core.files import File as DjangoFile
from django.core.management.base import BaseCommand

from analysis.models import Algorithm, Project

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

        algo = Algorithm(
            name=name,
            version=version,
            description=description,
            project=project
        )

        algo.save()
        if file_path:
            full_path = Path(settings.MEDIA_ROOT) / "algorithms" / file_path
            if not full_path.is_file():
                self.stderr.write(
                    f"Advertencia: el archivo '{full_path}' no existe en el sistema.")
            else:
                with full_path.open("rb") as fh:
                    algo.archive.save("archive.zip", DjangoFile(fh), save=True)
        self.stdout.write(self.style.SUCCESS(
            f'\nAlgoritmo "{algo.name}" creado correctamente con ID {algo.id}.'))
