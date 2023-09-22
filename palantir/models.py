from django.contrib.auth.models import User
from django.db import models


class AccessLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)
    message = models.TextField(default="{}")
    slug = models.CharField(max_length=1024)

    def __str__(self):
        return self.slug
