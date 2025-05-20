from django.views import View
from django.shortcuts import redirect
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView

# Homepage


class HomepageView(TemplateView):
    template_name = 'index.html'
