from django.core.management.base import BaseCommand
from fv_analysis.models import Algorithm


class Command(BaseCommand):
    help = 'Modificar un algoritmo existente preguntando por campos. Dejar vacío para no modificar.'

    def handle(self, *args, **options):
        try:
            algo_id = int(input("ID del algoritmo a modificar: ").strip())
        except ValueError:
            self.stderr.write("ID inválido. Abortando.")
            return

        try:
            algo = Algorithm.objects.get(id=algo_id)
        except Algorithm.DoesNotExist:
            self.stderr.write(f"No existe algoritmo con ID {algo_id}.")
            return

        self.stdout.write(
            f'Modificando algoritmo "{algo.name}" (ID: {algo.id}). Dejar vacío para mantener valor actual.')

        name = input(f"Nuevo nombre [{algo.name}]: ").strip()
        version = input(f"Nueva versión [{algo.version}]: ").strip()
        description = input(
            f"Nueva descripción [{algo.description}]: ").strip()
        file_path = input(
            f"Nuevo archivo (ruta relativa a MEDIA_ROOT) [{algo.file.name if algo.file else 'sin archivo'}]: ").strip()

        if name:
            algo.name = name
        if version:
            algo.version = version
        if description:
            algo.description = description
        if file_path:
            algo.file.name = file_path

        algo.save()
        self.stdout.write(self.style.SUCCESS(
            f'Algoritmo "{algo.name}" actualizado correctamente.'))
