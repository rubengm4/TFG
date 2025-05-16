from django.views import View
from django.shortcuts import redirect
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView

# Homepage


class HomepageView(TemplateView):
    template_name = 'homepage.html'

# Store the source securely


class SetSourceAndRedirectToLogin(View):
    def post(self, request):
        source = request.POST.get('source', 'default')
        request.session['login_source'] = source
        return redirect('custom_login')

# Custom login view


class CustomLoginView(LoginView):
    template_name = 'login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('login_source', 'default')
        return context
