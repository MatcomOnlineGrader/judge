from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string

from api import models
from mog.decorators import asynchronous

@asynchronous
def send_email(subject, message, recipients):
    """Send the same email to several recipients.   
    
    Parameters
    ----------
    subject : str,
              Email's subject.
    
    message : str,
              Email's body.
    
    recipients : list,
                 List containing email addresses.
    """
    for email in recipients:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True
        )


def report_clarification(clarification):
    """Send an email to every admin to handle this
    clarification.
    
    Parameters
    ----------
    clarification: Clarification,
                   api.models.Clarification instance
    """
    subject = 'Clarification request'
    message = render_to_string('mog/email/clarification.txt', {
        'clarification': clarification,
        'domain': 'http://%s' % Site.objects.get(pk=settings.SITE_ID).domain
    })

    admins = set(user.email for user in User.objects.filter(profile__role='admin'))
    judges = set(permission.user.email for permission in models.ContestPermission.objects.filter(contest=clarification.contest, role='judge', granted=True))
    recipients = list(admins.union(judges))

    send_email(
        subject=subject,
        message=message,
        recipients=recipients
    )
