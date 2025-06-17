from django import forms
from typing import Any

# Django contrib imports
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView

# Django core imports
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone

# Django views imports
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

# Local app imports
from fv_analysis.models import Project, UserProject, Execution, File, Algorithm


# --- Custom Forms ---


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name',
                  'last_name', 'password1', 'password2')

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        assert cleaned_data is not None, "cleaned_data no debería ser None"
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")

        return cleaned_data

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    error_messages = {
        'invalid_login': (
            "Usuario o contraseña incorrectos. Ten en cuenta que ambos campos distinguen mayúsculas y minúsculas."
        )
    }

    def __init__(self, *args: Any, **kwargs: Any):
        self.request = kwargs.pop('request', None)
        # Pasa request explícitamente a super
        super().__init__(request=self.request, *args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        if not self.request:
            return

        project_slug = self.request.session.get('login_source')
        if not project_slug:
            raise ValidationError("No project context found.",
                                  code='invalid_login')

        try:
            project = Project.objects.get(
                title__iexact=project_slug)
        except Project.DoesNotExist:
            raise ValidationError("Invalid project selected.",
                                  code='invalid_login')

        if not UserProject.objects.filter(user=user, project=project).exists():
            raise ValidationError(
                "Usuario o contraseña incorrectos. Ten en cuenta que ambos campos distinguen mayúsculas y minúsculas.", code='invalid_login')


# --- Views ---

# Project source selector (from homepage)
class SetSourceAndRedirectToLogin(View):
    def post(self, request: HttpRequest):
        source = request.POST.get('source', 'default')
        request.session['login_source'] = source
        request.session['source'] = source

        # Redirect to the appropriate homepage
        if source == 'fv-analysis':
            return redirect('fv_analysis_home')
        elif source == 'example-project':
            return redirect('example_project_home')
        # Add more as needed
        return redirect('index')


class RegisterView(FormView):  # type: ignore
    template_name = 'accounts/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:login')

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        source = request.session.get('login_source')

        if request.user.is_authenticated:
            return redirect('dashboard')

        if not source or source == 'default':
            return redirect('index')

        try:
            Project.objects.get(title__iexact=source)
        except Project.DoesNotExist:
            messages.error(request, "El proyecto seleccionado no existe.")
            return redirect('index')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: CustomUserCreationForm):
        user = form.save()

        # Get current project from session
        project_slug = self.request.session.get('login_source')
        try:
            project = Project.objects.get(title__iexact=project_slug)
        except Project.DoesNotExist:
            messages.error(self.request, "Project does not exist.")
            user.delete()
            return self.form_invalid(form)

        # Link user to project
        UserProject.objects.create(
            user=user,
            project=project,
            joined_at=timezone.now().date(),
            role='Member'
        )

        messages.success(self.request, "Registro completado con éxito.")
        return super().form_valid(form)  # type: ignore

    def form_invalid(self, form: CustomUserCreationForm):
        messages.error(self.request, "Registro no válido.")
        return super().form_invalid(form)  # type: ignore

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('login_source', '')
        return context


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = CustomAuthenticationForm

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        source = request.session.get('login_source')

        if request.user.is_authenticated:
            return redirect('dashboard')

        if not source or source == 'default':
            return redirect('index')

        try:
            project = Project.objects.get(title=source)
        except Project.DoesNotExist:
            return redirect('index')

        if request.user.is_authenticated:
            if not UserProject.objects.filter(user=request.user, project=project).exists():
                logout(request)
                return redirect('index')

        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = form_class(**self.get_form_kwargs())
        return form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('login_source', 'default')
        return context

    def get_success_url(self):
        source = self.request.session.get('login_source', 'default')
        if source:
            return reverse('dashboard')
        return reverse('index')

    def form_invalid(self, form):
        return super().form_invalid(form)


class LoginHomeView(TemplateView):
    template_name = 'accounts/login_home.html'

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('source', 'desconocido')
        return context


class DashboardView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any):
        project_slug = request.session.get('login_source')

        # Validar proyecto
        if not project_slug or project_slug == 'Sin proyecto':
            return redirect('index')

        try:
            project = Project.objects.get(title=project_slug)
        except Project.DoesNotExist:
            return redirect('index')

        # Validar pertenencia usuario al proyecto
        if not UserProject.objects.filter(user=request.user, project=project).exists():
            return redirect('index')

        # Contar archivos subidos por usuario en el proyecto
        files_count = File.objects.filter(
            user=request.user).count()

        # Contar análisis realizados por usuario en el proyecto
        analysis_count = Execution.objects.filter(
            user=request.user).count()

        # Obtener últimos 5 resultados
        recent_results = Execution.objects.filter(
            user=request.user).order_by('-execution_date')[:5]

        # Contar algoritmos totales
        algorithms_count = Algorithm.objects.filter(project=project).count()

        context = {
            'project_slug': project_slug,
            'user': request.user,
            'files_count': files_count,
            'analysis_count': analysis_count,
            'recent_results': recent_results,
            'algorithms_count': algorithms_count,
        }
        return render(request, 'accounts/dashboard.html', context)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('index')

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        request.session.pop('login_source', None)
        return super().dispatch(request, *args, **kwargs)
