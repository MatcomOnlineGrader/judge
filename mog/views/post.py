from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View, generic

from api.models import Post, Comment
from mog.forms import PostForm
from mog.utils import user_is_admin


class PostListView(generic.ListView):
    paginate_by = 30
    template_name = 'mog/post/index.html'

    def get_queryset(self):
        return Post.objects.order_by('-creation_date')


class PostDetailView(View):
    def get(self, request, pk, slug, *args, **kwargs):
        post = get_object_or_404(Post, pk=pk)
        if post.slug != slug:
            return redirect('mog:post', pk=pk, slug=post.slug, permanent=True)
        if request.user.is_authenticated:
            post.update_seen_comments(request.user)
        return render(request, 'mog/post/detail.html', {
            'post': post,
        })

    @method_decorator(login_required)
    def post(self, request, pk, slug, *args, **kwargs):
        post = get_object_or_404(Post, pk=pk)
        if not post.can_be_commented_by(request.user):
            return HttpResponseForbidden()
        body = request.POST['body']
        if body:
            comment = Comment(user=request.user, post=post, body=body)
            comment.save()
            # Save post to put it on top of modified posts!
            post.save()
        return redirect('mog:post', pk=pk, slug=post.slug)


class PostCreateView(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render(request, 'mog/post/create.html', {
            'form': PostForm()
        })

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        form = PostForm(request.POST)
        if not form.is_valid():
            return render(request, 'mog/post/create.html', {
                'form': form
            })
        data = form.cleaned_data
        post = Post(
            name=data['name'],
            body=data['body'],
            meta_description=data['meta_description'],
            meta_image=data['meta_image'],
            user=request.user
        )
        if user_is_admin(request.user):
            post.show_in_main_page = \
                request.POST.get('show_in_main_page', None) is not None
        post.save()
        return redirect('mog:post', pk=post.id, slug=post.slug)


class EditPostView(View):

    @method_decorator(login_required)
    def get(self, request, post_id, *args, **kwargs):
        post = get_object_or_404(Post, pk=post_id)
        if not post.can_be_edited_by(request.user, user_is_admin(request.user)):
            return HttpResponseForbidden()
        return render(request, 'mog/post/edit.html', {
            'form': PostForm(instance=post), 'post': post,
        })

    @method_decorator(login_required)
    def post(self, request, post_id, *args, **kwargs):
        post = get_object_or_404(Post, pk=post_id)
        if not post.can_be_edited_by(request.user, user_is_admin(request.user)):
            return HttpResponseForbidden()
        form = PostForm(request.POST)
        if not form.is_valid():
            return render(request, 'mog/post/edit.html', {
                'form': form, 'post': post,
            })
        data = form.cleaned_data
        post.name = data['name']
        post.body = data['body']
        post.meta_description = data['meta_description']
        post.meta_image = data['meta_image']
        if user_is_admin(request.user):
            post.show_in_main_page =\
                request.POST.get('show_in_main_page', None) is not None
        post.save()
        return redirect('mog:post', pk=post.pk, slug=post.slug)
