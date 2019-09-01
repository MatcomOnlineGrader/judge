from django.test import TestCase

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
