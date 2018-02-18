import os
import requests
import uuid
import urllib

from django.conf import settings


def associate_avatar(backend, strategy, details, response,
        user=None, *args, **kwargs):
    try:
        if not user.profile.avatar:
            url = None
            if backend.name == 'facebook':
                url = 'http://graph.facebook.com/%s/picture?type=large' % response['id']
            if backend.name == 'github':
                url = 'https://avatars3.githubusercontent.com/u/%s' % response['id']
            if backend.name == 'google-oauth2':
                url = urllib.parse.splitquery(response['image']['url'])[0]
            page = requests.get(url)
            if page.ok:
                extension = None
                if 'Content-Type' in page.headers:
                    content_type = page.headers['Content-Type'].lower()
                    if content_type.startswith('image/'):
                        extension = content_type.split('/')[-1]
                if not extension:
                    extension = 'jpeg'  # fallback image extension
                # save photo to a file
                path = 'user/avatar/%s.%s' % (str(uuid.uuid4()), extension)
                with open(os.path.join(settings.MEDIA_ROOT, path), 'wb') as f:
                    f.write(page.content)
                user.profile.avatar = path
                user.profile.save()
    except:
        pass
