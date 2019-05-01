from django.test import TestCase

from . import FixturedTestCase
from mog.templatetags import security


class SecurityFilterTestCase(FixturedTestCase):
    def test_can_comment_on_post(self):
        post = self.newPost(
            self.newUser(username="author")
        )
        # inactive users cannot comment on post
        user = self.newUser(username="user1", is_active=False)
        self.assertFalse(security.can_comment_on_post(
            user,
            post
        ))
        # users with 0 score cannot comment on post
        user = self.newUser(username="user2")
        self.assertFalse(security.can_comment_on_post(
            user,
            post
        ))
        # active users with positive score can comment on post
        user = self.newUser(username="user3")
        self.updateUserProfile(user, points=5)
        self.assertTrue(security.can_comment_on_post(
            user,
            post
        ))
