from django.urls import path

from . import views

urlpatterns = [
    path("state", views.state),
    path("settings", views.save_settings),
    path("plant/<str:serial>", views.save_plant),
    path("lookup", views.lookup),
    path("photo/<str:serial>", views.photo),
    path("history", views.history),
]
