from django.conf.urls import url

from . import views

app_name = 'mog'
urlpatterns = [
    url(r'^health/$', views.health, name='health'),
    url(r'^faq/$', views.faq, name='faq'),
    url(r'^privacy/$', views.privacy, name='privacy'),

    url(r'^feedback/create/$', views.feedback_create, name='feedback_create'),

    url(r'^api/institution/list/$', views.institution_list, name='api_institution_list'),

    url(r'^api/instance/group/list/$', views.instance_group_list, name='api_instance_group_list'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/group/$', views.instance_edit_group, name='api_instance_edit_group'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/render_description/$', views.instance_edit_render_description, name='api_instance_edit_render_description'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/team/$', views.instance_edit_team, name='api_instance_edit_team'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/user/$', views.instance_edit_user, name='api_instance_edit_user'),
    url(r'^api/instance/(?P<instance_pk>[0-9]+)/edit/enable/$', views.instance_edit_enable, name='api_instance_edit_enable'),

    url(r'^api/contest/permission/(?P<permission_pk>[0-9]+)/edit/granted$', views.contest_permission_edit_granted, name='api_contest_permission_edit_granted'),

    url(r'^message/send/(?P<user_id>[0-9]+)$', views.send_message, name='send_message'),

    url(r'^teams/json$', views.teams_json, name='teams_json'),

    url(r'^team/create$', views.create_team, name='create_team'),
    url(r'^team/remove/(?P<team_id>[0-9]+)$', views.remove_team, name='remove_team'),
    url(r'^team/edit/(?P<team_id>[0-9]+)$', views.edit_team, name='edit_team'),

    url(r'^comment/(?P<comment_id>[0-9]+)/edit/$', views.edit_comment, name='comment_edit'),
    url(r'^comment/(?P<comment_id>[0-9]+)/remove/$', views.remove_comment, name='comment_remove'),

    url(r'^posts/$', views.PostListView.as_view(), name='posts'),
    url(r'^post/edit/(?P<post_id>[0-9]+)$', views.EditPostView.as_view(), name='post_edit'),
    url(r'^post/create$', views.PostCreateView.as_view(), name='post_create'),
    url(r'^post/(?P<pk>[0-9]+)/(?P<slug>[-\w]+)/$', views.PostDetailView.as_view(), name='post'),

    url(r'^checkers/$', views.view_checker, name='view_checker'),
    url(r'^checkers/create/$', views.CreateCheckerView.as_view(), name='create_checker'),

    url(r'^problem/test/(?P<problem_id>[0-9]+)/view$', views.view_test, name='view_test'),
    url(r'^problem/test/(?P<problem_id>[0-9]+)/remove$', views.remove_test, name='remove_test'),
    url(r'^problem/test/(?P<problem_id>[0-9]+)/list$', views.ProblemTestsView.as_view(), name='problem_tests'),
    url(r'^problem/checker/(?P<problem_id>[0-9]+)/view$', views.ProblemCheckerView.as_view(), name='problem_checker'),
    url(r'^problem/checker/(?P<problem_id>[0-9]+)/create$', views.CheckerView.as_view(), name='checker'),
    url(r'^problem/remove/(?P<problem_id>[0-9]+)$', views.remove_problem, name='problem_remove'),
    url(r'^problem/edit/(?P<problem_id>[0-9]+)$', views.ProblemEditView.as_view(), name='problem_edit'),
    url(r'^problem/(?P<problem_id>[0-9]+)/(?P<slug>[-\w]+)/$', views.problem, name='problem'),
    url(r'^problems/$', views.ProblemListView.as_view(), name='problems'),

    url(r'^clarification/create/$', views.clarification_create, name='clarification_create'),
    url(r'^clarification/(?P<clarification_id>[0-9]+)/edit/$', views.clarification_edit, name='clarification_edit'),

    url(r'^contest/register/(?P<contest_id>[0-9]+)$', views.contest_register, name='contest_register'),
    url(r'^contest/register/user/(?P<contest_id>[0-9]+)$', views.contest_register_user, name='contest_register_user'),
    url(r'^contest/register/team/(?P<contest_id>[0-9]+)$', views.contest_register_team, name='contest_register_team'),
    url(r'^contest/remove/instance/(?P<instance_id>[0-9]+)$', views.contest_remove_instance, name='contest_remove_instance'),
    url(r'^contest/remove/registration/(?P<contest_id>[0-9]+)$', views.contest_remove_registration, name='contest_remove_registration'),
    url(r'^contest/instances/info/(?P<contest_id>[0-9]+)$', views.contest_instances_info, name='contest_instances_info'),
    
    url(r'contest/(?P<contest_id>[0-9]+)/registration/multiple/register/user/$', views.contest_registration_multiple_register_user, name='contest_registration_multiple_register_user'),
    url(r'contest/(?P<contest_id>[0-9]+)/registration/multiple/register/team/$', views.contest_registration_multiple_register_team, name='contest_registration_multiple_register_team'),
    url(r'contest/(?P<contest_id>[0-9]+)/registration/multiple/unregister/$', views.contest_registration_multiple_unregister, name='contest_registration_multiple_unregister'),
    url(r'contest/(?P<contest_id>[0-9]+)/registration/multiple/edit-group/$', views.contest_registration_multiple_edit_group, name='contest_registration_multiple_edit_group'),
    url(r'contest/(?P<contest_id>[0-9]+)/registration/multiple/enable/$', views.contest_registration_multiple_enable, name='contest_registration_multiple_enable'),
    url(r'contest/(?P<contest_id>[0-9]+)/registration/multiple/disable/$', views.contest_registration_multiple_disable, name='contest_registration_multiple_disable'),

    url(r'^contest/(?P<contest_id>[0-9]+)/clarifications$', views.contest_clarifications, name='contest_clarifications'),
    url(r'^contest/(?P<contest_id>[0-9]+)/create_problem$', views.CreateProblemInContestView.as_view(), name='contest_create_problem'),
    url(r'^contest/overview/(?P<contest_id>[0-9]+)$', views.contest_overview, name='contest_overview'),
    url(r'^contest/problems/(?P<contest_id>[0-9]+)$', views.contest_problems, name='contest_problems'),
    url(r'^contest/saris/(?P<contest_id>[0-9]+)$', views.contest_saris, name='contest_saris'),
    url(r'^contest/standing/(?P<contest_id>[0-9]+)$', views.contest_standing, name='contest_standing'),
    url(r'^contest/submissions/(?P<contest_id>[0-9]+)$', views.contest_submissions, name='contest_submissions'),
    url(r'^contest/submissions/export/(?P<contest_id>[0-9]+)$', views.contest_submissions_export, name='contest_submissions_export'),
    url(r'^contest/registration/(?P<contest_id>[0-9]+)$', views.contest_registration, name='contest_registration'),
    url(r'^contest/edit/(?P<contest_id>[0-9]+)$', views.ContestEditView.as_view(), name='contest_edit'),
    url(r'^contest/remove/(?P<contest_id>[0-9]+)$', views.remove_contest, name='contest_remove'),
    url(r'^contest/(?P<contest_id>[0-9]+)/team/(?P<team_id>[0-9]+)/submissions$', views.team_submissions, name='team_submissions'),
    url(r'^contest/create$', views.ContestCreateView.as_view(), name='contest_create'),
    url(r'^contests/$', views.contests, name='contests'),

    url(r'^contest/manage/(?P<contest_id>[0-9]+)$', views.contest_manage, name='contest_manage'),
    url(r'^contest/manage/import/baylor/(?P<contest_id>[0-9]+)$', views.contest_manage_import_baylor, name='contest_manage_import_baylor'),
    url(r'^contest/manage/import/guest/(?P<contest_id>[0-9]+)$', views.contest_manage_import_guest, name='contest_manage_import_guest'),
    url(r'^contest/manage/export/password/(?P<contest_id>[0-9]+)$', views.contest_manage_export_password, name='contest_manage_export_password'),

    url(r'^contest/permission/(?P<contest_id>[0-9]+)$', views.contest_permission, name='contest_permission'),
    url(r'^contest/permission/assign/(?P<contest_id>[0-9]+)$', views.contest_add_permission, name='contest_add_permission'),
    url(r'^contest/permission/import/(?P<contest_id>[0-9]+)$', views.contest_permission_import, name='contest_permission_import'),
    url(r'^contest/permission/export/(?P<contest_id>[0-9]+)$', views.contest_permission_export, name='contest_permission_export'),

    url(r'^contest/rate/(?P<contest_id>[0-9]+)$', views.rate_contest, name='rate_contest'),
    url(r'^contest/unrate/(?P<contest_id>[0-9]+)$', views.unrate_contest, name='unrate_contest'),
    url(r'^contest/(?P<contest_id>[0-9]+)/unfreeze/$', views.unfreeze_contest, name='contest_unfreeze'),
    url(r'^contest/stats/(?P<contest_id>[0-9]+)$', views.contest_stats, name='contest_stats'),
    url(r'^contest/ratings/(?P<contest_id>[0-9]+)$', views.contest_rating_changes, name='contest_ratings'),
    url(r'^contest/csv/(?P<contest_id>[0-9]+)$', views.contest_csv, name='contest_csv'),
    url(r'^contest/export/baylor/(?P<contest_id>[0-9]+)$', views.contest_baylor, name='contest_baylor'),

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
