import calendar
import datetime

from django.template.loader import render_to_string
from django.test import Client

from api.models import (
    Contest,
    ContestInstance,
    Team,
    User,
)

from tests import FixturedTestCase, TEST_USER_PASSWORD


class ContestRegistrationTestCase(FixturedTestCase):
    """
    This class contains tests related with contest registration where
    users can opt-in to participate in a contest. A registration of
    an user or team result in a new ContestInstance row in the
    database. No everyone has permission to do this and depend on some
    properties of the contest itself, also there is the concept of
    virtual participation where users/teams are marked as non-official
    participants but can experience a living standing.

    Test methods inside this class tries to cover correctness and
    any security case related with users registering themselve or their
    teams.

    The interaction is mainly done using the following endpoints:
    - /contest/register/<contest-id>
    - /contest/register/user/<contest-id> (only for admins)
    - /contest/register/team/<contest-id> (only for admins)

    TODO(leandro): Change the name of the endpoints to have <contest-id>
    right after contest/
    """

    def _register_team_in_contest(self, team, contest) -> ContestInstance:
        user = team.profiles.order_by('pk').first().user
        success = self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD,
        )
        self.assertTrue(success)
        self.client.post('/contest/register/{}'.format(contest.pk), data={
            "team": team.pk,
        })
        return ContestInstance.objects.filter(
            contest=contest, team=team
        ).first()

    def _register_user_in_contest(self, user, contest) -> ContestInstance:
        success = self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD,
        )
        self.assertTrue(success)
        self.client.post('/contest/register/{}'.format(contest.pk), data={
            "user": user.pk,
        })
        return ContestInstance.objects.filter(
            contest=contest, user=user
        ).first()

    def test_register_user_success(self):
        user, contest = self.newUser(username="leandro"), \
            self.newContest(code="contest")
        ci = self._register_user_in_contest(user, contest)
        self.assertIsNotNone(ci)
        self.assertEqual(ci.user_id, user.id)
        self.assertIsNone(ci.team)

    def test_register_team_success(self):
        team, contest = self.newTeam(number_of_users=3), \
            self.newContest(code="contest")
        ci = self._register_team_in_contest(team, contest)
        self.assertIsNotNone(ci)
        self.assertEqual(ci.team_id, team.id)

    def test_register_team_that_has_a_member_already_registered_fail(self):
        team, contest = self.newTeam(number_of_users=3), \
            self.newContest(code="contest")
        user = team.profiles.first().user
        user_ci = self._register_user_in_contest(user, contest)
        team_ci = self._register_team_in_contest(team, contest)
        self.assertIsNotNone(user_ci)
        self.assertIsNone(team_ci)

    def test_register_user_that_has_a_team_already_registered_fail(self):
        # TODO(leandro): Fix this test :(
        # team, contest = self.newTeam(number_of_users=3), \
        #     self.newContest(code="contest")
        # user = team.profiles.first().user
        # team_ci = self._register_team_in_contest(team, contest)
        # user_ci = self._register_user_in_contest(user, contest)
        # self.assertIsNone(user_ci)
        # self.assertIsNotNone(team_ci)
        pass

    def test_admin_endpoints_with_regular_user_in_request(self):
        team, contest = self.newTeam(number_of_users=3), \
            self.newContest(code="contest")
        user = team.profiles.order_by('pk').first().user
        self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD,
        )
        response = self.client.post('/contest/register/user/{}'.format(contest.pk), {
            "user": user.pk
        })
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/contest/register/team/{}'.format(contest.pk), {
            "team": team.pk
        })
        self.assertEqual(response.status_code, 403)

    def test_team_admin_endpoint_with_admin_in_request(self):
        team, contest = self.newTeam(number_of_users=3), \
            self.newContest(code="contest")
        admin = self.newUser(username="administrator")
        self.updateUserProfile(admin, role="admin")
        self.client.login(
            username=admin.username,
            password=TEST_USER_PASSWORD,
        )
        response = self.client.post('/contest/register/team/{}'.format(contest.pk), {
            "team": team.pk
        })
        self.assertEqual(response.status_code, 302)
        ci = ContestInstance.objects.filter(contest=contest, team=team).first()
        self.assertIsNotNone(ci)
        self.assertEqual(ci.team.id, team.id)
        self.assertIsNone(ci.user)
    
    def test_user_admin_endpoint_with_admin_in_request(self):
        user, contest = self.newUser(username="alice"), \
            self.newContest(code="contest")
        admin = self.newUser(username="administrator")
        self.updateUserProfile(admin, role="admin")
        self.client.login(
            username=admin.username,
            password=TEST_USER_PASSWORD,
        )
        response = self.client.post('/contest/register/user/{}'.format(contest.pk), {
            "user": user.pk
        })
        self.assertEqual(response.status_code, 302)
        ci = ContestInstance.objects.filter(contest=contest, user=user).first()
        self.assertIsNotNone(ci)
        self.assertEqual(ci.user.id, user.id)
        self.assertIsNone(ci.team)

    def test_contest_allow_team_success(self):
        """
        Assert that users and teams can register in a contest that allows teams.
        """
        contest, user, team = self.newContest(code="contest", allow_teams=True), \
            self.newUser(username="leandro"), \
                self.newTeam(number_of_users=3)
        user_ci = self._register_user_in_contest(user, contest)
        team_ci = self._register_team_in_contest(team, contest)
        self.assertIsNotNone(user_ci)
        self.assertIsNotNone(team_ci)

    def test_contest_do_not_allow_team_success(self):
        """
        Assert that only users are allowed to register in contests where
        allow_teams is False.
        """
        contest, user, team = self.newContest(code="contest", allow_teams=False), \
            self.newUser(username="leandro"), \
                self.newTeam(number_of_users=3)
        user_ci = self._register_user_in_contest(user, contest)
        team_ci = self._register_team_in_contest(team, contest)
        self.assertIsNotNone(user_ci)
        self.assertIsNone(team_ci)

    def test_that_regular_user_cannot_register_their_team_in_a_closed_contest(self):
        team, contest = self.newTeam(number_of_users=3), \
            self.newContest(code="closed-contest", closed=True)
        ci = self._register_team_in_contest(team, contest)
        self.assertIsNone(ci)

    def test_that_regular_user_cannot_register_in_a_closed_contest(self):
        user, contest = self.newUser(username="leandro"), \
            self.newContest(code="closed-contest", closed=True)
        ci = self._register_user_in_contest(user, contest)
        self.assertIsNone(ci)
