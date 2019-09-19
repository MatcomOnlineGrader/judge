from api.models import Submission
from django.db.models import Q
from django.utils.timezone import timedelta


COMPETITION_FASTEST = 'competition-fastest'
PROBLEM_FASTEST = 'problem-fastest'
PENDING_SUBMISSION = 'pending-submission'


class ProblemResult(object):
    """
    This object can be understood as a state machine that
    computes problem results (each cell of the standing).

    Submissions should be feeded in order (from older to newer).
    For every submission relevant information is updated, even
    information from parent (participant result, row containing
    this cell).
    """
    def __init__(self, participant_result, contest_start_date):
        # Wether the problem was accepted or not.
        self.accepted = False
        # Number of attempts before accepting the problem.
        self.attempts = 0
        # Time when the problem was accepted.
        self.acc_delta = None
        # Number of unkown submissions in frozen/death time.
        self.pending = 0

        # Is the first problem accepted solution of the competition.
        self.first = False
        # Is the first problem/participant accepted solution of the competition.
        self.first_all = False

        # We save an instance of the participant view to change its internal
        # variables as we receive new submissions and update our current state.
        self._participant_result = participant_result
        self._contest_start_date = contest_start_date


    def delta(self):
        if self.acc_delta:
            return self.acc_delta.total_seconds()
        return float('inf')


    def add_submission(self, submission, info):
        # Ignore all submissions after the first accepted
        if self.accepted:
            return

        # If submission is pending, user should not see this submission
        if info.get(PENDING_SUBMISSION):
            self.pending += 1
            return

        if info.get(COMPETITION_FASTEST):
            self.first_all = True

        if info.get(PROBLEM_FASTEST):
            self.first = True

        if submission.is_accepted:
            self.acc_delta = submission.date - self._contest_start_date

            self.accepted = True

            self._participant_result.solved += 1
            self._participant_result.penalty += int(self.acc_delta.total_seconds()) // 60 + 20 * self.attempts
            self._participant_result.attempts += self.attempts
            self._participant_result.last_accepted_delta = self.acc_delta.total_seconds()

        elif submission.result.penalty:
            self.attempts += 1

    def __str__(self):
        return f"Accepted:{self.accepted} Attemtps:{self.attempts} Pending:{self.pending} First:{self.first} FirstAll:{self.first_all}"


class ParticipantResult(object):
    """
    This object can be understood as a state machine that
    computes participant results (each row of the standing).

    Submissions should be feeded in order (from older to newer).
    Each submission is given to respective problem_result.
    """
    def __init__(self, participant, problem_mapping, contest_start_date):
        """
        problem_mapping: Dictionary containing {problem.id -> position in the contest (columns)}
        """
        # Number of problems solved so far. Each problem can be solved at most one time.
        # A problem is solved if there is an Accepted submission from this user to this
        # problem. If the submission is in death time it will not be reflected here.
        self.solved = 0
        # Penalty accumulated so far. Only counts penalty of accepted problems.
        self.penalty = 0
        # Sum of total invalid attempts done before accepting each problem.
        self.attempts = 0
        # Position in the ranking.
        self.rank = 1
        # Time of the last accepted problem.
        self.last_accepted_delta = 0

        # Participant instance.
        self.participant = participant
        self.problem_results = [ProblemResult(self, contest_start_date) for _ in problem_mapping]

        self._problem_mapping = problem_mapping


    def add_submission(self, submission, info):
        problem_id = self._problem_mapping.get(submission.problem_id)
        self.problem_results[problem_id].add_submission(submission, info)

    @property
    def instance(self):
        return self.participant

    def __str__(self):
        return f"{self.participant} Solved: {self.solved} Penalty: {self.penalty} Attempts: {self.attempts} Rank: {self.rank}"


