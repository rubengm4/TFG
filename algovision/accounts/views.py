from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django import forms
from django.views import View
from django.views.generic.edit import FormView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from fv_analysis.models import Project, UserProject   # make sure you import these
from django.utils import timezone


# --- Custom Forms ---


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name',
                  'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        if self.request:
            project_slug = self.request.session.get('source')
            if not project_slug:
                raise ValidationError(
                    "No project context found.", code='invalid_login')

            try:
                project = Project.objects.get(
                    title__iexact=project_slug.replace('-', ' '))
            except Project.DoesNotExist:
                raise ValidationError(
                    "Invalid project selected.", code='invalid_login')

            if not UserProject.objects.filter(user=user, project=project).exists():
                raise ValidationError(
                    "Este usuario no está registrado en este proyecto.",
                    code='invalid_login'
                )


# --- Views ---

# Project source selector (from homepage)
class SetSourceAndRedirectToLogin(View):
    def post(self, request):
        source = request.POST.get('source', 'default')
        request.session['login_source'] = source
        request.session['source'] = source

        # Redirect to the appropriate homepage
        if source == 'fv-analysis':
            return redirect('accounts:fv_home')
        # elif source == 'enlace2':
        #     return redirect('accounts:enlace2_home')
        # Add more as needed
        return redirect('home')


class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        # Save user to auth_user
        user = form.save()

        # Get current project from session
        project_slug = self.request.session.get('source')
        print("DEBUG: project_slug from session:", project_slug)
        try:
            project = Project.objects.get(
                title__iexact=project_slug)
        except Project.DoesNotExist:
            messages.error(self.request, "Project does not exist.")
            user.delete()
            return self.form_invalid(form)

        # Register the user in UserProject
        UserProject.objects.create(
            user=user,
            project=project,
            joined_at=timezone.now().date(),
            role='Member'
        )

        messages.success(self.request, "Registration successful.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Unsuccessful registration.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        if 'login_source' not in request.session:
            messages.error(
                request, "Debes seleccionar un proyecto antes de registrarte.")
            # replace with your actual homepage URL name
            return redirect('homepage')
        return super().dispatch(request, *args, **kwargs)


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomAuthenticationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request  # Pass the request to the form
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('login_source', 'default')
        return context

    def get_success_url(self):
        source = self.request.session.get('login_source', 'default')
        if source:
            return reverse('accounts:dashboard')
        return reverse('default_home')  # fallback


def fv_home(request):
    source = request.session.get('source', 'desconocido')
    return render(request, 'accounts/fv_home.html', {'source': source})


@login_required
def dashboard_view(request):
    project_slug = request.session.get('login_source', 'Sin proyecto')
    context = {
        'project_slug': project_slug,
        'user': request.user
    }
    return render(request, 'accounts/dashboard.html', context)


class CustomLogoutView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        request.session.pop('login_source', None)
        return super().dispatch(request, *args, **kwargs)
