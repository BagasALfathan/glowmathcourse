from django.db import migrations


_EMOJI_TABLE = (
    ('matematika', '🧮'),
    ('fisika', '⚛️'),
    ('kimia', '🧪'),
    ('biologi', '🧬'),
    ('inggris', '🇬🇧'),
    ('indonesia', '🇮🇩'),
    ('ekonomi', '💰'),
    ('sejarah', '📜'),
    ('geografi', '🌍'),
    ('seni', '🎨'),
    ('pkn', '⚖️'),
    ('koding', '💻'),
    ('coding', '💻'),
    ('komputer', '💻'),
)


def _emoji_for(name: str) -> str:
    if not name:
        return ''
    s = str(name).lower()
    for needle, emoji in _EMOJI_TABLE:
        if needle in s:
            return emoji
    return '📚'


def forwards(apps, schema_editor):
    Subject = apps.get_model('academics', 'Subject')
    for subj in Subject.objects.filter(icon=''):
        Subject.objects.filter(pk=subj.pk).update(icon=_emoji_for(subj.name))


def backwards(apps, schema_editor):
    Subject = apps.get_model('academics', 'Subject')
    Subject.objects.update(icon='')


class Migration(migrations.Migration):
    dependencies = [
        ('academics', '0004_subject_icon'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
