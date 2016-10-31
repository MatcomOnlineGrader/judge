from .account import Register, Login, Logout
from .contest import contests, contest_problems, contest_standing, contest_submissions,\
    remove_contest, contest_register, contest_remove_instance, contest_remove_registration,\
    ContestCreateView, ContestEditView, rate_contest, unrate_contest, contest_registration,\
    contest_register_team, contest_register_user
from .post import PostListView, PostDetailView, PostCreateView, EditPostView
from .problem import remove_problem, problem, ProblemCreateView, ProblemEditView,\
    ProblemListView, ProblemTestsView, remove_test, TestEditView
from .submission import submissions, submission, Submit
from .team import create_team, remove_team
from .user import UserListView, user_profile, users_json, UserEditView, user_messages, user_teams
from .views import index, faq
from .message import send_message
from .comment import edit_comment