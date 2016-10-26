import json
from api.models import *
from mog.utils import unescape

# import django
# django.setup()
# from api.fixtures import main
# main.fix()
# main.fix_links_in_posts_acm()
# main.unescape_()


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
        if contest.description:
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


def fix_links_in_posts_acm():
    for post in Post.objects.all():
        if post.body:
            soup = BeautifulSoup(post.body, 'html.parser')
            for tag in soup.find_all('a'):
                if tag['href'].startswith('../programacion'):
                    tag['href'] = '#'

                # This link need to point to some ftp
                if tag['href'].startswith('../Documentation'):
                    tag['href'] = '#'

                if tag['href'].startswith('../Problem/Details/'):
                    problem = Problem.objects.get(pk=tag['href'][19:])
                    tag['href'] = reverse('mog:problem', args=(problem.id, problem.slug))

                if tag['href'].startswith('../Contest/Standings/'):
                    contest = Contest.objects.get(pk=tag['href'][21:])
                    tag['href'] = reverse('mog:contest_standing', args=(contest.id, ))

                if tag['href'].startswith('../User/Details/'):
                    user = User.objects.get(pk=tag['href'][16:])
                    tag['href'] = reverse('mog:user', args=(user.id, ))

                if tag['href'].startswith('../Problem/SubmissionDetails/'):
                    try:
                        submission = Submission.objects.get(pk=tag['href'][29:])
                        submission.public = True
                        submission.save()
                        tag['href'] = reverse('mog:submission', args=(submission.id,))
                    except:
                        tag['href'] = '#'
            post.body = soup.prettify()
            post.save()
