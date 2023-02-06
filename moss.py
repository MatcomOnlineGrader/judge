import os
import pathlib
import shutil
import sys

import mosspy
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "judge.settings")
django.setup()

from api.models import Submission

MOSS_USER_ID = 544713462


def collect_submissions(contest_id):
    """Given a contest ID, this method returns the information of
    all accepted submissions sent to the contest during the onsite
    (real submissions)."""
    # -
    submissions = Submission.objects.filter(
        problem__contest_id=contest_id,
        result__name__iexact='accepted',
        hidden=False,
        instance__real=True,
    )
    # -
    info = []
    for submission in submissions: 
        problem_letter = submission.problem.letter
        source = submission.source
        # Transform submission language to something MOSS system can
        # understand.
        submission_language = submission.compiler.language.lower()
        submission_language = {
            "c#": "csharp",
            "c++": "cc",
        }.get(submission_language, submission_language)
        # Create the submission filename containing the related instance ID. This
        # will help to indentify two similar submissions from the same user/team
        # by just looking the filename.
        submission_file = "[{}]-{}.{}".format(
            submission.instance.id,
            submission.id,
            submission.compiler.file_extension,
        )
        # -
        info.append((problem_letter, submission_language, submission_file, source))
    # -
    return info


def write_submissions_to_fs(root, submissions):
    pathlib.Path(root).mkdir(parents=True, exist_ok=True)
    buckets = set()
    for problem_letter, submission_language, submission_file, source in submissions:
        bucket_path = os.path.join(root, problem_letter, submission_language)
        pathlib.Path(bucket_path).mkdir(parents=True, exist_ok=True)
        submission_path = os.path.join(bucket_path, submission_file)
        source_clean = ""
        for c in source:
            source_clean += c if ord(c) < 128 else '*'
        with open(submission_path, "w") as f:
            f.write(source_clean)
        buckets.add((bucket_path, problem_letter, submission_language))
    # -
    return list(buckets)


def upload_buckets_to_moss(root, buckets):
    processed_buckets = []

    log_path = os.path.join(root, "log.txt")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            for line in f.readlines():
                problem_letter, submission_language, _, _ = line.split(",")
                processed_buckets.append((problem_letter, submission_language))

    for bucket_path, problem_letter, submission_language in buckets:
        if (problem_letter, submission_language) in processed_buckets:
            print("\n--> skipping {}".format(bucket_path))
            continue
        
        iterations = 1
        while iterations <= 100:
            try:
                m = mosspy.Moss(MOSS_USER_ID, submission_language)
                for filename in list(sorted(os.listdir(bucket_path)))[:90]:
                    m.addFile(os.path.join(bucket_path, filename), filename)

                files = len(m.files)
                print("\n--> [{}] uploading {} [{} files]".format(iterations, bucket_path, files))
                url = m.send(lambda file_path, display_name: print('*', end='', file=sys.stderr, flush=True))

                with open(log_path, "a") as f:
                    f.write("{},{},{},{}\n".format(problem_letter, submission_language, files, url))

                break
            except:
                iterations += 1
        
        if iterations > 3:
            print("\n--> error {}".format(bucket_path))


print("collecting submissions")
contest_id = 6262
submissions = collect_submissions(contest_id)

print("writting submissions to fs")
root = "C:\\Users\\Administrator\\Desktop\\moss-{}".format(contest_id)
buckets = write_submissions_to_fs(root, submissions)

print("uploading buckets")
results = upload_buckets_to_moss(root, buckets)
print(results)
