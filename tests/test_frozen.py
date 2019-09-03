from api.models import Contest, ROLE_CHOICES, Submission
from . import FixturedTestCase, TEST_USER_PASSWORD
from mog.templatetags import security


class FrozenContestTestCase(FixturedTestCase):
    def setUp(self):
        super(FrozenContestTestCase, self).setUp()
        self.user = self.newUser(username="user1", is_active=True)
        self.other_user = self.newUser(username="user2", is_active=True)

        self.frozen_instance = self.newContestInstance(self.frozen_contest, self.user)
        self.normal_submission = self.newSubmission(self.frozen_instance, self.user, problem=self.problem2,
                                                    result=self.accepted, status='normal')
        self.frozen_submission = self.newSubmission(self.frozen_instance, self.user, problem=self.problem2,
                                                    result=self.accepted, status='frozen')
        self.death_submission = self.newSubmission(self.frozen_instance, self.user, problem=self.problem2,
                                                   result=self.accepted, status='death')

    def test_can_register_for_virtual(self):
        self.assertFalse(security.can_register_for_virtual(self.user, self.past_frozen_contest))
        self.assertTrue(security.can_register_for_virtual(self.user, self.past_contest))

    def test_user_can_see_frozen(self):
        self.assertTrue(security.can_see_details_of(self.user, self.normal_submission))
        self.assertTrue(security.can_see_details_of(self.user, self.frozen_submission))

    def test_user_cannot_see_death(self):
        self.assertFalse(security.can_see_details_of(self.user, self.death_submission))
        self.assertFalse(security.can_see_judgment_details_of(self.user, self.death_submission))

    def test_other_user_can_see_normal(self):
        self.assertTrue(security.can_see_details_of(self.other_user, self.normal_submission))

    def test_other_user_cannot_see_frozen_or_death(self):
        self.assertFalse(security.can_see_details_of(self.other_user, self.frozen_submission))
        self.assertFalse(security.can_see_details_of(self.other_user, self.death_submission))

    def test_unfreeze_endpoint_access_admin(self):
        """
        Test that admins can unfreeze a finished contest.
        """
        contest_id = self.past_frozen_contest.pk
        user = self.newUser(username="user-admin", is_active=True)
        self.updateUserProfile(user, role="admin")
        self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD,
        )
        contest = Contest.objects.get(pk=contest_id)
        self.assertTrue(contest.needs_unfreeze)
        response = self.client.post('/contest/{}/unfreeze/'.format(contest_id), {})
        contest = Contest.objects.get(pk=contest_id)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(contest.needs_unfreeze)

    def test_unfreeze_endpoint_access_not_admin(self):
        """
        Test that no other user (except admins) can change the unfreeze
        status of past contests. Requests to /contest/#/unfreeze/ must
        rejected with forbidden error.
        """
        contest_id = self.past_frozen_contest.pk
        roles = [
            role for role,_ in ROLE_CHOICES if role != 'admin'
        ] + ['invalid', '', None]
        for role in roles:
            user = self.newUser(username="user-%s" % role, is_active=True)
            self.updateUserProfile(user, role=role)
            self.client.login(
                username=user.username,
                password=TEST_USER_PASSWORD,
            )
            contest = Contest.objects.get(pk=contest_id)
            self.assertTrue(contest.needs_unfreeze)
            response = self.client.post('/contest/{}/unfreeze/'.format(contest_id), {})
            self.assertEqual(response.status_code, 403)
            contest = Contest.objects.get(pk=contest_id)
            self.assertTrue(contest.needs_unfreeze)

    def test_unfreeze_endpoint_for_running_contest(self):
        """
        Everyone (including admin) are forbidden to change the unfreeze
        status of running contest.
        """
        contest_id = self.running_contest.pk
        roles = [
            role for role, _ in ROLE_CHOICES
        ] + ['invalid', '', None]
        for role in roles:
            user = self.newUser(username="user-%s" % role, is_active=True)
            self.updateUserProfile(user, role=role)
            self.client.login(
                username=user.username,
                password=TEST_USER_PASSWORD,
            )
            contest = Contest.objects.get(pk=contest_id)
            self.assertTrue(contest.needs_unfreeze)
            self.client.post('/contest/{}/unfreeze/'.format(contest_id), {})
            contest = Contest.objects.get(pk=contest_id)
            self.assertTrue(contest.needs_unfreeze)

    def test_unfreeze_endpoint_for_coming_contest(self):
        """
        Everyone (including admin) are forbidden to change the unfreeze
        status of coming contests.
        """
        contest_id = self.coming_contest.pk
        roles = [
            role for role, _ in ROLE_CHOICES
        ] + ['invalid', '', None]
        for role in roles:
            user = self.newUser(username="user-%s" % role, is_active=True)
            self.updateUserProfile(user, role=role)
            self.client.login(
                username=user.username,
                password=TEST_USER_PASSWORD,
            )
            contest = Contest.objects.get(pk=contest_id)
            self.assertTrue(contest.needs_unfreeze)
            self.client.post('/contest/{}/unfreeze/'.format(contest_id), {})
            contest = Contest.objects.get(pk=contest_id)
            self.assertTrue(contest.needs_unfreeze)

    def test_users_cannot_submit_on_past_unfrozen_contests(self):
        """
        Users cannot submit to unfrozen contests even when those
        contests are finished. The steps in this test are:
        1. User submit to a frozen past contest
        2. No submission is added
        3. Contest gets unfrozen
        4. User re-submit
        5. A new submission is added
        """
        contest = self.past_frozen_contest

        self.problem1.contest = contest
        self.problem1.compilers.add(self.cpp)
        self.problem1.save()

        SUBMIT_POST_URL = "/submit/{}/".format(
            self.problem1.pk
        )

        user = self.newUser(username='otero')
        self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD,
        )

        submissions_count = Submission.objects.count()
        r = self.client.post(SUBMIT_POST_URL, data={
            'problem': self.problem1.pk,
            'compiler': self.cpp.pk,
            'source': 'blah',
        })

        self.assertEqual(submissions_count, Submission.objects.count(), \
            msg="No new submission is added")

        contest.needs_unfreeze = False
        contest.save()

        r = self.client.post(SUBMIT_POST_URL, data={
            'problem': self.problem1.pk,
            'compiler': self.cpp.pk,
            'source': 'blah',
        })

        self.assertEqual(submissions_count + 1, Submission.objects.count(), \
            msg="A new submission is added")
