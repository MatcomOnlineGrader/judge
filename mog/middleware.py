class AddNeverCacheHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        response["Cache-Control"] = "no-cache, no-store, must-revalidate,max-age=0"
        return response
