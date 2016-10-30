import json
from api.models import *
from mog.utils import unescape


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def analyze(function):
    def inner(link):
        result = function(link)
        # all urls will be relative, so skip any link with http or https prefix
        if link.startswith('http') or link.startswith('https'):
            return result
        # if link.startswith('http://coj') or link.startswith('https://icpc') or \
        #         link.startswith('https://kattis') or link.startswith('http://code') or \
        #         link.startswith('http://static') or link.startswith('http://icpc') or \
        #         link.startswith('https://en') or link.startswith('http://spoj') or \
        #         link.startswith('https://coj') or link.startswith('http://www.icpc') or \
        #         link.startswith('http://www.comp') or link.startswith('http://www.almam') or \
        #         link.startswith('http://www.spoj') or link.startswith('http://www.codef') or \
        #         link.startswith('http://es.w'):

        # Warning on unconverted links (len(link) < 1000 -> avoid display encode64 images)
        if len(link) < 1000 and link == result:
            print link, '<--->', result
        return result
    return inner


@analyze
def fix_link(link):
    # link to data
    if link.lower().startswith('http://judge.matcom.uh.cu/data/userfiles/'):
        return settings.MEDIA_URL + link[41:]

    if link.lower().startswith('/data/userfiles/'):
        return settings.MEDIA_URL + link[16:]

    if link.lower().startswith('../../content/uploads/'):
        # FIXME: Files inside content/uploads needs to be copied from that folder
        # FIXME: into media folder. The do not belong to UserFiles folder.
        return settings.MEDIA_URL + 'content/uploads/' + link[22:]

    if link.lower().startswith('../content/uploads/'):
        # FIXME: Files inside content/uploads needs to be copied from that folder
        # FIXME: into media folder. The do not belong to UserFiles folder.
        return settings.MEDIA_URL + 'content/uploads/' + link[19:]

    # link to contest
    if link.lower().startswith('http://judge.matcom.uh.cu/contest/'):
        if '/' in link[34:]:
            code, tail = link[34:].split('/')
        else:
            code, tail = link[34:], None
        contest = Contest.objects.filter(code=code).first()
        if contest:
            if not tail:
                # link to contest problems
                return reverse('mog:contest_problems', args=(contest.id,))
            elif tail.lower() == 'standings':
                # link to contest standings
                return reverse('mog:contest_standing', args=(contest.id,))
            elif len(tail) == 1:
                # link to contest problem
                position = ord(tail.lower()) - ord('a') + 1
                problem = contest.problems.filter(position=position).first()
                if problem:
                    return reverse('mog:problem', args=(problem.id, problem.slug))

    # link to post
    if link.lower().startswith('http://judge.matcom.uh.cu/post/'):
        post = Post.objects.filter(pk=link[31:]).first()
        if post:
            return reverse('mog:post', args=(post.id, post.slug))

    # link to user
    if link.lower().startswith('http://judge.matcom.uh.cu/user/'):
        user = User.objects.filter(username__iexact=link[31:]).first()
        if user:
            return reverse('mog:user', args=(user.id, ))

    # link to problem
    if link.lower().startswith('../problem/details/'):
        problem = Problem.objects.filter(pk=link[19:]).first()
        if problem:
            return reverse('mog:problem', args=(problem.id, problem.slug))

    # link to submission
    if link.lower().startswith('../problem/submissiondetails/'):
        submission = Submission.objects.filter(pk=link[29:]).first()
        if submission:
            # Make this submission public to everyone
            submission.public = True
            submission.save()
            return reverse('mog:submission', args=(submission.id,))

    # link to submission
    if link.lower().startswith('http://judge.matcom.uh.cu/submission/'):
        submission = Submission.objects.filter(pk=link[37:]).first()
        if submission:
            return reverse('mog:submission', args=(submission.id, ))

    # link to contest
    if link.lower().startswith('../contest/details/'):
        contest = Contest.objects.filter(pk=link[19:]).first()
        if contest:
            return reverse('mog:contest_problems', args=(contest.id, ))

    # link to contest
    if link.lower().startswith('../contest/'):
        if '/' in link[11:]:
            code, tail = link[11:].split('/')
        else:
            code, tail = link[11:], None
        contest = Contest.objects.filter(code=code).first()
        if contest:
            if not tail:
                # link to contest problems
                return reverse('mog:contest_problems', args=(contest.id, ))
            elif tail == 'standings':
                return reverse('mog:contest_standing', args=(contest.id,))

    # link to contest standings
    if link.lower().startswith('../contest/standings/'):
        contest = Contest.objects.filter(pk=link[21:]).first()
        if contest:
            return reverse('mog:contest_standing', args=(contest.id, ))

    # link to user
    if link.lower().startswith('../user/details/'):
        user = User.objects.filter(pk=link[16:]).first()
        if user:
            return reverse('mog:user', args=(user.id, ))

    return link


