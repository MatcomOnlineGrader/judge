from api.models import Submission
from django.db.models import Q
from django.utils.timezone import timedelta


# TODO(MarX): Remove ProblemResult in favor of ProblemResultNew.
class ProblemResult(object):
    def __init__(self, accepted=False, attempts=False, acc_delta=None, first=False, first_all=False, pending=0):
        self.accepted = accepted
        self.attempts = attempts
        self.acc_delta = acc_delta
        self.first = first
        self.first_all = first_all
        self.pending = pending

    def delta(self):
        if self.acc_delta:
            return self.acc_delta.total_seconds()
        return float('inf')


# TODO(MarX): Remove InstanceResult in favor of ParticipantResult.
class InstanceResult(object):
    def __init__(self, instance=None, problem_results=None, rank=1, solved=0, penalty=0):
        self.instance = instance
        self.solved = solved
        self.rank = rank
        self.penalty = penalty
        self.problem_results = []
        if problem_results:
            for problem_result in problem_results:
                self.add_problem_result(problem_result)

    def attempts(self):
        return sum([pr.attempts for pr in self.problem_results])

    def add_problem_result(self, problem_result):
        if problem_result.accepted:
            self.solved += 1
            self.penalty += problem_result.acc_delta.total_seconds() / 60 + 20 * problem_result.attempts
        self.problem_results.append(problem_result)


COMPETITION_FASTEST = 'competition-fastest'
PROBLEM_FASTEST = 'problem-fastest'
PENDING_SUBMISSION = 'pending-submission'


# TODO(MarX):Rename to ProblemResult
class ProblemResultNew(object):
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
        self.problem_results = [ProblemResultNew(self, contest_start_date) for _ in problem_mapping]

        self._problem_mapping = problem_mapping


    def add_submission(self, submission, info):
        problem_id = self._problem_mapping.get(submission.problem_id)
        self.problem_results[problem_id].add_submission(submission, info)

    @property
    def instance(self):
        return self.participant

    def __str__(self):
        return f"{self.participant} Solved: {self.solved} Penalty: {self.penalty} Attempts: {self.attempts} Rank: {self.rank}"


