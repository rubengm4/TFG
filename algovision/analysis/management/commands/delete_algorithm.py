from django.core.management.base import BaseCommand
from analysis.models import Algorithm


class Command(BaseCommand):
    help = 'Borrar un algoritmo por ID'

    def handle(self, *args, **options):
        try:
            algo_id = int(input("ID del algoritmo a borrar: ").strip())
        except ValueError:
            self.stderr.write("ID inválido. Abortando.")
            return

        try:
            algo = Algorithm.objects.get(id=algo_id)
        except Algorithm.DoesNotExist:
            self.stderr.write(f"No existe algoritmo con ID {algo_id}.")
            return

        confirm = input(
            f"¿Seguro que quieres borrar el algoritmo '{algo.name}' con ID {algo.id}? (sí/no): ").strip().lower()
        if confirm in ['sí', 'si', 's', 'yes', 'y']:
            algo.delete()
            self.stdout.write(self.style.SUCCESS(
                f'Algoritmo con ID {algo_id} borrado correctamente.'))
        else:
            self.stdout.write("Borrado cancelado.")
