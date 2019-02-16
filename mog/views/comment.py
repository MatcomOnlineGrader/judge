from django.http import HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from api.models import Comment


@login_required
@require_http_methods(["POST"])
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if not comment.can_be_edited_by(request.user):
        return HttpResponseForbidden()
    comment.body = request.POST.get('body', '')
    comment.save()
    return redirect('mog:post', pk=comment.post_id, slug=comment.post.slug)


@login_required
@require_http_methods(["POST"])
def remove_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if not comment.can_be_removed_by(request.user):
        return HttpResponseForbidden()
    comment.delete()
    return redirect('mog:post', pk=comment.post_id, slug=comment.post.slug)
