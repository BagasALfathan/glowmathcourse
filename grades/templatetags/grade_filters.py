"""Template filters for Grade display.

The Gradebook (Phase 3B) stores assessment title as a `[title] :: catatan`
prefix inside Grade.notes because the model has no separate title field
(ERD v4 locked, no migration). Anywhere we render `{{ grade.notes }}` for
end-users we should strip the prefix to avoid showing raw markup like
`[Ulangan Bab 3] :: Bagus`.

Three student-facing templates currently render notes raw:
- templates/components/_grade_table.html
- grades/templates/grades/_progress_report_body.html
- grades/templates/grades/print_my_grades.html

Apply `{{ grade.notes|grade_note }}` (strips prefix) and/or
`{{ grade.notes|grade_title }}` (returns just the title prefix) when
fixing those views in a follow-up.
"""
import re

from django import template

register = template.Library()

_NOTES_TITLE_RE = re.compile(r'^\[(?P<title>.+?)\]\s*::\s?(?P<note>.*)$', re.DOTALL)


def _parse(notes):
    if not notes:
        return None, ''
    m = _NOTES_TITLE_RE.match(notes)
    if m:
        return m.group('title'), m.group('note')
    return None, notes


@register.filter(name='grade_note')
def grade_note(notes):
    """Strip the `[title] ::` prefix and return just the comment portion."""
    _, note = _parse(notes)
    return note


@register.filter(name='grade_title')
def grade_title(notes):
    """Return just the title portion of a `[title] :: note` string,
    or empty string if no prefix present."""
    title, _ = _parse(notes)
    return title or ''
