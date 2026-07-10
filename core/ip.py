"""
Client IP resolution behind the Railway edge proxy.

Railway terminates connections at its edge, so REMOTE_ADDR is the proxy's
address — shared by every visitor. The proxy appends the real client IP as
the LAST entry of X-Forwarded-For (earlier entries are client-supplied and
spoofable), so that entry is the only trustworthy one.

Used by django-ratelimit (signup throttle), django-axes (login lockout via
AXES_CLIENT_IP_CALLABLE), and audit logging.
"""


def client_ip(request):
    """Return the real client IP: last X-Forwarded-For entry, else REMOTE_ADDR."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '')


def ratelimit_client_ip(group, request):
    """django-ratelimit key callable (signature: group, request)."""
    return client_ip(request)
