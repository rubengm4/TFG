from django.core.management.base import BaseCommand
from analysis.models import Algorithm, Project
from django.conf import settings
import os


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
            f'\nModificando algoritmo "{algo.name}" (ID: {algo.id}). Dejar vacío para mantener valor actual.\n')

        name = input(f"Nuevo nombre [{algo.name}]: ").strip()
        version = input(f"Nueva versión [{algo.version}]: ").strip()
        description = input(
            f"Nueva descripción [{algo.description}]: ").strip()
        file_path = input(
            f"Nuevo archivo (relativa a MEDIA_ROOT/algorithms) [{algo.file.name if algo.file else 'sin archivo'}]: ").strip()

        # Mostrar proyectos
        proyectos = Project.objects.all()
        self.stdout.write("\nProyectos disponibles:")
        for proyecto in proyectos:
            selected = " (actual)" if proyecto == algo.project else ""
            self.stdout.write(f"{proyecto.id}: {proyecto.title}{selected}")

        project_id = input(
            f"\nID del nuevo proyecto [{algo.project.id}]: ").strip()

        if name:
            algo.name = name
        if version:
            algo.version = version
        if description:
            algo.description = description
        if file_path:
            full_path = os.path.join(
                settings.MEDIA_ROOT, 'algorithms', file_path)
            if not os.path.exists(full_path):
                self.stderr.write(
                    f"Advertencia: el archivo '{full_path}' no existe en el sistema.")
            algo.file.name = f"algorithms/{file_path}"

        if project_id:
            try:
                new_project = Project.objects.get(id=project_id)
                algo.project = new_project
            except Project.DoesNotExist:
                self.stderr.write(
                    "ID de proyecto no válido. Se mantendrá el proyecto actual.")

        algo.save()
        self.stdout.write(self.style.SUCCESS(
            f'\nAlgoritmo "{algo.name}" (ID: {algo.id}) actualizado correctamente.'))
