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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")

        return cleaned_data

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
            return redirect('fv_analysis_home')
        # elif source == 'enlace2':
        #     return redirect('accounts:enlace2_home')
        # Add more as needed
        return redirect('home')


class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        source = request.session.get('login_source')

        if not source or source == 'default':
            return redirect('index')

        try:
            Project.objects.get(title__iexact=source)
        except Project.DoesNotExist:
            messages.error(request, "El proyecto seleccionado no existe.")
            return redirect('index')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
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
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Registro no válido.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['source'] = self.request.session.get('login_source', '')
        return context


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        source = request.session.get('login_source')

        if not source or source == 'default':
            return redirect('index')

        try:
            project = Project.objects.get(title=source)
        except Project.DoesNotExist:
            return redirect('index')

        if request.user.is_authenticated:
            # Already logged in user not in the project → log out
            if not UserProject.objects.filter(user=request.user, project=project).exists():
                logout(request)
                return redirect('index')

        return super().dispatch(request, *args, **kwargs)

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
            return reverse('dashboard')
        return reverse('index')  # fallback


def fv_analysis_home(request):
    source = request.session.get('source', 'desconocido')
    return render(request, 'accounts/fv_home.html', {'source': source})


@login_required
def dashboard_view(request):
    project_slug = request.session.get('login_source')

    # If no project selected or it's "Sin proyecto", force selection
    if not project_slug or project_slug == 'Sin proyecto':
        return redirect('index')

    try:
        project = Project.objects.get(title=project_slug)
    except Project.DoesNotExist:
        return redirect('index')

    # Check if user is actually in the project
    if not UserProject.objects.filter(user=request.user, project=project).exists():
        return redirect('index')

    context = {
        'project_slug': project_slug,
        'user': request.user,
    }
    return render(request, 'accounts/dashboard.html', context)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('index')

    def dispatch(self, request, *args, **kwargs):
        request.session.pop('login_source', None)
        return super().dispatch(request, *args, **kwargs)