def get_relevant_standing_data(contest, virtual=False, group=None, bypass_frozen=False):
    """
    Find relevant submissions/participants/problems to calculate the standing.
    This should hit database 3 times, one per (submissions, participants, problems) query.
    None other access to database is required.
    """
    # Submissions

    submissions = Submission.objects.select_related('result').filter(
        instance__contest__id=contest.id,
        hidden=False
    )

    if not virtual:
        submissions = submissions.filter(instance__real=True)

    if group:
        submissions = submissions.filter(instance__group=group)

    submissions = list(submissions.order_by('date'))

    # Participants
    participants = contest.instances.select_related('team__institution', 'user__profile__institution').all()

    if not virtual:
        participants = participants.filter(real=True)

    if group:
        participants = participants.filter(group=group)

    # Problems
    problems = list(contest.problems.order_by('position'))
    participants = list(participants)

    return submissions, participants, problems


def calculate_standing_new(contest, virtual=False, viewer_instance=None, group=None, bypass_frozen=False):
    # Load relevant data from database
    submissions, participants, problems = \
        get_relevant_standing_data(contest, virtual, group, bypass_frozen)

    # Relative time used for virtual participants
    if viewer_instance:
        viewer_instance_relative_time =\
            viewer_instance.relative_time

    # Helper functions

    def submission_relevance(submission):
        """
        Rules to filter whether a submission should be shown to this user.

        Return value:
            -1: Ignore this submission.
             0: Add this submission as pending.
            +1: Add this submission.
        """
        # Pending submissions are not taken into account while building standing.
        if submission.is_pending:
            return -1

        # user can bypass fozen time, this imply their can see the contest
        # without any pending submissions.
        if bypass_frozen:
            return +1

        if viewer_instance and not viewer_instance.real:
            delta = submission.date - submission.instance.instance_start_date
            if delta > viewer_instance_relative_time:
                # For virtual participants don't show submissions that haven't
                # passed according to its relative time in the contest.
                return -1

        # In the standing only normal submissions can bee seen.
        if submission.is_normal:
            return +1
        else:
            return 0

    problem_mapping = {
        problem.id : ix for (ix, problem) in enumerate(problems)
    }

    standing = {
        participant.id : ParticipantResult(
            participant,
            problem_mapping,
            participant.instance_start_date,
        ) for participant in participants
    }

    # Keep track of all problem accepted so far to determine first accepted per problem and
    # first accepted globally in the competition.
    problem_accepted = [False] * len(problems)
    some_accepted = False

    for submission in submissions:
        info = {}

        result = submission_relevance(submission)

        if result == -1:
            # Ignore this submission
            continue

        problem_id = problem_mapping.get(submission.problem_id)

        if result == 0:
            info[PENDING_SUBMISSION] = True
        else:
            # Detect competition/problem fastest submission
            # Note: Do this only when this submission is public for this user.
            if submission.is_accepted:
                if not some_accepted:
                    some_accepted = True
                    problem_accepted[problem_id] = True

                    info[COMPETITION_FASTEST] = True
                    info[PROBLEM_FASTEST] = True

                elif not problem_accepted[problem_id]:
                    problem_accepted[problem_id] = True
                    info[PROBLEM_FASTEST] = True

        participant_id = submission.instance_id
        standing[participant_id].add_submission(submission, info)

    participants_result = list(standing.values())

    # Sort participants according to their results
    def instance_key(participant_result):
        """
        According to: https://icpc.baylor.edu/worldfinals/rules#HScoringoftheFinals
        Sort by:
            - Maximum count of problem solved.
            - Least penalty.
            - Least time of last Accepted.
            - Instance id (this is not relevant to the rank but to keep order consistent among requests.)
        """
        return -participant_result.solved, participant_result.penalty, participant_result.last_accepted_delta, participant_result.participant.id

    participants_result.sort(key=instance_key)

    # Build ranking
    # Participant rank is equal to the number of participants with a result strictly better
    # than her/him plus one. Several participants can have the same ranking.
    if len(participants_result) > 0:
        participants_result[0].rank = 1

        for i in range(1, len(participants_result)):
            if instance_key(participants_result[i])[:-1] == instance_key(participants_result[i - 1])[:-1]:
                participants_result[i].rank = participants_result[i - 1].rank
            else:
                participants_result[i].rank = i + 1

    return problems, participants_result
