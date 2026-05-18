from django import template

register = template.Library()


_MONTHS_ID = [
    '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]


@register.filter
def month_name(month_num):
    try:
        idx = int(month_num)
        return _MONTHS_ID[idx] if 1 <= idx <= 12 else str(month_num)
    except (ValueError, TypeError):
        return month_num


@register.filter
def subject_emoji(subject_name):
    """Render a relevant emoji for a subject, falling back to a book."""
    if not subject_name:
        return '📖'
    s = str(subject_name).lower()
    table = (
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
    for needle, emoji in table:
        if needle in s:
            return emoji
    return '📚'


@register.filter
def times(n):
    """Return range(n) — for repeating template blocks. Caps at 50 for safety."""
    try:
        return range(min(int(n), 50))
    except (ValueError, TypeError):
        return range(0)


@register.filter
def greeting_time(_ignored=None):
    """'pagi' / 'siang' / 'sore' / 'malam' based on the current local hour."""
    from django.utils import timezone
    hour = timezone.localtime().hour
    if 5 <= hour < 11:
        return 'pagi'
    if 11 <= hour < 15:
        return 'siang'
    if 15 <= hour < 18:
        return 'sore'
    return 'malam'
