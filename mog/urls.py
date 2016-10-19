from django.contrib.auth.decorators import login_required
from django.conf.urls import url

from . import views

app_name = 'mog'
urlpatterns = [
    url(r'^faq/$', views.faq, name='faq'),

    url(r'^message/send/(?P<user_id>[0-9]+)$', views.send_message, name='send_message'),

    url(r'^team/create$', views.create_team, name='create_team'),
    url(r'^team/remove/(?P<team_id>[0-9]+)$', views.remove_team, name='remove_team'),

    url(r'^comment/edit/(?P<comment_id>[0-9]+)$', views.edit_comment, name='comment_edit'),

    url(r'^posts/$', views.PostListView.as_view(), name='posts'),
    url(r'^post/edit/(?P<post_id>[0-9]+)$', views.EditPostView.as_view(), name='post_edit'),
    url(r'^post/create$', views.PostCreateView.as_view(), name='post_create'),
    url(r'^post/(?P<pk>[0-9]+)/(?P<slug>[-\w]+)/$', views.PostDetailView.as_view(), name='post'),

    url(r'^problem/test/(?P<problem_id>[0-9]+)/edit$', views.TestEditView.as_view(), name='edit_test'),
    url(r'^problem/test/(?P<problem_id>[0-9]+)/remove$', views.remove_test, name='remove_test'),
    url(r'^problem/test/(?P<problem_id>[0-9]+)/list$', views.ProblemTestsView.as_view(), name='problem_tests'),
    url(r'^problem/create$', views.ProblemCreateView.as_view(), name='problem_create'),
    url(r'^problem/remove/(?P<problem_id>[0-9]+)$', views.remove_problem, name='problem_remove'),
    url(r'^problem/edit/(?P<problem_id>[0-9]+)$', views.ProblemEditView.as_view(), name='problem_edit'),
    url(r'^problem/(?P<problem_id>[0-9]+)/(?P<slug>[-\w]+)/$', views.problem, name='problem'),
    url(r'^problems/$', views.ProblemListView.as_view(), name='problems'),

    url(r'^contest/standing/(?P<contest_id>[0-9]+)$', views.contest_standing, name='contest_standing'),
    url(r'^contest/register/(?P<contest_id>[0-9]+)$', views.contest_register, name='contest_register'),
    url(r'^contest/unregister/(?P<contest_id>[0-9]+)$', views.contest_unregister, name='contest_unregister'),
    url(r'^contest/remove/(?P<contest_id>[0-9]+)$', views.remove_contest, name='contest_remove'),
    url(r'^contest/edit/(?P<contest_id>[0-9]+)$', views.ContestEditView.as_view(), name='contest_edit'),
    url(r'^contest/create$', views.ContestCreateView.as_view(), name='contest_create'),
    url(r'^contests/$', views.contests, name='contests'),
    url(r'^contest/problems/(?P<contest_id>[0-9]+)/$', views.contest_problems, name='contest_problems'),
    url(r'^contest/submissions/$', views.SubmissionListView.as_view(
        template_name='mog/contest/submissions.html'
    ), name='contest_submissions'),

    url(r'^submission/(?P<submission_id>[0-9]+)/$', views.submission, name='submission'),
    url(r'^submissions/$', views.SubmissionListView.as_view(
        template_name = 'mog/submission/index.html'
    ), name='submissions'),

    url(r'^users/json$', views.users_json, name='users_json'),
    url(r'^users/$', views.UserListView.as_view(), name='users'),

    url(r'^user/(?P<user_id>[0-9]+)/$', views.user_profile, name='user'),
    url(r'^user/edit/(?P<user_id>[0-9]+)/$', views.UserEditView.as_view(), name='user_edit'),
    url(r'^user/messages/(?P<user_id>[0-9]+)/$', views.user_messages, name='user_messages'),
    url(r'^user/teams/(?P<user_id>[0-9]+)/$', views.user_teams, name='user_teams'),

    url(r'^submit/(?P<problem_id>[0-9]+)/$', views.Submit.as_view(), name='submit'),

    url(r'^$', views.index, name='index'),
    url(r'^login/$', views.Login.as_view(), name='login'),
    url(r'^logout/$', views.Logout.as_view(), name='logout'),
    url(r'^register/$', views.Register.as_view(), name='register'),
]
