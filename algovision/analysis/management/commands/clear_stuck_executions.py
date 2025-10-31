from django.core.management.base import BaseCommand
from django.utils import timezone
from analysis.models import Execution
from datetime import timedelta


class Command(BaseCommand):
    help = 'Marca como FAILED las ejecuciones que llevan demasiado tiempo PENDING'

    def handle(self, *args, **options):
        timeout = timedelta(minutes=30)
        now = timezone.now()

        stuck_executions = Execution.objects.filter(
            status="PENDING",
            execution_date__lt=now - timeout
        )

        count = stuck_executions.count()
        ids = list(stuck_executions.values_list('id', flat=True))
        stuck_executions.update(status="FAILED")

        if ids:
            self.stdout.write(
                f"{count} ejecuciones marcadas como FAILED: {ids}"
            )
        else:
            self.stdout.write(
                "No hay ejecuciones pendientes que hayan superado el timeout.")
