from django.test import TestCase

from mog.templatetags.security import can_create_clarification, can_edit_clarification
from . import FixturedTestCase
from mog.templatetags import security


class RoleObserverTestCase(FixturedTestCase):
    def setUp(self):
        super(RoleObserverTestCase, self).setUp()
        self.normal_user = self.newUser(username="user1", is_active=True)
        self.observer_user = self.newUser(username="user2", is_active=True)
        self.updateUserProfile(self.observer_user, role='observer')

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
            self.assertTrue(can_edit_clarification(self.judge, contest))
            self.assertTrue(can_create_clarification(self.judge, contest))
