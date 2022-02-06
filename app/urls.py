from django.urls import path

from . import views

urlpatterns = [
    path('meta', views.get_meta),
    path('update', views.update_db),
    path('users', views.get_users),
    path('table/<str:username>', views.get_table),
    path('points/<str:username>', views.get_points),
    path('highlights', views.get_highlights),
    path('highlights/<str:username>', views.get_highlights_user)
]
