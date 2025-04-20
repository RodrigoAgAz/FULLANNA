from django.middleware.csrf import CsrfViewMiddleware
from django.urls import reverse

class CustomCsrfMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if request.method == 'POST' and request.path == reverse('chat'):
            return None  # Skip CSRF check for this path
        return super().process_view(request, callback, callback_args, callback_kwargs)