def fix_tags():
    # Remove problem-tags
    for problem in Problem.objects.all():
        problem.tags.clear()
    # Add new ones from fixtures
    with open(os.path.join(BASE_DIR, 'problem_tags.json'), 'r') as f:
        for row in json.load(f):
            problem_id = row['fields']['problem_id']
            tag_id = row['fields']['tag_id']
            problem = Problem.objects.filter(pk=problem_id).first()
            tag = Tag.objects.filter(pk=tag_id).first()
            if problem and tag:
                problem.tags.add(tag)


def fix_problems():
    for problem in Problem.objects.all():
        # Slugify the problem title
        problem.slug = slugify(problem.title)
        for field in ['body', 'input', 'output', 'hints']:
            value = getattr(problem, field)
            if value:
                # Unescape html
                value = unescape(value)
                # Creates a soup html tree
                soup = BeautifulSoup(value, 'html.parser')
                # Fix hyperlink references
                for a in soup.find_all('a'):
                    a['href'] = fix_link(a['href'])
                # Fix image sources
                for img in soup.find_all('img'):
                    img['src'] = fix_link(img['src'])
                setattr(problem, field, soup.prettify())
        problem.save()


def fix_contests():
    for contest in Contest.objects.all():
        if contest.description:
            # Unescape description html
            value = unescape(contest.description)
            # Creates a soup html tree
            soup = BeautifulSoup(value, 'html.parser')
            # Fix hyperlink references
            for a in soup.find_all('a'):
                a['href'] = fix_link(a['href'])
            # Fix image sources
            for img in soup.find_all('img'):
                img['src'] = fix_link(img['src'])
        # Set contest rated iff there is some rating change
        contest.rated = contest.rating_changes.count() > 0
        contest.save()


def fix_posts():
    for post in Post.objects.order_by('modification_date'):
        # Slugify the post name
        post.slug = slugify(post.name)
        if post.body:
            # Unescape body html
            value = unescape(post.body)
            # Creates a soup html tree
            soup = BeautifulSoup(value, 'html.parser')
            # Fix hyperlink references
            for a in soup.find_all('a'):
                a['href'] = fix_link(a['href'])
            # Fix image sources
            for img in soup.find_all('img'):
                img['src'] = fix_link(img['src'])
            post.body = soup.prettify()
        post.save()


def fix_comments():
    # First, fix seen/unseen comments
    with open(os.path.join(BASE_DIR, 'comment_seen.json'), 'r') as f:
        # Prefetch users & comments to fast lookup
        users = User.objects.order_by('pk')
        comments = Comment.objects.all()
        comments_dict = dict([(comment.pk, comment) for comment in comments])

        # Extract (user, comment) only from each row.
        rows = map(lambda row: (row['fields']['user_id'], row['fields']['comment_id']), json.load(f))
        rows.sort()

        i, ptr = 0, 0
        while i < len(rows):
            j = i
            while j < len(rows) and rows[i][0] == rows[j][0]:
                j += 1
            while users[ptr].pk < rows[i][0]:
                ptr += 1
            user = users[ptr]
            user.seen_comments.clear()
            user.seen_comments.add(
                *[comments_dict[rows[k][1]] for k in range(i, j) if rows[k][1] in comments_dict]
            )
            i = j

    # Strip all html from comments
    for comment in Comment.objects.order_by('date'):
        soup = BeautifulSoup(comment.body, 'html.parser')
        comment.body = soup.text
        comment.save()


def fix_teams():
    # Remove profile-teams
    for user in User.objects.all():
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user)
        user.profile.teams.clear()

    # Add new ones from fixtures
    with open(os.path.join(BASE_DIR, 'userprofile_teams.json'), 'r') as f:
        for row in json.load(f):
            user_id = row['fields']['user_id']
            team_id = row['fields']['team_id']
            User.objects.get(pk=user_id).profile.teams.add(
                Team.objects.get(pk=team_id)
            )

    # Add institution to teams. Simply select
    # any member with non blank institution and
    # attach it to team.
    for team in Team.objects.all():
        profile = team.profiles.filter(~Q(institution=None)).first()
        if profile.institution:
            team.institution = profile.institution
            team.save()


def fix_users():
    # Add user profiles
    for user in User.objects.all():
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user)


# $ python manage.py shell --settings=judge.settings.production
# or
# $ python manage.py shell --settings=judge.settings.development
# import django
# django.setup()
# from api.fixtures.main import fix_all
# fix_all()
def fix_all():
    print '::: fixing users'
    fix_users()
    print '::: fixing teams'
    fix_teams()
    print '::: fixing comments'
    fix_comments()
    print '::: fixing posts'
    fix_posts()
    print '::: fixing problems'
    fix_problems()
    print '::: fixing problems-tags'
    fix_tags()
    print '::: DONE'
