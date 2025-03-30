from django.core.paginator import (
    EmptyPage,
    PageNotAnInteger,
    Paginator,
)
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page

from api.models import Post


def index(request):
    post_list = (
        Post.objects.filter(show_in_main_page=True)
        .order_by("-creation_date")
        .select_related("user")
    )
    paginator = Paginator(post_list, 5)
    page = request.GET.get("page")
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    return render(request, "mog/index.html", {"posts": posts})


def faq(request):
    return render(request, "mog/faq.html")


def privacy(request):
    return render(request, "mog/privacy.html")


def health(request):
    return HttpResponse("OK")


@cache_page(24 * 60 * 60)
def robotstxt(request):
    content = render_to_string("mog/robots.txt")
    response = HttpResponse(content, content_type="text/plain")
    response["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
    return response
