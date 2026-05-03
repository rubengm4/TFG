from django import forms
from typing import Any, Optional

# Django contrib imports
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import LoginView, LogoutView

# Django core imports
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse, resolve  # type: ignore
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

# Django views imports
from django.views import View
from django.views.generic import TemplateView, UpdateView
from django.views.generic.edit import FormView

# Local app imports
from analysis.models import Project, UserProject, Execution, File, Algorithm


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
        # Tailwind classes applied directly
        tailwind_class = (
            'w-full px-3 py-2 rounded border border-gray-300 bg-white text-gray-900 '
            'focus:outline-none focus:ring-2 focus:ring-blue-500'
        )
        for field in self.fields.values():
            field.widget.attrs['class'] = tailwind_class

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
        # Sends request explicitly to the parent class for use in confirm_login_allowed
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
    """
    Recibe el menú o proyecto seleccionado desde el home
    y guarda el contexto en la sesión para futuras redirecciones.
    """

    def post(self, request: HttpRequest):
        source = request.POST.get('source', '').strip()
        if not source:
            return redirect('index')

        # Save in session for later use in login and registration
        request.session['login_source'] = source
        request.session['source'] = source

        try:
            project = Project.objects.get(title__iexact=source)
            request.session['project_id'] = project.id
        except Project.DoesNotExist:
            request.session['project_id'] = None

        # Redirect to login screen based on source
        if source == 'pv-analysis':
            return redirect('pv_analysis_home')
        elif source == 'people-analysis':
            return redirect('people_analysis_home')
        elif source == 'stats-analysis':
            return redirect('stats_analysis_home')

        # Go to index if source is unrecognized or default
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
            messages.error(self.request, "El proyecto no existe.")
            user.delete()
            return self.form_invalid(form)

        # Link user to project
        UserProject.objects.create(
            user=user,
            project=project,
            joined_at=timezone.now().date(),
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
        project_id = request.session.get('project_id')

        # If user is authenticated, go to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')

        # If no valid context, go back to index
        if not source and not project_id:
            return redirect('index')

        # If project doesn't exist, go back to index
        try:
            if project_id:
                Project.objects.get(id=project_id)
            elif source:
                Project.objects.get(title__iexact=source)
        except Project.DoesNotExist:
            return redirect('index')

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('dashboard')

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('login_source', '')
        return context


class LoginHomeView(TemplateView):
    template_name = 'accounts/login_home.html'

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('source', 'desconocido')
        return context


def resolve_project_from_session(request: HttpRequest) -> Optional[Project]:
    raw_id = request.session.get('project_id')
    if raw_id is not None:
        try:
            pid = int(raw_id)
        except (TypeError, ValueError):
            pid = None
        if pid is not None:
            project = Project.objects.filter(pk=pid).first()
            if project is not None:
                return project
    slug = request.session.get('login_source')
    if not slug or slug == 'Sin proyecto':
        return None
    return Project.objects.filter(title__iexact=slug).first()


def user_has_dashboard_project_access(user: Any, project: Project) -> bool:
    return UserProject.objects.filter(user=user, project=project).exists()


def sync_session_project(request: HttpRequest, project: Project) -> None:
    request.session['login_source'] = project.title
    request.session['source'] = project.title
    request.session['project_id'] = project.pk


class CustomLoginRedirectMixin(AccessMixin):
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        try:
            _ = resolve(request.path)
        except Exception as e:
            print(f"resolve error: {e}")

        login_source = request.session.get('login_source')

        if not request.user.is_authenticated:
            if not login_source or login_source == 'default':
                request.session.pop('login_source', None)
                return redirect('index')

            from analysis.models import Project
            try:
                Project.objects.get(title__iexact=login_source)
            except Project.DoesNotExist:
                request.session.pop('login_source', None)
                return redirect('index')
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)


class NeverCacheMixin:
    @method_decorator(never_cache)
    def dispatch(self, *args: Any, **kwargs: Any):
        return super().dispatch(*args, **kwargs)


class DashboardView(NeverCacheMixin, CustomLoginRedirectMixin, View):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any):
        project = resolve_project_from_session(request)
        if project is None:
            return redirect('index')

        if not user_has_dashboard_project_access(request.user, project):
            return redirect('index')

        sync_session_project(request, project)
        project_slug = project.title

        # Count files linked to the project through executions
        files_count = File.objects.filter(
            user=request.user).count()

        # Count executions for this user and project
        analysis_count = Execution.objects.filter(
            user=request.user).count()

        # Get last 5 executions for this user and project, ordered by execution date
        recent_results = Execution.objects.filter(
            user=request.user).order_by('-execution_date')[:5]

        # Get number of algorithms linked to the project
        algorithms_count = Algorithm.objects.filter(project=project).count()

        context: dict[str, Any] = {
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


class CustomUserChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        tailwind_class = (
            'w-full px-3 py-2 rounded border border-gray-300 bg-white text-gray-900 '
            'focus:outline-none focus:ring-2 focus:ring-blue-500'
        )
        for field in self.fields.values():
            field.widget.attrs['class'] = tailwind_class
            if field.label and field.label.lower() == 'username':
                field.widget.attrs['readonly'] = True
                field.help_text = "El nombre de usuario no se puede modificar."


class UserUpdateView(CustomLoginRedirectMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "accounts/manage_user.html"
    # Wherever you want to redirect after successful update
    success_url = reverse_lazy("dashboard")

    def get_object(self):
        # Only allows editing their own user
        return self.request.user


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        # Check that the new password is not the same as the current one
        if form.cleaned_data['new_password1'] == form.cleaned_data['old_password']:
            form.add_error(
                'new_password1', "La nueva contraseña no puede ser igual a la actual.")
            return self.form_invalid(form)

        messages.success(
            self.request, "✅ Tu contraseña se ha cambiado correctamente.")
        return super().form_valid(form)

# Form to write "DELETE" to confirm account deletion


class DeleteUserForm(forms.Form):
    confirm_text = forms.CharField(
        max_length=6,
        label='Escribe DELETE para continuar',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 bg-white text-gray-900',
            'placeholder': 'DELETE'
        })
    )

# Step 2: Writing confirmation form to ensure user types "DELETE" before final confirmation


class DeleteUserConfirmView(CustomLoginRedirectMixin, FormView):
    template_name = 'accounts/delete_user_confirm.html'
    form_class = DeleteUserForm

    def form_valid(self, form: form_class):
        confirm_text: str = form.cleaned_data['confirm_text']
        if confirm_text == "DELETE":
            return redirect('accounts:delete_user_final')
        form.add_error('confirm_text', 'Debes escribir DELETE exactamente.')
        return self.form_invalid(form)

# Step 3: Final confirmation and deletion


class DeleteUserView(CustomLoginRedirectMixin, View):
    def get(self, request: HttpRequest):
        # Show final confirmation page before deletion, explaining consequences and asking for final confirmation
        return render(request, 'accounts/delete_user_final.html')

    def post(self, request: HttpRequest):
        user = request.user
        # Here, you could delete associated files and executions if you want to ensure complete cleanup of user data
        user.delete()
        messages.success(request, "Usuario eliminado correctamente.")
        return redirect('accounts:login')
