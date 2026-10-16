from django.contrib import admin
from django.urls import include, path

from accounts.views import test_page
from core import views

urlpatterns = [
    path("health", views.health),
    path("api/auth/", include("accounts.urls")),
    path("test/accounts", test_page),
    path("admin/", admin.site.urls),
]
