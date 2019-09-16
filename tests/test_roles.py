from django.test import TestCase

from bs4 import BeautifulSoup

from . import FixturedTestCase, TEST_USER_PASSWORD
from mog.gating import grant_role_to_user_in_contest, user_is_admin
from mog.templatetags import security
from mog.templatetags.security import can_create_clarification, can_edit_clarification


class RoleAdminTestCase(FixturedTestCase):
    def test_user_is_admin(self):
        admin = self.newUser(username="admin")
        self.updateUserProfile(admin, role="admin")
        self.assertTrue(user_is_admin(admin))

    def test_admin_cannot_see_messages_of_other_users(self):
        other = self.newUser(username="other")
        admin = self.newAdmin(username="admin")
        url = "/user/messages/%d/" % other.pk

        self.login(admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        self.login(other)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_see_edit_profile_of_other_users(self):
        other = self.newUser(username="other")
        admin = self.newAdmin(username="admin")
        url = "/user/edit/%d/" % other.pk

        self.login(admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        self.login(other)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_post_to_edit_profiles_of_other_users(self):
        other = self.newUser(username="other")
        admin = self.newAdmin(username="admin")
        url = "/user/edit/%d/" % other.pk

        # First, the regular user send a POST request to update their
        # own profile. As we are not sending any data along with the
        # request, then a response (status-code=200) is sent back
        # detailing the required fields. We assert that there is at
        # least of `This field is required` error.
        self.login(other)
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

        # The admin will be redirected to home if tries to send a POST
        # request to modify the profile of another user.
        self.login(admin)
        response = self.client.post(url, data={})
        self.assertRedirects(response, "/", status_code=302)
    
    def test_admin_can_see_other_user_profile_tabs(self):
        john = self.newUser(username="john")
        jane = self.newUser(username="jane")
        admin = self.newAdmin(username="admin")

        url = "/user/%d/" % john.pk
        user_profile_tab_id = "user-profile-tabs"

        self.login(admin)
        response = self.client.get(url)
        self.assertContains(response, user_profile_tab_id)

        self.login(john)
        response = self.client.get(url)
        self.assertContains(response, user_profile_tab_id)

        self.login(jane)
        response = self.client.get(url)
        self.assertNotContains(response, user_profile_tab_id)


class RoleObserverTestCase(FixturedTestCase):
    def setUp(self):
        super(RoleObserverTestCase, self).setUp()
        self.normal_user = self.newUser(username="user1", is_active=True)
        self.observer_user = self.newUser(username="user2", is_active=True)
        self.updateUserProfile(self.observer_user, role='observer')
        grant_role_to_user_in_contest(self.observer_user, self.problem2.contest, 'observer')

        self.running_instance = self.newContestInstance(self.running_contest, self.observer_user)
        self.past_instance = self.newContestInstance(self.past_contest, self.observer_user)
        self.frozen_instance = self.newContestInstance(self.frozen_contest, self.observer_user)
        self.death_instance = self.newContestInstance(self.death_contest, self.observer_user)

        instances = [self.running_instance, self.past_instance, self.frozen_instance, self.death_instance]
        status = ['normal', 'normal', 'frozen', 'death']

        self.all_visible_submissions = [self.newSubmission(instance, self.normal_user, problem=self.problem2,
                                                           result=self.accepted, status=status)
                                        for instance, status in zip(instances, status)]

        self.all_hidden_submissions = [self.newSubmission(instance, self.normal_user, problem=self.problem2,
                                                          result=self.accepted, status=status, hidden=True)
                                       for instance, status in zip(instances, status)]

    def test_can_see_visible_submissions(self):
        for submission in self.all_visible_submissions:
            self.assertTrue(security.can_see_code_of(self.observer_user, submission))
            self.assertTrue(security.can_see_judgment_details_of(self.observer_user, submission))
            self.assertTrue(security.can_see_details_of(self.observer_user, submission))

    def test_cannot_see_hidden_submissions(self):
        for submission in self.all_hidden_submissions:
            self.assertFalse(security.can_see_code_of(self.observer_user, submission))
            self.assertFalse(security.can_see_judgment_details_of(self.observer_user, submission))
            self.assertFalse(security.can_see_details_of(self.observer_user, submission))


class RoleJudgeTestCase(FixturedTestCase):
    def setUp(self):
        super(RoleJudgeTestCase, self).setUp()
        self.user = self.newUser(username="user1", is_active=True)
        self.judge = self.newUser(username="user2", is_active=True)
        self.updateUserProfile(self.judge, role='judge')

        grant_role_to_user_in_contest(self.judge, self.problem2.contest, 'judge')

        self.running_instance = self.newContestInstance(self.running_contest, self.user)
        self.past_instance = self.newContestInstance(self.past_contest, self.user)
        self.frozen_instance = self.newContestInstance(self.frozen_contest, self.user)
        self.death_instance = self.newContestInstance(self.death_contest, self.user)

        instances = [self.running_instance, self.past_instance, self.frozen_instance, self.death_instance]
        status = ['normal', 'normal', 'frozen', 'death']

        self.all_visible_submissions = [self.newSubmission(instance, self.user, problem=self.problem2,
                                                           result=self.accepted, status=status)
                                        for instance, status in zip(instances, status)]

        self.all_hidden_submissions = [self.newSubmission(instance, self.user, problem=self.problem2,
                                                          result=self.accepted, status=status, hidden=True)
                                       for instance, status in zip(instances, status)]

    def test_can_see_visible_submissions(self):
        for submission in self.all_visible_submissions:
            self.assertTrue(security.can_see_code_of(self.judge, submission))
            self.assertTrue(security.can_see_judgment_details_of(self.judge, submission))
            self.assertTrue(security.can_see_details_of(self.judge, submission))

    def test_can_see_hidden_submissions(self):
        for submission in self.all_hidden_submissions:
            self.assertTrue(security.can_see_code_of(self.judge, submission))
            self.assertTrue(security.can_see_judgment_details_of(self.judge, submission))
            self.assertTrue(security.can_see_details_of(self.judge, submission))

    def can_see_coming_contest(self):
        self.assertTrue(self.coming_contest.can_be_seen_by(self.judge))

    def can_see_hidden_contest(self):
        self.assertTrue(self.coming_hidden_contest.can_be_seen_by(self.judge))

    def test_can_create_edit_clarifications(self):
        for contest in [self.past_contest, self.running_contest, self.frozen_contest, self.coming_hidden_contest]:
            grant_role_to_user_in_contest(self.judge, contest, 'judge')
            self.assertTrue(can_edit_clarification(self.judge, contest))
            self.assertTrue(can_create_clarification(self.judge, contest))
