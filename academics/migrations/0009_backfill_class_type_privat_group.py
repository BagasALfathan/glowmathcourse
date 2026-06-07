"""Data migration: convert the deprecated REGULAR class_type into PRIVAT or
GROUP based on capacity.

- capacity == 1 -> PRIVAT
- capacity >  1 -> GROUP

GANJIL_GENAP rows are left alone. New rows default to GROUP.
"""
from django.db import migrations


def backfill_class_type(apps, schema_editor):
    Kelas = apps.get_model('academics', 'Kelas')
    qs = Kelas.objects.filter(class_type='REGULAR')
    qs.filter(capacity=1).update(class_type='PRIVAT')
    qs.exclude(capacity=1).update(class_type='GROUP')


def reverse_noop(apps, schema_editor):
    # Reverse intentionally a no-op: the original distinction (REGULAR) is
    # already lost in PRIVAT/GROUP semantics; restoring would collapse the
    # information.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0008_alter_kelas_class_type'),
    ]

    operations = [
        migrations.RunPython(backfill_class_type, reverse_noop),
    ]
