from django.urls import path

from . import views

urlpatterns = [
    path("", views.my_units),
    path("pair", views.pair),
    path("<str:serial>/remove", views.remove),
    path("<str:serial>/live", views.live),
]
