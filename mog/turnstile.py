"""Minimal Cloudflare Turnstile form field.

Replaces the third-party ``django-turnstile`` package (unmaintained, one
release, officially Django <= 4.0). Cloudflare publishes no official Python
library, and the server side is a single ``siteverify`` POST, so we own it here.

Usage mirrors the old package::

    from mog.turnstile import TurnstileField

    class MyForm(forms.Form):
        turnstile = TurnstileField(label="", action="turnstile-spin-v2")

The widget renders Cloudflare's script plus the ``cf-turnstile`` div; the field
reads the token the script injects (``cf-turnstile-response``) and verifies it
against Cloudflare before the form is considered valid. Site key and secret come
from ``settings.TURNSTILE_SITEKEY`` / ``settings.TURNSTILE_SECRET``.
"""

import requests
from django import forms
from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

JS_API_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js"
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Cloudflare's client script always submits the token under this fixed name,
# regardless of the Django form field's name.
TOKEN_FIELD_NAME = "cf-turnstile-response"

# Fail closed if Cloudflare can't be reached: a failed challenge blocks the POST.
VERIFY_TIMEOUT = 5


class TurnstileWidget(forms.Widget):
    """Renders the Turnstile script tag and the ``cf-turnstile`` challenge div."""

    def __init__(self, attrs=None, data_attrs=None):
        super().__init__(attrs)
        self.data_attrs = data_attrs or {}

    def value_from_datadict(self, data, files, name):
        # The token lives under Cloudflare's fixed field name, not `name`.
        return data.get(TOKEN_FIELD_NAME)

    def render(self, name, value, attrs=None, renderer=None):
        data_attrs = {"sitekey": settings.TURNSTILE_SITEKEY, **self.data_attrs}
        attrs_html = format_html_join(
            "", ' data-{}="{}"', ((key, val) for key, val in data_attrs.items())
        )
        return format_html(
            '<script src="{}" async defer></script>\n'
            '<div class="cf-turnstile"{}></div>',
            JS_API_URL,
            attrs_html,
        )


class TurnstileField(forms.Field):
    """Form field that renders a Turnstile widget and verifies its token."""

    widget = TurnstileWidget
    default_error_messages = {
        "invalid": _("Challenge verification failed. Please try again."),
        "unavailable": _("Could not verify the challenge. Please try again."),
    }

    def __init__(self, *, action=None, theme=None, size=None, **kwargs):
        # Non-Field options become data-* attributes on the widget div.
        data_attrs = {}
        if action is not None:
            data_attrs["action"] = action
        if theme is not None:
            data_attrs["theme"] = theme
        if size is not None:
            data_attrs["size"] = size
        kwargs.setdefault("widget", TurnstileWidget(data_attrs=data_attrs))
        super().__init__(**kwargs)

    def validate(self, value):
        # Handles the empty/required case (a missing token is a failed challenge).
        super().validate(value)
        if value in self.empty_values:
            return
        try:
            response = requests.post(
                VERIFY_URL,
                data={"secret": settings.TURNSTILE_SECRET, "response": value},
                timeout=VERIFY_TIMEOUT,
            )
            result = response.json()
        except (requests.RequestException, ValueError):
            raise forms.ValidationError(
                self.error_messages["unavailable"], code="unavailable"
            )
        if not result.get("success"):
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")
