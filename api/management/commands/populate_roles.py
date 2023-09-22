"""
This command is to change role for a bulk of user at the same time.
It will add entries to the ContestPermission table.

Note: ContestPermission works as a log table, so only last entry for
each tuple (user, contest) will matter.
"""

from django.core.management import BaseCommand

from api.models import Contest, ContestPermission
from django.contrib.auth.models import User


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("-u", "--usernames", type=str, dest="usernames_path")
        parser.add_argument(
            "-c", "--contest_code", type=str, dest="code", help="Contest code"
        )
        parser.add_argument(
            "-n", "--no_granted", action="store_true", dest="no_granted", default=False
        )
        parser.add_argument("-r", "--role", dest="role", choices=["judge", "observer"])

    def handle(self, *args, **options):
        usernames_path = options.get("usernames_path")

        with open(usernames_path) as username_fd:
            required_usernames = username_fd.read().strip(" \n").split("\n")
            required_usernames = [user.strip(" ") for user in required_usernames]

        current_users = User.objects.filter(username__in=required_usernames)

        not_found = 0

        for user in required_usernames:
            if not current_users.filter(username=user).exists():
                print(f"User {user} not found.")
                not_found += 1

        if not_found > 0:
            print("Some users were not found. Update the list first.")
            return

        granted = not options.get("no_granted")
        contest = Contest.objects.get(code=options.get("code"))
        role = options.get("role")

        assert role in ("judge", "observer")

        action = "Adding" if granted else "Removing"

        print(f"{action} role {role} for contest {contest} to:")
        print("\n".join("+ " + user.username for user in current_users))

        for user in current_users:
            perm = ContestPermission(
                user=user,
                contest=contest,
                role=role,
                granted=granted,
            )
            perm.save()

        print("Done.")
