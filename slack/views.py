from django.http.response import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from slack.attachments import get_standing, get_statistics
from slack.utils import parse_int


@csrf_exempt
def statistics(request):
    return JsonResponse(data={
        'text': 'Matcom Online Grader (Statistics)',
        'response_type': 'in_channel',
        'attachments': get_statistics()
    })


@csrf_exempt
def standing(request):
    start = max(1, parse_int(request.POST.get('text'), default=1))
    return JsonResponse(data={
        'text': 'Matcom Online Grader (Standing)',
        'response_type': 'in_channel',
        'attachments': get_standing(start=start - 1)
    })
