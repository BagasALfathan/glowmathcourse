import io
from datetime import datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Backup all data to a JSON fixture file in backups/'

    def handle(self, *args, **options):
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        filename = backup_dir / f'backup_{timestamp}.json'

        buf = io.StringIO()
        call_command(
            'dumpdata',
            '--natural-foreign',
            '--natural-primary',
            '--indent', '2',
            '--exclude', 'contenttypes',
            '--exclude', 'auth.permission',
            stdout=buf,
        )

        filename.write_text(buf.getvalue(), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Backup berhasil disimpan: {filename}'))

        backups = sorted(backup_dir.glob('backup_*.json'))
        for old in backups[:-10]:
            old.unlink()
            self.stdout.write(f'Backup lama dihapus: {old.name}')
