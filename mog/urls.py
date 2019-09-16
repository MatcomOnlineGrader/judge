from django.conf.urls import url

from . import views

app_name = 'mog'
urlpatterns = [
    url(r'^health/$', views.health, name='health'),
    url(r'^faq/$', views.faq, name='faq'),
    url(r'^privacy/$', views.privacy, name='privacy'),

    url(r'^feedback/create/$', views.feedback_create, name='feedback_create'),

    url(r'^api/instance/group/list/$', views.instance_group_list,
        name='api_instance_group_list'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/group/$', views.instance_edit_group,
        name='api_instance_edit_group'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/render_description/$', views.instance_edit_render_description,
        name='api_instance_edit_render_description'),

    url(r'^message/send/(?P<user_id>[0-9]+)$', views.send_message, name='send_message'),

    url(r'^team/create$', views.create_team, name='create_team'),
    url(r'^team/remove/(?P<team_id>[0-9]+)$', views.remove_team, name='remove_team'),

    url(r'^comment/(?P<comment_id>[0-9]+)/edit/$', views.edit_comment, name='comment_edit'),
    url(r'^comment/(?P<comment_id>[0-9]+)/remove/$', views.remove_comment, name='comment_remove'),

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

    url(r'^clarification/create/$', views.clarification_create, name='clarification_create'),
    url(r'^clarification/(?P<clarification_id>[0-9]+)/edit/$', views.clarification_edit, name='clarification_edit'),

    url(r'^contest/register/(?P<contest_id>[0-9]+)$', views.contest_register, name='contest_register'),
    url(r'^contest/register/user/(?P<contest_id>[0-9]+)$', views.contest_register_user, name='contest_register_user'),
    url(r'^contest/register/team/(?P<contest_id>[0-9]+)$', views.contest_register_team, name='contest_register_team'),
    url(r'^contest/remove/instance/(?P<instance_id>[0-9]+)$', views.contest_remove_instance,
        name='contest_remove_instance'),
    url(r'^contest/remove/registration/(?P<contest_id>[0-9]+)$', views.contest_remove_registration,
        name='contest_remove_registration'),

    url(r'^contest/(?P<contest_id>[0-9]+)/clarifications$', views.contest_clarifications, name='contest_clarifications'),
    url(r'^contest/overview/(?P<contest_id>[0-9]+)$', views.contest_overview, name='contest_overview'),
    url(r'^contest/problems/(?P<contest_id>[0-9]+)$', views.contest_problems, name='contest_problems'),
    url(r'^contest/saris/(?P<contest_id>[0-9]+)$', views.contest_saris, name='contest_saris'),
    url(r'^contest/standing/(?P<contest_id>[0-9]+)$', views.contest_standing, name='contest_standing'),
    url(r'^contest/submissions/(?P<contest_id>[0-9]+)$', views.contest_submissions, name='contest_submissions'),
    url(r'^contest/registration/(?P<contest_id>[0-9]+)$', views.contest_registration, name='contest_registration'),
    url(r'^contest/edit/(?P<contest_id>[0-9]+)$', views.ContestEditView.as_view(), name='contest_edit'),
    url(r'^contest/remove/(?P<contest_id>[0-9]+)$', views.remove_contest, name='contest_remove'),

    url(r'^contest/create$', views.ContestCreateView.as_view(), name='contest_create'),
    url(r'^contests/$', views.contests, name='contests'),

    url(r'^contest/rate/(?P<contest_id>[0-9]+)$', views.rate_contest, name='rate_contest'),
    url(r'^contest/unrate/(?P<contest_id>[0-9]+)$', views.unrate_contest, name='unrate_contest'),
    url(r'^contest/(?P<contest_id>[0-9]+)/unfreeze/$', views.unfreeze_contest, name='contest_unfreeze'),
    url(r'^contest/json/(?P<contest_id>[0-9]+)$', views.contest_json, name='contest_json'),
    url(r'^contest/csv/(?P<contest_id>[0-9]+)$', views.contest_csv, name='contest_csv'),

    url(r'^submission/(?P<submission_id>[0-9]+)/$', views.submission, name='submission'),
    url(r'^submission/rejudge/(?P<submission_id>[0-9]+)/$', views.rejudge, name='submission_rejudge'),
    url(r'^submissions/$', views.submissions,name='submissions'),

    url(r'^users/json$', views.users_json, name='users_json'),
    url(r'^users/$', views.UserListView.as_view(), name='users'),

    url(r'^user/(?P<user_id>[0-9]+)/$', views.user_profile, name='user'),
    url(r'^user/edit/(?P<user_id>[0-9]+)/$', views.UserEditView.as_view(), name='user_edit'),
    url(r'^user/messages/(?P<user_id>[0-9]+)/$', views.user_messages, name='user_messages'),
    url(r'^user/teams/(?P<user_id>[0-9]+)/$', views.user_teams, name='user_teams'),

    url(r'^submit/(?P<problem_id>[0-9]+)/$', views.Submit.as_view(), name='submit'),

    url(r'^$', views.index, name='index'),
]
