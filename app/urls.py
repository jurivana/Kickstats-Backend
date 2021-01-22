from django.urls import path

from . import views

urlpatterns = [
    path('api/meta', views.get_meta),
    path('api/update', views.update_db),
    path('api/users', views.get_users),
    path('api/table', views.get_table),
    path('api/table/<str:username>', views.get_table),
    path('api/points/<str:username>', views.get_points)
]