def calculate_standing_old(contest, virtual=False, viewer_instance=None, group=None, bypass_frozen=False):
    instances = contest.instances.all() if virtual else \
        contest.instances.filter(real=True)
    if group:
        instances = instances.filter(group=group)
    if viewer_instance:
        viewer_instance_relative_time =\
            viewer_instance.relative_time
    problems = contest.problems.order_by('position')
    instance_results = []
    for instance in instances:
        instance_result = InstanceResult(instance=instance)
        for problem in problems:
            if bypass_frozen:
                # User has special role, this imply he/she can see the contest
                # without any pending submissions.
                pending_submissions = 0
                submissions = instance.submissions\
                    .filter(Q(problem=problem) & Q(hidden=False))
            elif viewer_instance:
                if viewer_instance.real:
                    # If the instance looking at the ranking is real (participant),
                    # then two cases may follow:
                    # 1) The user is looking at his/her row. In this case he/she will
                    #    be able to see all his/her submissions except death
                    #    submissions (frozen & normal). Pending submissions will
                    #    be death submissions.
                    # 2) The user is looking at another row. In this case he/she will
                    #    be able to see only normal submissions for this row. Pending
                    #    submissions will be frozen & death submissions.
                    if viewer_instance == instance:
                        # case1
                        pending_submissions = instance.submissions\
                            .filter(Q(problem=problem) & Q(hidden=False) & Q(status='death')).count()
                        submissions = instance.submissions\
                            .filter(Q(problem=problem) & Q(hidden=False) & (Q(status='normal') | Q(status='frozen')))
                    else:
                        # case2
                        pending_submissions = instance.submissions\
                            .filter(Q(problem=problem) & Q(hidden=False) & ~Q(status='normal')).count()
                        submissions = instance.submissions\
                            .filter(Q(problem=problem) & Q(hidden=False) & Q(status='normal'))
                else:
                    # if the instance is virtual, then it will simulate the contest,
                    # the number of pending submissions will be 0 because here frozen/death
                    # time are disabled.
                    pending_submissions = 0
                    if instance.real:
                        submissions = instance.submissions.filter(
                            Q(problem=problem) &
                            Q(hidden=False) &
                            Q(date__lte=(contest.start_date + viewer_instance_relative_time))
                        )
                    else:
                        submissions = instance.submissions.filter(
                            Q(problem=problem) &
                            Q(hidden=False) &
                            Q(date__lte=(instance.start_date + viewer_instance_relative_time))
                        )
            else:
                # user not registered in contest, in this case, only normal solutions will
                # be displayed (solutions before frozen time), pending solutions will be
                # those submissions marked as 'frozen' or 'death'.
                submissions = instance.submissions\
                    .filter(Q(problem=problem) & Q(hidden=False) & Q(status='normal'))
                pending_submissions = instance.submissions\
                    .filter(Q(problem=problem) & Q(hidden=False) & (Q(status='frozen') | Q(status='death'))).count()

            accepted, attempts, acc_delta = 0, False, None
            accepted_submission = submissions\
                .filter(result__name__iexact='accepted').order_by('date').first()
            if accepted_submission:
                attempts = submissions\
                    .filter(result__penalty=True, date__lt=accepted_submission.date).count()
                if instance.real:
                    acc_delta = accepted_submission.date - contest.start_date
                else:
                    acc_delta = accepted_submission.date - instance.start_date
            else:
                attempts = submissions.filter(result__penalty=True).count()
            instance_result.add_problem_result(
                ProblemResult(accepted=acc_delta, attempts=attempts, acc_delta=acc_delta, pending=pending_submissions)
            )
        instance_results.append(instance_result)

    def instance_key(ir):
        """Used to sort instances, first by number of solved problems (higher first),
        second by penalty (lower first) and finally, in case of tie, users with the lowest
        greater accepted time comes first, in case of tie, second lowest greater accepted
        time come first, and so on.
        """
        acc_deltas = sorted(
            [problem_result.delta() for problem_result in ir.problem_results], key=lambda row: -row
        )
        return -ir.solved, ir.penalty, acc_deltas

    instance_results.sort(key=instance_key)

    # set ranks
    for i in range(1, len(instance_results)):
        if instance_key(instance_results[i]) == instance_key(instance_results[i - 1]):
            instance_results[i].rank = instance_results[i - 1].rank
        else:
            instance_results[i].rank = instance_results[i - 1].rank + 1

    # find first accepted submission by problem and in the
    # contest in general.
    global_instance, global_min_delta = None, float('inf')
    for i in range(len(problems)):
        local_instance, local_min_delta = None, float('inf')
        for ir in instance_results:
            delta = ir.problem_results[i].delta()
            if delta < local_min_delta:
                local_instance, local_min_delta = ir.problem_results[i], delta
                if delta < global_min_delta:
                    global_instance, global_min_delta = ir.problem_results[i], delta
        if local_instance:
            local_instance.first = True

    if global_instance:
        global_instance.first_all = True

    return problems, instance_results


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

    submissions = submissions.order_by('date')

    # Participants
    participants = contest.instances.all()

    if not virtual:
        participants = participants.filter(real=True)

    if group:
        participants = participants.filter(group=group)

    # Problems
    problems = contest.problems.order_by('position')

    return list(submissions), list(participants), list(problems)


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

        if viewer_instance:
            if not viewer_instance.real:
                delta = submission.date - submission.instance.instance_start_date
                if delta > viewer_instance_relative_time:
                    # For virtual participants don't show submissions that haven't
                    # passed according to its relative time in the contest.
                    return -1

            # Two cases may follow:
            # 1) The user is looking at their row. In this case they will
            #    be able to see all their submissions except death
            #    submissions (frozen & normal). Pending submissions will
            #    be death submissions.
            # 2) The user is looking at another row. In this case they will
            #    be able to see only normal submissions for this row. Pending
            #    submissions will be frozen & death submissions.

            if submission.is_normal:
                return +1

            elif submission.is_death:
                return 0

            elif submission.is_frozen:
                if submission.instance == viewer_instance:
                    return +1
                else:
                    return 0
        else:
            # This is a guest (user not participating in the contest or not logged)
            # They can't see any submission in frozen time.
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


def calculate_standing(contest, virtual=False, viewer_instance=None, group=None, bypass_frozen=False):
    return calculate_standing_new(contest, virtual, viewer_instance, group, bypass_frozen)
