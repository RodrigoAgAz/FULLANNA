from django.middleware.csrf import CsrfViewMiddleware

class CustomCsrfMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if request.path == '/chatbot/chat/':
            return None  # Skip CSRF check for this path
        return super().process_view(request, callback, callback_args, callback_kwargs)