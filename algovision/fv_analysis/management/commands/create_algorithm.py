from django.core.management.base import BaseCommand
from fv_analysis.models import Algorithm
from typing import Any


class Command(BaseCommand):
    help = 'Crear un algoritmo nuevo preguntando por name, version, description y file (ruta dentro de media).'

    def handle(self, *args: Any, **options: Any):
        self.stdout.write("Creando un nuevo algoritmo.")
        name = input("Nombre: ").strip()
        version = input("Versión: ").strip()
        description = input("Descripción: ").strip()
        file_path = input(
            "Ruta del archivo (relativa a MEDIA_ROOT/algorithms, o dejar vacío si no tiene archivo): ").strip()

        if not name:
            self.stderr.write("El nombre es obligatorio. Abortando.")
            return

        algo = Algorithm(
            name=name,
            version=version if version else '1.0',
            description=description,
        )

        if file_path:
            algo.file.name = f"algorithms/{file_path}"

        algo.save()
        self.stdout.write(self.style.SUCCESS(
            f'Algoritmo "{algo.name}" creado correctamente con ID {algo.id}.'))
