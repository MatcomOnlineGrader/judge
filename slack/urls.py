from django.conf.urls import url
from . import views

app_name = 'slack'

urlpatterns = [
    url(r'^statistics/$', views.statistics, name='statistics'),
    url(r'^standing/$', views.standing, name='standing'),
]
