import datetime

from django.core.management.base import BaseCommand

from academics.models import AcademicPeriod, Category, Quarter, Subject


CATEGORIES = {
    'IPA': 'Ilmu Pengetahuan Alam',
    'IPS': 'Ilmu Pengetahuan Sosial',
    'Bahasa': 'Bahasa dan Sastra',
    'Umum': 'Mata Pelajaran Umum',
}

SUBJECTS = {
    'IPA': ['Matematika', 'Fisika', 'Kimia', 'Biologi'],
    'IPS': ['Ekonomi', 'Sejarah', 'Geografi'],
    'Bahasa': ['Bahasa Indonesia', 'Bahasa Inggris'],
    'Umum': ['PKN', 'Seni Budaya'],
}


class Command(BaseCommand):
    help = 'Seed initial categories, subjects, and academic period data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...\n')

        # ── Categories ──────────────────────────────────────
        cat_objects = {}
        for name, description in CATEGORIES.items():
            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'description': description},
            )
            cat_objects[name] = cat
            label = 'Dibuat' if created else 'Sudah ada'
            self.stdout.write(f'  {label}: Kategori "{name}"')

        # ── Subjects ─────────────────────────────────────────
        self.stdout.write('')
        for cat_name, subject_names in SUBJECTS.items():
            cat = cat_objects[cat_name]
            for subject_name in subject_names:
                _, created = Subject.objects.get_or_create(
                    name=subject_name,
                    category=cat,
                )
                label = 'Dibuat' if created else 'Sudah ada'
                self.stdout.write(f'  {label}: Mapel "{subject_name}" [{cat_name}]')

        # ── Academic Period ───────────────────────────────────
        self.stdout.write('')
        period, created = AcademicPeriod.objects.get_or_create(
            year='2026-2027',
            quarter=Quarter.Q1,
            defaults={
                'name': 'Q1 2026-2027',
                'start_date': datetime.date(2026, 1, 1),
                'end_date': datetime.date(2026, 3, 31),
                'is_active': True,
            },
        )
        label = 'Dibuat' if created else 'Sudah ada'
        self.stdout.write(f'  {label}: Periode "{period.name}"')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Seed data selesai.'))
        self.stdout.write(
            f'  Total: {Category.objects.count()} kategori, '
            f'{Subject.objects.count()} mata pelajaran, '
            f'{AcademicPeriod.objects.count()} periode akademik.'
        )
