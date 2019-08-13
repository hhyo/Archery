from django.http import JsonResponse
import archery


def info(request):
    archery_version = '.'.join(str(i) for i in archery.version)
    system_info = {
        'archery': {
            'version': archery_version
        }
    }
    return JsonResponse(system_info)
