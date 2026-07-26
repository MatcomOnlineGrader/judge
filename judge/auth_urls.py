"""Authentication URLs (login / logout / password management).

These were previously provided by django-registration 2.x via its
``registration.auth_urls`` module, under ``auth_*`` URL names. django-registration
3.x dropped the bundled auth URLs, so they are reproduced here to keep existing
templates and links working unchanged (they reverse ``auth_login``,
``auth_logout``, ``auth_password_reset`` and ``auth_password_reset_confirm``).

Django's built-in auth views resolve their default templates under
``registration/`` (login.html, password_reset_*.html, password_change_*.html),
all of which already exist in this project.
"""

from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from mog.forms import TurnstilePasswordResetForm

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="auth_login"),
    path("logout/", auth_views.LogoutView.as_view(), name="auth_logout"),
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            success_url=reverse_lazy("auth_password_change_done")
        ),
        name="auth_password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="auth_password_change_done",
    ),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            form_class=TurnstilePasswordResetForm,
            success_url=reverse_lazy("auth_password_reset_done"),
        ),
        name="auth_password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="auth_password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            success_url=reverse_lazy("auth_password_reset_complete")
        ),
        name="auth_password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="auth_password_reset_complete",
    ),
]
