from django.contrib import admin
from django.urls import include, path

from accounts.views import test_page as accounts_test_page
from core import views
from units.device import readings as device_readings
from units.views import test_page as units_test_page
from web.views import index as app_index

admin.site.site_header = "Happy Plant admin"
admin.site.site_title = "Happy Plant admin"

urlpatterns = [
    path("", app_index),
    path("api/app/", include("web.urls")),
    path("health", views.health),
    path("api/auth/", include("accounts.urls")),
    path("api/units/", include("units.urls")),
    path("api/device/readings", device_readings),
    path("test/accounts", accounts_test_page),
    path("test/units", units_test_page),
    path("admin/", admin.site.urls),
]
