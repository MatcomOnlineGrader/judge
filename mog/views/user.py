from django.contrib.auth import login

from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View, generic

from api.models import User, UserProfile, Division
from mog.forms import UserProfileForm, UserForm
from mog.utils import user_is_admin


class UserListView(generic.ListView):
    model = User
    template_name = 'mog/user/index.html'
    context_object_name = 'profiles'
    paginate_by = 30

    def get_queryset(self):
        result = UserProfile.sorted_by_ratings()
        if 'q' in self.request.GET:
            result = result.filter(
                Q(user__username__contains=self.request.GET['q']) |
                Q(user__first_name__contains=self.request.GET['q']) |
                Q(user__last_name__contains=self.request.GET['q'])
            )
        return result

    def get_context_data(self, **kwargs):
        context = super(UserListView, self).get_context_data(**kwargs)
        if 'q' in self.request.GET:
            context['query'] = {'q': self.request.GET['q']}
        return context


def user_profile(request, user_id):
    user_in_profile = get_object_or_404(User, pk=user_id)
    return render(request, 'mog/user/detail.html', {
        'user_in_profile': user_in_profile,
        'ratings': user_in_profile.profile.get_ratings(),
        'divisions': Division.objects.order_by('rating').all()
    })


@require_http_methods(["GET"])
def users_json(request):
    q = request.GET.get('q', '')
    users = User.objects.filter(
        Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
    )
    data = [{
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'url': user.profile.avatar.url if user.profile.avatar else '/static/mog/images/avatar.jpg'
    } for user in users[:10]]

    if 'callback' in request.GET:
        # Allow cross domain requests
        # TODO: Drop this!!!
        import json
        from django.http import HttpResponse
        callback = request.GET['callback']
        return HttpResponse('{0}({1})'.format(callback, json.dumps(data)), content_type='application/javascript')

    return JsonResponse(
        data=data,
        safe=False
    )


class UserEditView(View):
    @method_decorator(login_required)
    def get(self, request, user_id, *args, **kwargs):
        user = get_object_or_404(User, pk=user_id)
        if not user_is_admin(request.user) and request.user != user:
            return HttpResponseForbidden()
        return render(request, 'mog/user/edit.html', {
            'user_in_profile': user, 'user_form': UserForm(instance=user),
            'profile_form': UserProfileForm(instance=user.profile),
        })

    @method_decorator(login_required)
    def post(self, request, user_id, *args, **kwargs):
        user = get_object_or_404(User, pk=user_id)
        if not user_is_admin(request.user) and request.user != user:
            return redirect('mog:index')
        user_form, profile_form = UserForm(request.POST, instance=user),\
            UserProfileForm(request.POST, request.FILES, instance=user.profile)
        if not user_form.is_valid() or not profile_form.is_valid():
            return render(request, 'mog/user/edit.html', {
                'user_in_profile': user, 'user_form': user_form,
                'profile_form': profile_form
            })
        user_form.save()
        login(request, user)
        profile_form.save()
        return redirect('mog:user', user_id=user.pk)


@login_required
def user_messages(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if not user_is_admin(request.user) and request.user != user:
        return HttpResponseForbidden()
    user.messages_received.update(saw=True)
    return render(request, 'mog/user/messages.html', {
        'inbox': user.messages_received.order_by('-date').all(),
        'outbox': user.messages_sent.order_by('-date').all(),
        'user_in_profile': user,
    })


@login_required
def user_teams(request, user_id):
    user_in_profile = get_object_or_404(User, pk=user_id)
    if not user_is_admin(request.user) and request.user != user_in_profile:
        return HttpResponseForbidden()
    return render(request, 'mog/user/teams.html', {
        'user_in_profile': user_in_profile,
        'teams': user_in_profile.profile.teams.all()
    })
