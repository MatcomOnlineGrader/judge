"""
Report useful statistics for a contest regarding submissions by participants.

Fetch similar information to which is reported in World Finals.
For more details see: http://www.csc.kth.se/~austrin/icpc/finals2019solutions.pdf


+ First to solve per problem.
+ Number of different participants trying each problem.
+ Number of different participanss solving each problem.
+ Smallest AC solution from judges per problem.
+ Smallest AC solution from participants per problem.
+ List of AC/WA/RTE/TLE/ per problem with time.
"""

from api.models import Submission, Problem
from json import dumps


def get_contest_stats(contest):
    problems = Problem.objects.filter(contest_id=contest.id)

    submissions = Submission.objects.select_related('result').filter(problem__contest__id=contest.id)

    contest_start = contest.start_date
    contest_end = contest.end_date

    info = [{
        "submissions": [],  # (Time in minute, veredict)
        "tried": set(),  # Participants
        "accepted": set(),  # Participants
        "shortest_code_participant": float('inf'),
        "shortest_code_judge": float('inf'),
        "title": prob.title,
        "first_solve": float('inf'),
        "position": prob.position,
    } for prob in problems]

    info.sort(key=lambda x: x['position'])

    interesting = {
        "Accepted",
        "Wrong Answer",
        "Time Limit Exceeded",
        "Runtime Error"
    }

    for sub in submissions:
        position = sub.problem.position - 1

        if sub.hidden:
            if str(sub.result) == "Accepted":
                info[position]["shortest_code_judge"] = min(info[position]["shortest_code_judge"], len(sub.source))

            # Ignore hidden solutions
            continue

        if sub.date > contest_end:
            # Ignore solution out of contest
            continue

        minutes = int((sub.date - contest_start).total_seconds() / 60)

        if str(sub.result) == "Accepted":
            info[position]['accepted'].add(sub.user.id)
            info[position]['shortest_code_participant'] = min(info[position]['shortest_code_participant'],
                                                              len(sub.source))
            info[position]['first_solve'] = min(info[position]['first_solve'], minutes)

        if str(sub.result) in interesting:
            info[position]['tried'].add(sub.user.id)
            info[position]['submissions'].append((minutes, str(sub.result), sub.compiler.language))

    for prob in info:
        prob['submissions'].sort()
        prob['tried'] = len(prob['tried'])
        prob['accepted'] = len(prob['accepted'])

    return dumps(info)