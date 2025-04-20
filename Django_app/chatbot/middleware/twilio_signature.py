import hmac, hashlib, base64
from django.conf import settings
from django.http import HttpResponseForbidden

class TwilioSignatureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.token = settings.TWILIO_AUTH_TOKEN

    def __call__(self, request):
        if request.path.startswith("/chatbot/"):
            tw_sig = request.headers.get("X-Twilio-Signature")
            if not self._valid(request, tw_sig):
                return HttpResponseForbidden("Invalid Twilio signature")
        return self.get_response(request)

    def _valid(self, request, tw_sig):
        if not (tw_sig and self.token):
            return False
        url = request.build_absolute_uri()
        body = request.body.decode() or ''
        data = url + body
        digest = hmac.new(self.token.encode(),
                         data.encode(), hashlib.sha1).digest()
        computed = base64.b64encode(digest).decode()
        return hmac.compare_digest(computed, tw_sig)