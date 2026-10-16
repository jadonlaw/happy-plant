from django.urls import path

from . import views

urlpatterns = [
    path("csrf", views.csrf),
    path("me", views.me),
    path("signup", views.signup),
    path("verify", views.verify),
    path("resend", views.resend),
    path("login", views.login_view),
    path("logout", views.logout_view),
    path("reset/request", views.reset_request),
    path("reset/confirm", views.reset_confirm),
]
