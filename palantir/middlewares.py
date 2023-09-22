import time

import palantir.utils as palantir_utils


class AccessLogMiddleware:
    """This middleware tracks every request sent to the website"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        message = {
            "request": palantir_utils.build_request_message(request),
            "response": {},
        }
        try:
            s = time.time()
            response = self.get_response(request)
            e = time.time()
            message["response"].update(
                **{
                    "time": e - s,
                    "code": response.status_code,
                    "contentType": response.get("Content-Type"),
                }
            )
            palantir_utils.log_access_eventually(message)
            return response
        except Exception as e:
            message["response"].update(
                **{
                    "exception": type(e).__name__,
                }
            )
            palantir_utils.log_access_eventually(message)
            raise e
