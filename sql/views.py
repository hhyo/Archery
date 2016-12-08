from django.shortcuts import render
from django.http import HttpResponse


# Create your views here.
def test1(request):
    #return HttpResponse("ffffffffvvvvvvvvvvv")
    context = {'currentMenu':123}
    return render(request, 'base.html', context)
