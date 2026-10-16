from django.contrib import admin
from django.urls import include, path

from accounts.views import test_page as accounts_test_page
from core import views
from units.views import test_page as units_test_page

admin.site.site_header = "Happy Plant admin"
admin.site.site_title = "Happy Plant admin"

urlpatterns = [
    path("health", views.health),
    path("api/auth/", include("accounts.urls")),
    path("api/units/", include("units.urls")),
    path("test/accounts", accounts_test_page),
    path("test/units", units_test_page),
    path("admin/", admin.site.urls),
]
