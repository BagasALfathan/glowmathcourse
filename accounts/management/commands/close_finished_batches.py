"""Cron-friendly batch sweep.

Walks every non-deleted Kelas, calls
sessions_app.services.sweep_finished_batches(kelas), and reports how many
enrollments were auto-completed. The kelas stays OPEN (CLOSED is now a
manual teacher action meaning the slot is retired).

Run daily in production:
    python manage.py close_finished_batches

Local dev / one-off:
    python manage.py close_finished_batches --verbose
"""
from django.core.management.base import BaseCommand

from academics.models import Kelas
from sessions_app.services import batch_state, sweep_finished_batches


class Command(BaseCommand):
    help = (
        'Sweep every kelas: enrollments whose batch window has ended flip '
        'to COMPLETED, the slot reopens automatically.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose', action='store_true',
            help='Print one line per kelas swept.',
        )

    def handle(self, *args, **opts):
        verbose = bool(opts.get('verbose'))
        total_flipped = 0
        kelas_count = 0
        swept_count = 0

        for kelas in Kelas.objects.filter(is_deleted=False).only('id', 'name'):
            kelas_count += 1
            try:
                n = sweep_finished_batches(kelas)
            except Exception as e:
                self.stderr.write(
                    f'  ! sweep failed for kelas {kelas.pk} "{kelas.name}": {e}'
                )
                continue
            if n:
                total_flipped += n
                swept_count += 1
                if verbose:
                    self.stdout.write(
                        f'  - {kelas.name}: {n} enrollment(s) auto-completed'
                    )

        self.stdout.write(self.style.SUCCESS(
            f'\nSwept {swept_count} of {kelas_count} kelas. '
            f'{total_flipped} enrollment(s) flipped to COMPLETED.'
        ))
