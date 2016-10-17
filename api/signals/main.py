from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.models import UserProfile, Submission


@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if created:
        UserProfile(user=instance).save()
