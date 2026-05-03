import random

from django.core.management.base import BaseCommand

from accounts.models import ApprovalStatus, Education, Level, Role, User


STUDENT_FIRST_NAMES = [
    'Andi', 'Budi', 'Citra', 'Dian', 'Eko', 'Fajar', 'Gita', 'Hana',
    'Indra', 'Joko', 'Kiki', 'Lina', 'Mita', 'Nanda', 'Oki', 'Putri',
    'Rafi', 'Sari', 'Tono', 'Umi', 'Vina', 'Wawan', 'Xena', 'Yogi', 'Zara',
    'Agus', 'Bayu', 'Cici', 'Dito', 'Elsa', 'Fani', 'Gilang', 'Hesti',
    'Ivan', 'Julia', 'Kevin', 'Lisa', 'Mario', 'Nina', 'Oscar',
    'Prita', 'Qori', 'Rizal', 'Sinta', 'Teguh', 'Ulfa', 'Vito', 'Wulan',
    'Yanti', 'Zaki',
]

STUDENT_LAST_NAMES = [
    'Pratama', 'Santoso', 'Wijaya', 'Kusuma', 'Hidayat', 'Rahayu',
    'Setiawan', 'Nugroho', 'Purnama', 'Hartono', 'Susanto', 'Wibowo',
    'Kurniawan', 'Hakim', 'Saputra', 'Lestari', 'Dewi', 'Utama',
    'Permana', 'Firmansyah',
]

TEACHER_FIRST_NAMES = [
    'Ahmad', 'Benny', 'Cahya', 'Dewi', 'Eko', 'Farida', 'Guntur',
    'Hendra', 'Irma', 'Jaya', 'Kartika', 'Lukman', 'Maya', 'Nuri',
    'Oka', 'Putro', 'Rini', 'Suharto', 'Tina', 'Umar',
]

TEACHER_LAST_NAMES = [
    'Budiman', 'Cahyono', 'Darmawan', 'Effendi', 'Fauzi', 'Gunawan',
    'Hasanah', 'Ibrahim', 'Jauhari', 'Kusno', 'Latif', 'Mahmud',
    'Nasution', 'Oesman', 'Prabowo', 'Qodir', 'Rachman', 'Salim',
    'Tanjung', 'Usman',
]

SCHOOLS = [
    'SDN 01 Merdeka', 'SDN 02 Nusantara', 'SDN 03 Bangsa',
    'SMPN 01 Harapan', 'SMPN 02 Cerdas', 'SMPN 03 Mandiri',
    'SMAN 01 Unggul', 'SMAN 02 Prestasi', 'SMAN 03 Gemilang',
]

SPECIALIZATIONS = [
    'Matematika', 'Fisika', 'Kimia', 'Biologi',
    'Bahasa Indonesia', 'Bahasa Inggris', 'Ekonomi', 'Sejarah',
]


class Command(BaseCommand):
    help = 'Generate dummy student and teacher accounts (student001-100, teacher001-100)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing dummy accounts before generating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted_s = User.objects.filter(username__startswith='student').delete()[0]
            deleted_t = User.objects.filter(username__startswith='teacher').delete()[0]
            self.stdout.write(f'Cleared {deleted_s} student and {deleted_t} teacher accounts.')

        self.stdout.write('Generating dummy accounts...\n')

        student_created = 0
        student_skipped = 0
        for i in range(1, 101):
            username = f'student{i:03d}'
            if User.objects.filter(username=username).exists():
                student_skipped += 1
                continue

            first = random.choice(STUDENT_FIRST_NAMES)
            last = random.choice(STUDENT_LAST_NAMES)
            level = random.choice([Level.SD, Level.SMP, Level.SMA])

            if level == Level.SD:
                grade = random.randint(1, 6)
                school = random.choice([s for s in SCHOOLS if s.startswith('SDN')])
            elif level == Level.SMP:
                grade = random.randint(7, 9)
                school = random.choice([s for s in SCHOOLS if s.startswith('SMPN')])
            else:
                grade = random.randint(10, 12)
                school = random.choice([s for s in SCHOOLS if s.startswith('SMAN')])

            user = User.objects.create_user(
                username=username,
                password='murid123',
                first_name=first,
                last_name=last,
                email=f'{username}@dummy.glow',
                role=Role.STUDENT,
                approval_status=ApprovalStatus.APPROVED,
            )
            user.student_profile.level = level
            user.student_profile.school_name = school
            user.student_profile.school_grade = grade
            user.student_profile.parent_name = f'Orang Tua {last}'
            user.student_profile.save()
            student_created += 1

        teacher_created = 0
        teacher_skipped = 0
        for i in range(1, 101):
            username = f'teacher{i:03d}'
            if User.objects.filter(username=username).exists():
                teacher_skipped += 1
                continue

            first = random.choice(TEACHER_FIRST_NAMES)
            last = random.choice(TEACHER_LAST_NAMES)

            user = User.objects.create_user(
                username=username,
                password='teacher123',
                first_name=first,
                last_name=last,
                email=f'{username}@dummy.glow',
                role=Role.TEACHER,
                approval_status=ApprovalStatus.APPROVED,
            )
            user.teacher_profile.specialization = random.choice(SPECIALIZATIONS)
            user.teacher_profile.education = random.choice([Education.S1, Education.S2])
            user.teacher_profile.experience_years = random.randint(1, 15)
            user.teacher_profile.save()
            teacher_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done! Students: {student_created} created, {student_skipped} skipped. '
            f'Teachers: {teacher_created} created, {teacher_skipped} skipped.'
        ))
        self.stdout.write('  Student password : murid123')
        self.stdout.write('  Teacher password : teacher123')
