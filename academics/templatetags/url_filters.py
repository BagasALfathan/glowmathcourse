from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def querystring_replace(query_dict, **kwargs):
    """Replace/add params in a QueryDict, return URL-encoded string.

    Usage:  ?{% querystring_replace request.GET page=2 sort='popular' %}

    Passing value=None or '' removes the key entirely. Useful for keeping
    filter state intact while toggling sort/page.
    """
    qd = query_dict.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            qd.pop(key, None)
        else:
            qd[key] = value
    return mark_safe(qd.urlencode())
