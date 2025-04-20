# anna_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

# Simple health check function
def health_check(request):
    return HttpResponse("ok")

# Test endpoint for sentry
def raise_test_error(request):
    """Deliberately raise a ZeroDivisionError to test Sentry integration"""
    1 / 0  # This will trigger a ZeroDivisionError
    return HttpResponse("This won't be reached")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chatbot/', include('chatbot.urls')),  # Make sure this is here
    path('', include('django_prometheus.urls')),
    path('healthz/', health_check),
    path('raise-test/', raise_test_error),
]