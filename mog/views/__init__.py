from .account import Register, Login, Logout
from .contest import contests, contest_problems, contest_standing,\
    remove_contest, contest_register, contest_unregister, ContestCreateView, ContestEditView
from .post import PostListView, PostDetailView, PostCreateView, EditPostView
from .problem import remove_problem, problem, ProblemCreateView, ProblemEditView,\
    ProblemListView, ProblemTestsView, remove_test, TestEditView
from .submission import SubmissionListView, submission, Submit
from .team import create_team, remove_team
from .user import UserListView, user_profile, users_json, UserEditView, user_messages, user_teams
from .views import index, faq
from .message import send_message