"""
This command assign balloon colors to the problems of a contest with a set of predefined "nice-looking" colors
"""

from django.core.management import BaseCommand
from api.models import Contest, Problem
import random

class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('--contest', type=int, default='',
                            help='Id of the contest to set the balloon colors')

    def handle(self, *args, **options):
        contest_id = options.get('contest')

        colors = ['#5acafa', #light blue
                  '#ff2121', #red
                  '#a642b3', #violet
                  '#fff024', #yellow
                  '#3d3d3d', #black
                  '#00ff15', #green
                  '#3636ff', #dark blue
                  '#b3b3b3', #gray
                  '#a86f25', #brown
                  '#ffa51f', #orange
                  '#ff66ff', #pink
                  '#4d9900'  #dark green
                  ]

        contest = Contest.objects.get(pk=contest_id)
        n_problems = len(list(contest.problems.all()))
        if n_problems > len(colors):
            print('ERROR: nor enough colors for this contest')
        else:
            random.shuffle(colors)
            for problem in contest.problems.all():
                problem.balloon = colors[problem.position-1]
                problem.letter_color = 'white'
                problem.save()
                print('Problem %d Color: %s' % (problem.id, problem.balloon))




