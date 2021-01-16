from django.urls import path

from . import views

urlpatterns = [
    path('api/update', views.update_db),
    path('api/table', views.get_table),
    path('api/table/<str:username>', views.get_table)
]