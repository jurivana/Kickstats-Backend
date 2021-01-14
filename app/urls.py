from django.urls import path

from . import views

urlpatterns = [
    path('api/update', views.update_db, name='index'),
]