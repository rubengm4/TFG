from django.views.generic import TemplateView

# Homepage


class HomepageView(TemplateView):
    template_name = 'index.html'
