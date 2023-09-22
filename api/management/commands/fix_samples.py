"""
This command reads the sample test cases from the hard drive and stores them in the database.

NOTE: This command should be run after the branch `sample_tests` is
merged in master and pushed to our prod database.
"""
import os
import json

from django.core.management import BaseCommand
from api.models import Problem
from django.conf import settings


def legacy_get_tests(problem, folder):
    """get file names living in a problem folder"""
    if folder in ["inputs", "outputs", "sample inputs", "sample outputs"]:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return []
        return sorted(os.listdir(path))

    return []


def legacy_test_content(problem, folder, test):
    if folder in ["sample inputs", "sample outputs"]:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        if os.path.exists(path):
            with open(path, "r") as f:
                content = "".join(f.readlines())
            return content
    return None


def get_samples_json(problem):
    # create structure for the json-dictionary
    result = dict()
    input_names = sorted(legacy_get_tests(problem, "sample inputs"))
    output_names = sorted(legacy_get_tests(problem, "sample outputs"))

    if len(input_names) != len(output_names):
        print(
            "WARNING: Problem %d has different number of input and output samples"
            % problem.id
        )

    for i, (input_name, output_name) in enumerate(zip(input_names, output_names)):
        name = "sample{:02d}".format(i + 1)
        result[name] = dict()
        result[name]["in"] = legacy_test_content(problem, "sample inputs", input_name)
        result[name]["out"] = legacy_test_content(
            problem, "sample outputs", output_name
        )

    return json.dumps(result)


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def handle(self, *args, **options):
        problems = Problem.objects.all()
        for problem in problems:
            samples_json = get_samples_json(problem)
            problem.samples = samples_json
            problem.save()
            print("Successfully stored samples for Problem %d" % problem.id)
