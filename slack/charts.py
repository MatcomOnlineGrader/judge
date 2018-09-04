import urllib


GOOGLE_CHART_API = "https://chart.googleapis.com/chart"


def google_pie(labels, data, **kwargs):
    parameters = {
        'cht': 'p3',
        'chd': 't:%s' % ','.join(map(str, data)),
        'chl': '|'.join(labels),
        'chs': kwargs.get('size', '512x128'),
    }
    if 'title' in kwargs:
        parameters['chtt'] = kwargs['title']
    if 'colors' in kwargs:
        parameters['chco'] = ','.join(kwargs['colors'])
    return '%s?%s' % (GOOGLE_CHART_API, urllib.parse.urlencode(parameters))
