from django.http import JsonResponse
import django_q

import archery


def info(request):
    archery_version = '.'.join(str(i) for i in archery.version)
    django_q_version = '.'.join(str(i) for i in django_q.VERSION)
    system_info = {
        'archery': {
            'version': archery_version
        },
        'django_q': {
            'version': django_q_version
        }
    }
    return JsonResponse(system_info)
