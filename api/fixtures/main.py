import json
from api.models import *
from mog.utils import unescape


def fix():
    print 'slugify problem titles'
    for problem in Problem.objects.all():
        problem.slug = slugify(problem.title)
        problem.save()

    print 'slugify post name'
    for post in Post.objects.all():
        post.slug = slugify(post.name)
        post.save()

    print 'create profiles'
    for user in User.objects.all():
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user)

    print 'insert to api_userprofile_teams'
    with open('userprofile_teams.json', 'r') as f:
        for row in json.load(f):
            user_id = row['fields']['user_id']
            team_id = row['fields']['team_id']
            User.objects.get(pk=user_id).profile.teams.add(
                Team.objects.get(pk=team_id)
            )

    print 'insert to api_problem_tags'
    with open('problem_tags.json', 'r') as f:
        for row in json.load(f):
            problem_id = row['fields']['problem_id']
            tag_id = row['fields']['tag_id']
            try:
                problem = Problem.objects.get(pk=problem_id)
                tag = Tag.objects.get(pk=tag_id)
                problem.tags.add(tag)
            except:
                pass

    print 'insert to api_comment_seen'
    with open('comment_seen.json', 'r') as f:
        for row in json.load(f):
            user_id = row['fields']['user_id']
            comment_id = row['fields']['comment_id']
            try:
                comment = Comment.objects.get(pk=comment_id)
                User.objects.get(pk=user_id).seen_comments.add(comment)
            except:
                pass


def unescape_():
    for contest in Contest.objects.all():
        contest.description = unescape(contest.description)
        contest.save()

    for post in Post.objects.order_by('modification_date'):
        if post.body:
            post.body = unescape(post.body)
        post.save()

    for problem in Problem.objects.all():
        if problem.body:
            problem.body = unescape(problem.body)
        if problem.input:
            problem.input = unescape(problem.input)
        if problem.output:
            problem.output = unescape(problem.output)
        if problem.hints:
            problem.hints = unescape(problem.hints)
        problem.save()
