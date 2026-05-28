from django import template
from django.utils.safestring import mark_safe

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


@register.simple_tag
def star_rating(value, size=12, show_number=False, show_count=False, count=None):
    """Render visually accurate fractional star rating via CSS overlay.

    Two stacked spans: gray base (5 stars) + amber overlay clipped to
    (value / 5) * 100% width. Result: 4.7 looks like 4.7, not 5.0.

    Usage:
        {% star_rating teacher.avg_rating %}
        {% star_rating teacher.avg_rating size=14 %}
        {% star_rating teacher.avg_rating size=12 show_number=True show_count=True count=teacher.rating_count %}
    """
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0
    pct = min(100.0, max(0.0, (value / 5.0) * 100.0))
    size = int(size)
    # 5 chars at `size`px plus a tiny letter-spacing budget. Slightly over-wide is fine.
    width = size * 5 + 6
    line_height = size + 2
    star_html = (
        f'<span class="sr-wrap" style="display:inline-block;position:relative;'
        f'width:{width}px;height:{line_height}px;line-height:{line_height}px;vertical-align:middle">'
        f'<span class="sr-bg" style="position:absolute;top:0;left:0;color:#e5e7eb;'
        f'font-size:{size}px;letter-spacing:1px;line-height:{line_height}px">&#9733;&#9733;&#9733;&#9733;&#9733;</span>'
        f'<span class="sr-fg" style="position:absolute;top:0;left:0;color:#f59e0b;'
        f'font-size:{size}px;letter-spacing:1px;line-height:{line_height}px;'
        f'width:{pct:.1f}%;overflow:hidden;white-space:nowrap">&#9733;&#9733;&#9733;&#9733;&#9733;</span>'
        f'</span>'
    )
    parts = [star_html]
    if show_number:
        if value > 0:
            parts.append(
                f'<b style="font-size:11px;color:#92400e;margin-left:4px">{value:.1f}</b>'
            )
        else:
            parts.append(
                '<b style="font-size:11px;color:#6b7280;margin-left:4px">Baru</b>'
            )
    if show_count:
        parts.append(
            f'<span style="font-size:10px;color:#b45309;margin-left:2px">({count or 0})</span>'
        )
    return mark_safe(''.join(parts))


@register.filter
def getitem(dictionary, key):
    """dict[key] lookup with int/str coercion fallback. Returns 0 if missing."""
    if dictionary is None:
        return 0
    try:
        return dictionary.get(key, dictionary.get(int(key), 0))
    except (ValueError, TypeError, AttributeError):
        return 0


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
