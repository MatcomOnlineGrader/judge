from .contest import contests, contest_clarifications, contest_problems, contest_standing, contest_submissions, \
    remove_contest, contest_register, contest_remove_instance, contest_remove_registration, \
    ContestCreateView, ContestEditView, rate_contest, unrate_contest, contest_registration, \
    contest_register_team, contest_register_user, unfreeze_contest, contest_json, contest_csv, contest_saris
from .post import PostListView, PostDetailView, PostCreateView, EditPostView
from .problem import remove_problem, problem, ProblemCreateView, ProblemEditView, \
    ProblemListView, ProblemTestsView, remove_test, TestEditView
from .submission import submissions, submission, Submit, rejudge
from .team import create_team, remove_team
from .user import UserListView, user_profile, users_json, UserEditView, user_messages, user_teams
from .views import index, faq, privacy
from .message import send_message
from .comment import edit_comment, remove_comment
from .clarification import clarification_create, clarification_edit
from .instance import instance_group_list, instance_edit_group
from .feedback import feedback_create
