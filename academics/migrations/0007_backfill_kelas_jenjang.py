"""Data migration: backfill one KelasJenjang row per existing Kelas.

After this migration, every existing Kelas has at least one KelasJenjang row
whose level mirrors the legacy Kelas.level field. New rows are created via
Kelas.set_jenjang() in the create/edit views going forward.
"""
from django.db import migrations


def backfill_kelas_jenjang(apps, schema_editor):
    Kelas = apps.get_model('academics', 'Kelas')
    KelasJenjang = apps.get_model('academics', 'KelasJenjang')

    to_create = []
    for kelas in Kelas.objects.all().only('id', 'level'):
        if not kelas.level:
            continue
        # Skip if a row already exists (idempotent rerun safety).
        if KelasJenjang.objects.filter(kelas_id=kelas.id, level=kelas.level).exists():
            continue
        to_create.append(KelasJenjang(kelas_id=kelas.id, level=kelas.level))

    if to_create:
        KelasJenjang.objects.bulk_create(to_create)


def reverse_noop(apps, schema_editor):
    # Reverse is intentionally a no-op so unmigrating doesn't wipe
    # KelasJenjang rows that may have been edited after the backfill.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0006_kelas_class_type_kelasjenjang'),
    ]

    operations = [
        migrations.RunPython(backfill_kelas_jenjang, reverse_noop),
    ]
