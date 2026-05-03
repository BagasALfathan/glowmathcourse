from academics.utils import update_expired_classes


class StatusUpdateMiddleware:
    """Run update_expired_classes() on every authenticated request (cached 5 min)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated if hasattr(request, 'user') else False:
            update_expired_classes()
        return self.get_response(request)
