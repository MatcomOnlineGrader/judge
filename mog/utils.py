import html
import os

from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.safestring import mark_safe


def get_special_day(date):
    """
    Given a date returns a string describing
    whether that day is special or not. Non
    special days are considered regulars.
    - Valentine Day (February, 14)
    - Halloween (October, 31)
    - Thanksgiving (Fourth Thursday of November)
    - Christmas (19 to 31 of December)
    """
    day = 'regular'
    if date.month == 2 and date.day == 14:
        day = 'valentine'
    if date.month == 10 and date.day == 31:
        day = 'halloween'
    if date.month == 11 and 22 <= date.day <= 28 and date.weekday() == 3:
        day = 'thanksgiving'
    if date.month == 12 and 19 <= date.day <= 31:
        day = 'christmas'
    return day


def unescape(value):
    return mark_safe(html.unescape(value))


def secure_html(html):
    """
    Remove all scrips, forms & events on every tag in
    a chunk of HTML code
    """
    if not html:
        return html
    soup = BeautifulSoup(html, 'html5lib')
    # Remove all scripts
    for tag in soup.find_all('script'):
        tag.extract()
    # Remove all forms
    for tag in soup.find_all('form'):
        tag.extract()
    # Remove all attributes starting with on-
    # to avoid js execution when events fired.
    for tag in soup.findAll():
        for attr in tag.attrs.keys():
            if attr and attr.startswith('on'):
                del tag[attr]
    return soup.prettify()


def user_is_browser(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_browser


def user_is_admin(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_admin


def user_rating(user):
    """return user rating"""
    return user.profile.rating if hasattr(user, 'profile') else 0


def get_tests(problem, folder):
    """get file names living in a problem folder"""
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return []
        return sorted(os.listdir(path))
    return []


def handle_tests(problem, files, folder):
    """copy files into an specified problem folder"""
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return
        for incoming_file in files:
            name = incoming_file.name.replace(' ', '_')  # grader issues
            with open(os.path.join(path, name), 'wb+') as f:
                for chunk in incoming_file.chunks():
                    f.write(chunk)
            incoming_file.close()


def handle_remove_test(problem, folder, test):
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        try:
            os.remove(path)
            return True
        except OSError:
            pass
    return False


def test_content(problem, folder, test):
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = ''.join(f.readlines())
            return content
    return None


def write_to_test(problem, folder, test, content):
    if handle_remove_test(problem, folder, test):
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        with open(path, 'w') as f:
            f.write(content)


class ProblemResult(object):
    def __init__(self, accepted=False, attempts=False, acc_delta=None, first=False, first_all=False):
        self.accepted = accepted
        self.attempts = attempts
        self.acc_delta = acc_delta
        self.first = first
        self.first_all = first_all

    def delta(self):
        if self.acc_delta:
            return self.acc_delta.total_seconds()
        return float('inf')


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


def calculate_standing(contest, virtual=False, user_instance=None):
    instances = contest.instances.all() if virtual else \
        contest.instances.filter(real=True)
    if user_instance:
        user_instance_relative_time =\
            user_instance.relative_time
    problems = contest.problems.order_by('position')
    instance_results = []
    for instance in instances:
        instance_result = InstanceResult(instance=instance)
        for problem in problems:
            submissions = instance.submissions\
                .filter(problem=problem).filter(hidden=False)
            if user_instance and not user_instance.real:
                # If user_instance is virtual, then we need keep only
                # submissions sent no after than user_instance current
                # time.
                if instance.real:
                    submissions = submissions.filter(date__lte=(contest.start_date + user_instance_relative_time))
                else:
                    submissions = submissions.filter(date__lte=(instance.start_date + user_instance_relative_time))
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
                ProblemResult(accepted=acc_delta, attempts=attempts, acc_delta=acc_delta)
            )
        instance_results.append(instance_result)

    def instance_key(ir):
        """Used to sort instances, first by number of solved problems (higher first),
        second by penalty (lower first) and finally, in case of tie, users with the lowest
        greater accepted time comes first, in case of tie, second lowest greater accepted
        time come first, and so on.
        """
        acc_deltas = sorted(
            [problem_result.delta() for problem_result in ir.problem_results],
            key=lambda row: -row
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


def fix_problem_folder(problem):
    folders = [
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id)),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'inputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'outputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'sample inputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'sample outputs'),
    ]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
