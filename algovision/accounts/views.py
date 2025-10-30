from django import forms
from typing import Any

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

# Django views imports
from django.views import View
from django.views.generic import TemplateView, UpdateView
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
        # Aplicamos clases Tailwind directamente
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
    """
    Recibe el menú o proyecto seleccionado desde el home
    y guarda el contexto en la sesión para futuras redirecciones.
    """

    def post(self, request: HttpRequest):
        source = request.POST.get('source', '').strip()
        if not source:
            return redirect('index')

        # Guardar en sesión el login_source y project_id si existe
        request.session['login_source'] = source
        request.session['source'] = source

        try:
            project = Project.objects.get(title__iexact=source)
            request.session['project_id'] = project.id
        except Project.DoesNotExist:
            request.session['project_id'] = None

        # Redirigir a la pantalla de login del proyecto seleccionado
        if source == 'fv-analysis':
            return redirect('fv_analysis_home')
        elif source == 'people-analysis':
            return redirect('people_analysis_home')
        elif source == 'stats-analysis':
            return redirect('stats_analysis_home')

        # Si no se reconoce, volver al inicio
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

        # Si el usuario ya está autenticado, ir al dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')

        # Si no hay contexto válido, volver al index
        if not source and not project_id:
            return redirect('index')

        # Si el proyecto no existe, volver al index
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

            from fv_analysis.models import Project
            try:
                Project.objects.get(title__iexact=login_source)
            except Project.DoesNotExist:
                request.session.pop('login_source', None)
                return redirect('index')
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)


class DashboardView(CustomLoginRedirectMixin, View):
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
    success_url = reverse_lazy("dashboard")  # o donde quieras redirigir

    def get_object(self):
        # Solo permite editar su propio usuario
        return self.request.user


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        # Comprobar que la nueva contraseña no sea igual a la actual
        if form.cleaned_data['new_password1'] == form.cleaned_data['old_password']:
            form.add_error(
                'new_password1', "La nueva contraseña no puede ser igual a la actual.")
            return self.form_invalid(form)

        messages.success(
            self.request, "✅ Tu contraseña se ha cambiado correctamente.")
        return super().form_valid(form)

# Formulario para escribir "DELETE"


class DeleteUserForm(forms.Form):
    confirm_text = forms.CharField(
        max_length=6,
        label='Escribe DELETE para continuar',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 bg-white text-gray-900',
            'placeholder': 'DELETE'
        })
    )

# Step 2: Confirmación de escritura


class DeleteUserConfirmView(CustomLoginRedirectMixin, FormView):
    template_name = 'accounts/delete_user_confirm.html'
    form_class = DeleteUserForm

    def form_valid(self, form: form_class):
        confirm_text: str = form.cleaned_data['confirm_text']
        if confirm_text == "DELETE":
            return redirect('accounts:delete_user_final')
        form.add_error('confirm_text', 'Debes escribir DELETE exactamente.')
        return self.form_invalid(form)

# Step 3: Confirmación final y borrado


class DeleteUserView(CustomLoginRedirectMixin, View):
    def get(self, request: HttpRequest):
        # Mostrar confirmación final
        return render(request, 'accounts/delete_user_final.html')

    def post(self, request: HttpRequest):
        user = request.user
        # Aquí podrías eliminar archivos y ejecuciones asociados
        user.delete()
        messages.success(request, "Usuario eliminado correctamente.")
        return redirect('accounts:login')
