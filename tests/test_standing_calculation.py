from . import FixturedTestCase

from mog.standing import calculate_standing_new, calculate_standing_old
from api.models import Contest, ContestInstance, Submission, Problem, User, Team, Result, Compiler

from django.conf import settings
from django.utils.timezone import timedelta, datetime
from functools import partial

from unittest import skip
from itertools import repeat

import pytz

ACCEPTED = 'Accepted'
PENDING = 'Pending'
INVALID = 'Wrong Answer'

class CalculateStandingCase(FixturedTestCase):
    def setUp(self):
        super().setUp()

        self.contest_nonce = 0
        self.team_nonce = 0
        self.users = {}
        self.teams = {}

        self.compiler = Compiler.objects.get(name='GNU C++ 5.1.0')


    def get_user(self, user_id):
        if not user_id in self.users:
            user = User.objects.create(username=f"Test User {user_id}")
            self.users[user_id] = user
            return user
        else:
            return self.users[user_id]


    def get_team(self, user_ids):
        user_ids = tuple(user_ids)

        if not user_ids in self.teams:
            team = Team.objects.create(name=f"Test Team {self.team_nonce}")
            self.team_nonce += 1
            for user_id in user_ids:
                team.profiles.add(self.get_user(user_id).profile)
            self.teams[user_ids] = team
            return team
        else:
            return self.teams[user_ids]


    def make_contest(self,
        duration=timedelta(hours=5),
        frozen=timedelta(hours=1),
        death=timedelta(minutes=15),
        num_problems=5,
        num_users=0,
        num_teams=0,
        submissions=[],
        groups=None,
        checkpoint=timedelta(minutes=0),
        after_frozen=timedelta(minutes=0)):
        """
        duration: Timedelta. Duration of the contest.
        frozen: Timedelta. Duration of frozen time.
        death: Timedelta. Duration of death time.
        num_problems: Number of problems in the contest.
        num_users: Number of participants as users.
        num_teams: Number of participants as teams.
        submissions: List of submissions.
            [participant_id, problem_id, result, delta]
                participant_id: Id of the sender of the submissions. [0, num_user + num_teams)
                problem_id: Id of this submission problem. [0, num_problems)
                result: One of (ACCEPTED, PENDING, INVALID)
                delta: Time passed since the beginning of the competition in minutes.
        groups: None to use not groups. Otherwise array of lengh `num_user + num_teams` with name of groups.
        checkpoint: Timedelta. Time passed since the beginning of the competition. See standing at this moment.
        after_frozen: Timedelta. Time to wait to unfreeze standing after the contest is over.
        """

        START_TIME = datetime(
            year=2018,
            month=1,
            day=1,
            tzinfo=pytz.timezone(settings.TIME_ZONE)
        )

        checkpoint = START_TIME + checkpoint

        # Create new contest
        contest_nonce = self.contest_nonce
        self.contest_nonce += 1

        contest = Contest.objects.create(
            name=f"Test Contest #{contest_nonce}",
            code=f"TC{self.contest_nonce}",
            visible=True,
            start_date=START_TIME,
            end_date=START_TIME + duration,
            frozen_time=frozen.total_seconds() // 60,
            death_time=death.total_seconds() // 60,
            allow_teams=True,
        )
        self.contest_nonce += 1

        # Create problems
        problems = []
        for prob_id in range(num_problems):
            problem = Problem.objects.create(
                title=f"Test Problem #{contest_nonce}-{prob_id}",
                contest=contest,
                position=prob_id,
                time_limit=1,
                memory_limit=1,
            )
            problems.append(problem)

        # Create participants
        groups = repeat(None) if groups is None else iter(groups)

        participants = []
        for user_ix in range(num_users):
            user = self.get_user(user_ix)
            participant = ContestInstance.objects.create(
                user=user,
                contest=contest,
                real=True,
                start_date=START_TIME,
                group=next(groups),
            )
            participants.append(participant)

        all_team_ids = []
        for team_ix in range(num_teams):
            # Create team with three new users not used for this contest
            team_ids = list(range(num_users + 3 * team_ix, num_users + 3 * team_ix + 3))
            all_team_ids.append(team_ids)
            team = self.get_team(team_ids)
            participant = ContestInstance.objects.create(
                team=team,
                contest=contest,
                real=True,
                start_date=START_TIME,
                group=next(groups),
            )
            participants.append(participant)

        # Create submissions
        for participant_id, problem_id, result, delta in submissions:
            if isinstance(delta, int):
                delta = timedelta(minutes=delta)

            self.assertIsInstance(delta, timedelta)
            submission_date = START_TIME + delta

            if checkpoint < submission_date:
                # This submission is ahead of time. Ignore it.
                continue

            # Compute status
            if contest.frozen_time_from_date(submission_date):
                status = 'frozen'
            elif contest.death_time_from_date(submission_date):
                status = 'death'
            else:
                status = 'normal'

            if checkpoint >= contest.end_date + after_frozen:
                # Show all submissions after standing become unfrozen
                status = 'normal'

            if participant_id < num_users:
                user = self.get_user(participant_id)
            else:
                user = self.get_user(all_team_ids[participant_id - num_users][0])

            Submission.objects.create(
                problem=problems[problem_id],
                date=submission_date,
                instance=participants[participant_id],
                result=Result.objects.get(name=result),
                status=status,
                compiler=self.compiler,
                user=user
            )

        return contest, participants


    def make_contest_multiple_checkpoints(self, checkpoints, **kwargs):
        contest_desc = partial(self.make_contest, **kwargs)

        for checkpoint in checkpoints:
            contest, participants = contest_desc(checkpoint=checkpoint)
            self.full_compare(contest, participants)


    def compare_old_new(self, contest, debug=False, **kwargs):
        problems_old, ranking_old = calculate_standing_old(contest, **kwargs)
        problems_new, ranking_new = calculate_standing_new(contest, **kwargs)

        self.assertSequenceEqual(problems_old, problems_new)

        for rank_entry_old, rank_entry_new in zip(ranking_old, ranking_new):
            # print(rank_entry_old, rank_entry_new)

            self.assertEqual(rank_entry_old.solved, rank_entry_new.solved)
            # Note: In theory rank number can be different, regarding participants
            # with the same ranking (not in the bottom of the standing).
            # Old ranking: [1, 1, 2, 3, 3, 4, 4, 4]
            # New ranking: [1, 1, 3, 4, 4, 6, 6, 6]
            # In practice is almost impossible for two participants with at least
            # on accepted solution having the exact same score, because of
            # tie breakers.
            self.assertEqual(rank_entry_old.rank, rank_entry_new.rank)
            self.assertAlmostEqual(rank_entry_old.penalty, rank_entry_new.penalty)
            self.assertEqual(rank_entry_old.instance, rank_entry_new.participant)

            self.assertIsInstance(rank_entry_new.solved, int)
            self.assertIsInstance(rank_entry_new.rank, int)
            self.assertIsInstance(rank_entry_new.penalty, int)
            self.assertIsInstance(rank_entry_new.participant, ContestInstance)

            if debug:
                print(rank_entry_new)

            for prob_result_old, prob_result_new in zip(rank_entry_old.problem_results, rank_entry_new.problem_results):
                self.assertEqual(isinstance(prob_result_old.accepted, timedelta), prob_result_new.accepted)
                self.assertEqual(prob_result_old.attempts, prob_result_new.attempts)
                self.assertEqual(prob_result_old.acc_delta, prob_result_new.acc_delta)
                self.assertEqual(prob_result_old.first, prob_result_new.first)
                self.assertEqual(prob_result_old.first_all, prob_result_new.first_all)
                self.assertEqual(prob_result_old.pending, prob_result_new.pending)
                self.assertEqual(prob_result_old.delta(), prob_result_new.delta())

                if debug:
                    print(prob_result_new)


    def full_compare(self, contest, participants, groups=None):
        if isinstance(groups, list):
            groups = list(set(groups))
            for group in groups:
                self.assertIsInstance(group, str)
                self.full_compare(contest, participants, group)

            self.full_compare(contest, participants, None)
            return

        # Point of view of every participant
        for participant in participants:
            self.compare_old_new(contest, group=groups, viewer_instance=participant)

        # Not participant viewer
        self.compare_old_new(contest, group=groups)

        # Can observe viewer
        self.compare_old_new(contest, group=groups, bypass_frozen=True)


    def test_simple(self):
        contest, _ = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, ACCEPTED, 1]
            ],
            checkpoint=timedelta(hours=5),
        )
        self.compare_old_new(contest, debug=False)


    def test_simple_full(self):
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, ACCEPTED, 1]
            ],
            checkpoint=timedelta(hours=5),
        )
        self.full_compare(contest, participants)


    def test_frozen_simple_ac(self):
        """
        Accepted on frozen time.
        """
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=4, minutes=10)]
            ],
            checkpoint=timedelta(hours=4, minutes=30),
        )
        self.full_compare(contest, participants)


    def test_frozen_simple_invalid(self):
        """
        Invalid on frozen time.
        """
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, INVALID, timedelta(hours=4, minutes=10)]
            ],
            checkpoint=timedelta(hours=4, minutes=30),
        )
        self.full_compare(contest, participants)


    def test_frozen_complex(self):
        """
        Checkpoints on frozen time.
        """
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=4),
                timedelta(hours=4, minutes=1),
                timedelta(hours=4, minutes=44),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
            ]
        )


    def test_ignore_problems_after_first_accepted(self):
        """
        Solutions after first AC should be ignored
        """
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, INVALID, 10],
                [0, 0, ACCEPTED, 20],
                [0, 0, INVALID, 30],
                [0, 0, ACCEPTED, 40],
            ],
            checkpoint=timedelta(minutes=50),
        )
        self.full_compare(contest, participants)


    def test_ignore_problems_after_first_accepted_frozen(self):
        """
        Solutions after first AC should be ignored even in frozen/death time.
        """
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, ACCEPTED, 20],
                [0, 0, ACCEPTED, timedelta(hours=4, minutes=10)],
                [0, 0, INVALID, timedelta(hours=4, minutes=45)],
                [0, 0, INVALID, timedelta(hours=4, minutes=50)],
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_death_simple_ok(self):
        """
        Accepted on death time.
        """
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=4, minutes=50)]
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_death_simple_invalid(self):
        """
        Invalid on death time.
        """
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, INVALID, timedelta(hours=4, minutes=50)]
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_death_complex(self):
        """
        Checkpoints on death time.
        """
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=4, minutes=45),
                timedelta(hours=4, minutes=59),
                timedelta(hours=5),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
                [4, 1, ACCEPTED, timedelta(hours=4, minutes=45)],
                [0, 3, INVALID, timedelta(hours=4, minutes=47)],
                [0, 3, ACCEPTED, timedelta(hours=4, minutes=50)],
            ]
        )

    def test_teams_simple(self):
        """
        Test one team Accepted
        """
        contest, participants = self.make_contest(
            num_teams=3,
            submissions=[
                [0, 0, ACCEPTED, 1]
            ],
            checkpoint=timedelta(hours=5),
        )
        self.full_compare(contest, participants)


    def test_unfrozen_complex(self):
        """
        Test submission remain frozen after competition ends
        """
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=5, minutes=10),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
                [4, 1, ACCEPTED, timedelta(hours=4, minutes=45)],
                [0, 3, INVALID, timedelta(hours=4, minutes=47)],
                [0, 3, ACCEPTED, timedelta(hours=4, minutes=50)],
            ],
            after_frozen=timedelta(minutes=15),
        )


    def test_past_complex(self):
        """
        Everyone can see past problems
        """
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=5, minutes=20),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
                [4, 1, ACCEPTED, timedelta(hours=4, minutes=45)],
                [0, 3, INVALID, timedelta(hours=4, minutes=47)],
                [0, 3, ACCEPTED, timedelta(hours=4, minutes=50)],
            ],
            after_frozen=timedelta(minutes=15),
        )


    def test_no_problems(self):
        contest, participants = self.make_contest(
            num_users=3,
            num_problems=0,
            submissions=[],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_no_participants(self):
        contest, participants = self.make_contest(
            submissions=[],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_no_accepted(self):
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, INVALID, timedelta(minutes=10)]
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_no_submissions(self):
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    # TODO(MarX): Don't compare against old calculate, but against expected output
    @skip("New ranking is no compatible with previous ranking on tie-breaks.")
    def test_user_with_same_ranking(self):
        contest, participants = self.make_contest(
            num_users=3,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=0, minutes=10)],
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    # TODO(MarX): Don't compare against old calculate, but against expected output
    @skip("Pending submissions differ from previous implementation")
    def test_ignore_problems_after_first_accepted_frozen(self):
        """
        Ignore submissions in frozen for AC problems before frozen.
        """
        contest, participants = self.make_contest(
            num_users=1,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [0, 0, INVALID, timedelta(hours=4, minutes=23)],
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.compare_old_new(contest)


    def test_not_ignore_problems_after_first_accepted_in_frozen(self):
        """
        Don't ignore pending submissions if the AC was in frozen.
        """
        contest, participants = self.make_contest(
            num_users=1,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=4, minutes=10)],
                [0, 0, INVALID, timedelta(hours=4, minutes=23)],
            ],
            checkpoint=timedelta(hours=4, minutes=55),
        )
        self.full_compare(contest, participants)


    def test_frozen_time_full_contest(self):
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=5),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
                [4, 1, ACCEPTED, timedelta(hours=4, minutes=45)],
                [0, 3, INVALID, timedelta(hours=4, minutes=47)],
                [0, 3, ACCEPTED, timedelta(hours=4, minutes=50)],
            ],
            frozen=timedelta(hours=5),
        )


    def test_death_time_full_contest(self):
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=5),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
                [4, 1, ACCEPTED, timedelta(hours=4, minutes=45)],
                [0, 3, INVALID, timedelta(hours=4, minutes=47)],
                [0, 3, ACCEPTED, timedelta(hours=4, minutes=50)],
            ],
            frozen=timedelta(hours=5),
            death=timedelta(hours=5),
        )


    def test_grouped_simple(self):
        self.make_contest_multiple_checkpoints(
            checkpoints=[
                timedelta(hours=5),
            ],
            num_users=5,
            submissions=[
                [0, 0, ACCEPTED, timedelta(hours=0, minutes=10)],
                [1, 0, INVALID, timedelta(hours=1, minutes=10)],
                [1, 1, ACCEPTED, timedelta(hours=1, minutes=20)],
                [2, 1, INVALID, timedelta(hours=1, minutes=30)],
                [2, 0, INVALID, timedelta(hours=3, minutes=59)],
                [3, 0, ACCEPTED, timedelta(hours=3, minutes=59)],
                [2, 0, ACCEPTED, timedelta(hours=4, minutes=00)],
                [4, 2, ACCEPTED, timedelta(hours=4, minutes=10)],
                [4, 1, ACCEPTED, timedelta(hours=4, minutes=45)],
                [0, 3, INVALID, timedelta(hours=4, minutes=47)],
                [0, 3, ACCEPTED, timedelta(hours=4, minutes=50)],
            ],
            frozen=timedelta(hours=5),
            death=timedelta(hours=5),
            groups=["pinar", "guantanamo", "guantanamo", "pinar", "guest"],
        )
