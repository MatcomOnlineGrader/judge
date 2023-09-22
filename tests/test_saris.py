from mog.helpers import get_contest_json
from . import FixturedTestCase, TEST_USER_PASSWORD


class SarisTestCase(FixturedTestCase):
    def setUp(self):
        super(SarisTestCase, self).setUp()
        self.number_of_users = 5
        self.number_of_problems = 10

        self.problems = [
            self.newProblem(
                title="Problem%d" % i, position=i, contest=self.past_contest
            )
            for i in range(self.number_of_problems)
        ]

        self.users = [
            self.newUser(username="user%d" % i, is_active=True)
            for i in range(self.number_of_users)
        ]
        self.instances = [
            self.newContestInstance(self.past_contest, self.users[i])
            for i in range(self.number_of_users)
        ]

    def submit_in_contest(self, user_idx, problem_idx, result, minutes):
        self.newSubmission(
            self.instances[user_idx],
            self.users[user_idx],
            minutes=minutes,
            problem=self.problems[problem_idx],
            result=result,
        )

    def test_counts(self):
        for i in range(self.number_of_users):
            for j in range(self.number_of_problems):
                self.submit_in_contest(i, j, self.accepted, i * j * 10)
        result = get_contest_json(contest=self.past_contest)

        self.assertTrue(
            len(result["runs"]) == self.number_of_users * self.number_of_problems
        )
        self.assertTrue(len(result["contestants"]) == self.number_of_users)
        self.assertTrue(
            result["freezeTimeMinutesFromStart"]
            == int(self.past_contest.duration.total_seconds() / 60)
            - self.past_contest.frozen_time
        )

    def test_title(self):
        result = get_contest_json(contest=self.past_contest)
        self.assertTrue(result["contestName"] == self.past_contest.name)

    def test_user_did_not_submit(self):
        for i in range(self.number_of_users):
            self.submit_in_contest(i, 0, self.accepted, i * 10)
        result = get_contest_json(contest=self.past_contest)
        self.assertTrue(len(result["runs"]) == self.number_of_users)
        self.assertTrue(len(result["contestants"]) == self.number_of_users)

    def test_no_user_submitted(self):
        result = get_contest_json(contest=self.past_contest)
        self.assertTrue(len(result["runs"]) == 0)
        self.assertTrue(len(result["contestants"]) == self.number_of_users)

    def test_submissions(self):
        for i in range(self.number_of_users):
            self.submit_in_contest(i, 0, self.accepted, i * 10)
        result = get_contest_json(contest=self.past_contest)

        for i in range(len(result["runs"])):
            self.assertTrue(result["runs"][i]["timeMinutesFromStart"] == i * 10)
            self.assertTrue(result["runs"][i]["contestant"] == self.users[i].username)

    def test_endpoint_access(self):
        self.normal_user = self.newUser(username="normal", is_active=True)
        self.observer_user = self.newUser(username="observer", is_active=True)
        self.admin_user = self.newUser(username="admin", is_active=True)
        self.updateUserProfile(self.observer_user, role="observer")
        self.updateUserProfile(self.admin_user, role="admin")

        self.client.login(
            username=self.normal_user.username,
            password=TEST_USER_PASSWORD,
        )

        response = self.client.post(
            "/contest/saris/{}".format(self.past_contest.pk), {}
        )
        self.assertEqual(response.status_code, 403)

        for user in [self.observer_user, self.admin_user]:
            self.client.login(
                username=user.username,
                password=TEST_USER_PASSWORD,
            )
            response = self.client.post(
                "/contest/saris/{}".format(self.past_contest.pk), {}
            )
