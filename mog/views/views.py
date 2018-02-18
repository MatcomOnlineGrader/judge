from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render

from api.models import Post


def index(request):
    post_list = Post.objects.filter(show_in_main_page=True)\
        .order_by('-creation_date').select_related('user')
    paginator = Paginator(post_list, 5)
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    return render(request, 'mog/index.html', {
        'posts': posts
    })


def faq(request):
    return render(request, 'mog/faq.html')


def privacy(request):
    return render(request, 'mog/privacy.html')
