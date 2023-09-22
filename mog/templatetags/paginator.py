import urllib.parse

from django import template
from django.utils.html import mark_safe

register = template.Library()


def encode_parameters(page_number, query):
    query = dict((k, v.encode("utf8")) for k, v in query.items())
    return "?" + urllib.parse.urlencode(dict(query, page=page_number))


@register.filter(needs_autoscape=True)
def paginate(page, query=None):
    paginator = page.paginator
    footer = min(10, paginator.num_pages)
    first = footer * ((page.number - 1) // footer) + 1
    last = min(paginator.num_pages, first + footer - 1)
    query = query or {}

    html = '<ul class="pagination">'
    html += '<li class="{0}"><a href="{1}">&#171</a></li>'.format(
        "" if page.has_previous() else "disabled",
        encode_parameters(page.previous_page_number(), query)
        if page.has_previous()
        else "#",
    )

    for number in range(first, last + 1):
        if page.number == number:
            html += '<li class="active"><a>{0}</a></li>'.format(number)
        else:
            html += '<li><a href="{0}">{1}</a></li>'.format(
                encode_parameters(number, query), number
            )

    html += '<li class="{0}"><a href="{1}">&#187</a></li>'.format(
        "" if page.has_next() else "disabled",
        encode_parameters(page.next_page_number(), query) if page.has_next() else "#",
    )

    html += "</ul>"

    return mark_safe(html)
