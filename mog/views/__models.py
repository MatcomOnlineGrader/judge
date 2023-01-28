from typing import List, Dict
from datetime import datetime

class _Instance():
    def __init__(self):
        self.pk: int = None
        self.id: int = None
        self.group: str = None
        self.render_team_description_only: bool = None
        self.team: _Team = None
        self.user: _User = None
    def __str__(self):
        if self.team:
            return 'Team: ' + self.team.name
        return self.user.username

class _User():
    def __init__(self):
        self.pk: int = None
        self.id: float = None
        self.username: str = None
        self.last_login: datetime = None
        self.profile: _UserProfile = None
    def __str__(self) -> str:
        return self.username

class _UserProfile():
    def __init__(self):
        self.user: _User = None
        self.rating: int = None
    def __str__(self) -> str:
        return self.user

class _TeamProfiles():
    def __init__(self):
        self.profiles: List[_UserProfile] = []
    def all(self) -> List[_UserProfile]:
        return self.profiles
    def append(self, user: _UserProfile):
        self.profiles.append(user)

class _Team():
    def __init__(self):
        self.pk: int = None
        self.id: int = None
        self.name: str = None
        self.profiles: _TeamProfiles = None
    def __str__(self):
        return '{0} ({1})'.format(
            self.name,
            ', '.join([profile.user.username for profile in self.profiles.all()])
        )
