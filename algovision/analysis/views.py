from django.views.decorators.cache import never_cache
import os
import json
import re
import shutil
import posixpath
from urllib.parse import urlparse

from accounts.views import (
    CustomLoginRedirectMixin,
    resolve_project_from_session,
    user_has_dashboard_project_access,
)

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
    HttpRequest,
    Http404,
    FileResponse,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView, CreateView, ListView, DeleteView, UpdateView

from typing import Any, List, Dict

from pathlib import Path

from .algorithm_paths import algorithm_pkg_disk_root, remove_legacy_extract_next_to_zip
from .aux_file_func import is_size_valid, is_type_valid, extension_getter, name_change
from .models import File, Algorithm, Project, Execution, Output, UserProject, sanitize_uploaded_filename
from .forms import AlgorithmForm, ProjectForm, UserProjectForm
from .tasks import ejecutar_algoritmo_task, install_requirements_task, REQUIREMENTS_PATH


class NoCacheMixin:
    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


_MEDIA_UPLOADS = re.compile(r"^uploads/(\d+)/(.+)$")
_MEDIA_OUTPUTS = re.compile(r"^outputs/(\d+)/(.+)$")
_MEDIA_ALGO_ZIP = re.compile(r"^algorithms/pkg/(\d+)/([^/]+\.zip)$")


def _media_rel_path_from_forwarded_uri(forwarded_uri: str) -> str | None:
    """Return path relative to MEDIA_ROOT, or None if invalid."""
    if not forwarded_uri or not forwarded_uri.strip():
        return None
    path = urlparse(forwarded_uri.strip()).path
    if not path:
        return None
    if path.startswith("/media/"):
        rel = path[7:]
    elif path.startswith("/"):
        rel = path[1:]
    else:
        rel = path
    if not rel or rel.endswith("/"):
        return None
    parts = rel.split("/")
    if ".." in parts or "" in parts:
        return None
    norm = posixpath.normpath(rel)
    if norm.startswith("..") or norm.startswith("/"):
        return None
    return rel


class MediaForwardAuthView(View):
    """Caddy forward_auth target: allow / deny /media/* based on X-Forwarded-Uri."""

    http_method_names = ["get", "head", "options"]

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._authorize(request)

    def head(self, request: HttpRequest) -> HttpResponse:
        return self._authorize(request)

    def options(self, request: HttpRequest) -> HttpResponse:
        return HttpResponse(status=200)

    def _authorize(self, request: HttpRequest) -> HttpResponse:
        rel = _media_rel_path_from_forwarded_uri(
            request.META.get("HTTP_X_FORWARDED_URI", "")
        )
        if rel is None:
            return HttpResponseForbidden()

        if rel == "envs" or rel.startswith("envs/"):
            return HttpResponseForbidden()

        user = request.user

        m = _MEDIA_UPLOADS.match(rel)
        if m:
            uid = int(m.group(1))
            if not user.is_authenticated:
                return HttpResponseForbidden()
            if user.is_staff or user.id == uid:
                return HttpResponse(status=200)
            return HttpResponseForbidden()

        m = _MEDIA_OUTPUTS.match(rel)
        if m:
            uid = int(m.group(1))
            if not user.is_authenticated:
                return HttpResponseForbidden()
            if user.is_staff or user.id == uid:
                return HttpResponse(status=200)
            return HttpResponseForbidden()

        m = _MEDIA_ALGO_ZIP.match(rel)
        if m:
            if not user.is_authenticated:
                return HttpResponseForbidden()
            if user.is_staff:
                return HttpResponse(status=200)
            return HttpResponseForbidden()

        return HttpResponseForbidden()


class HomepageView(NoCacheMixin, TemplateView):
    template_name = 'index.html'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        # Only clean if there is NO user logged in, to avoid losing session data for authenticated users when they refresh the homepage
        if not request.user.is_authenticated:
            for key in ['login_source', 'project_id', 'source']:
                request.session.pop(key, None)
        else:
            project = resolve_project_from_session(request)
            if project is not None and user_has_dashboard_project_access(
                request.user, project
            ):
                return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['type', 'upload_date']


@method_decorator(login_required, name='dispatch')
class FileManagerView(CustomLoginRedirectMixin, View):
    template_name = 'file_manager.html'

    def get(self, request: HttpRequest):
        files = File.objects.filter(user=request.user)
        return render(request, self.template_name, {'files': files})

    def post(self, request: HttpRequest):
        if 'delete_file' in request.POST:
            file_id = request.POST.get('delete_file')
            file_obj = get_object_or_404(File, id=file_id, user=request.user)
            file_name = os.path.basename(file_obj.file.name)

            file_path = file_obj.file.path
            if os.path.exists(file_path):
                os.remove(file_path)

            file_obj.delete()
            messages.success(
                request, f"Archivo {file_name} eliminado correctamente.")
            return redirect('file_manager')

        uploaded_files = request.FILES.getlist('files')

        # Maximum file size allowed (in MB)
        MAX_FILE_SIZE_MB = 10
        MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

        # If there are uploaded files
        if uploaded_files:
            # Get names of every existing user file in the database
            existing_names = File.objects.filter(
                user=request.user).values_list('file', flat=True)
            existing_file_names = [os.path.basename(n) for n in existing_names]

            # For every uploaded file
            for uploaded_file in uploaded_files:
                # Size validator
                if is_size_valid(uploaded_file, MAX_FILE_SIZE_BYTES, request) == False:
                    continue

                # Type validator
                if is_type_valid(uploaded_file, request) == False:
                    continue

                # Name setter
                uploaded_file.name, was_renamed = name_change(
                    uploaded_file, existing_file_names)

                # Get extension
                type = extension_getter(uploaded_file)

                # Create file in database
                File.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    type=type,
                    upload_date=timezone.now()
                )

                # If file was renamed
                if was_renamed:
                    messages.info(
                        request, f"Archivo {uploaded_file.name} renombrado por duplicado.")
                else:
                    messages.success(
                        request, f"Archivo {uploaded_file.name} subido correctamente.")
        else:
            messages.error(request, "No se seleccionaron archivos.")

        return redirect('file_manager')


@method_decorator(login_required, name='dispatch')
class AnalysisView(View):
    template_name = 'analysis.html'

    def get(self, request: HttpRequest):
        project_id = request.session.get('login_source')
        project = Project.objects.get(title=project_id)

        files = File.objects.filter(user=request.user)
        algorithms = Algorithm.objects.filter(project_id=project.pk)

        # Read file_id saved in session for pre-selection
        selected_file_id = request.session.pop('selected_file_id', None)
        selected_algorithm_id = request.session.pop(
            'selected_algorithm_id', None)
        return render(request, self.template_name, {
            'files': files,
            'algorithms': algorithms,
            'selected_file_id': selected_file_id,
            'selected_algorithm_id': selected_algorithm_id,
        })

    def post(self, request: HttpRequest):
        file_id = request.POST.get('file_id')
        algorithm_id = request.POST.get('algorithm')
        second_file_id = request.POST.get('second_file_id')

        if file_id and not algorithm_id:
            # Case: coming from /files with only file_id for pre-selection
            request.session['selected_file_id'] = file_id
            return redirect('analysis')

        # Case: coming from analysis form to execute (file and algo)
        if not file_id or not algorithm_id:
            messages.error(request, "Debes seleccionar archivo y algoritmo.")
            return redirect('analysis')

        file = get_object_or_404(File, id=file_id, user=request.user)
        try:
            algorithm = Algorithm.objects.get(id=algorithm_id)
        except Algorithm.DoesNotExist:
            messages.error(request, "Archivo o algoritmo no válido.")
            return redirect('analysis')

        input_file: str = file.file.path
        media_root = settings.MEDIA_ROOT

        # Resolve user path
        rel_path = os.path.relpath(input_file, media_root)
        parts = rel_path.split(os.sep)
        user_id = parts[1]

        # Prepare output directory and zip
        output_dir = os.path.join(media_root, 'outputs', user_id)
        os.makedirs(output_dir, exist_ok=True)

        # Save selection so it persists if you return to analysis
        request.session['selected_file_id'] = file_id
        request.session['selected_algorithm_id'] = algorithm_id

        supported_types = algorithm.supported_types.all()
        supported_names = ', '.join([str(ftype) for ftype in supported_types])

        # Check compatibility of the file with the algorithm: if the file type is not in the supported types of the algorithm, show an error message and return
        if file.type not in supported_types:
            messages.error(
                request,
                f"El archivo seleccionado no es compatible con el algoritmo '{algorithm.name}'. El algoritmo solo admite archivos de tipo: {supported_names}"
            )
            return redirect('analysis')

        # Check of second file is required and if it's compatible with the algorithm: if the algorithm requires a second file but it's not provided, or if the provided second file is not compatible with the algorithm, show an error message and return
        second_file = None
        if algorithm.requires_two_files:
            if not second_file_id:
                messages.error(
                    request, "Este algoritmo requiere un segundo archivo.")
                return redirect('analysis')
            try:
                second_file = File.objects.get(
                    id=second_file_id, user=request.user)
            except File.DoesNotExist:
                messages.error(
                    request, "El segundo archivo seleccionado no existe.")
                return redirect('analysis')

            if second_file.type not in supported_types:
                messages.error(
                    request,
                    f"El segundo archivo seleccionado no es compatible con el algoritmo '{algorithm.name}'. "
                    f"Este algoritmo solo admite archivos de tipo: {supported_names}"
                )
                return redirect('analysis')

        # Create execution (but don't run it here, just create the record in the database with status PENDING, the Celery task will update it when it starts and finishes)
        now = timezone.now()
        exec = Execution.objects.create(
            execution_date=now,
            status="PENDING",
            algorithm_id=algorithm_id,
            file_id=file_id,
            secondary_file=second_file if second_file else None,
            snapshot_file_name=file.filename(),
            snapshot_alg_name=algorithm.name,
            user=request.user
        )

        results_url: str = reverse('results')
        if algorithm.requires_two_files:
            ejecutar_algoritmo_task.delay(
                file_id, algorithm_id, exec.id, int(second_file_id))
        else:
            ejecutar_algoritmo_task.delay(
                file_id, algorithm_id, exec.id)

        messages.success(
            request,
            format_html(
                "Se ha iniciado el análisis con <strong>{}</strong> sobre <strong>{}</strong>{}. "
                "Puedes consultar su estado en la pestaña de "
                "<a href='{}' style='font-weight:700; text-decoration:none; color:inherit;'>Mis Resultados</a>",
                algorithm.name,
                file.filename(),
                " y un segundo archivo" if algorithm.requires_two_files else "",
                results_url,
            ),
        )

        return redirect('analysis')


class RenameFileView(CustomLoginRedirectMixin, View):
    def post(self, request: HttpRequest, file_id: int):
        file_obj = get_object_or_404(File, id=file_id, user=request.user)
        data = json.loads(request.body)

        raw_input = data.get('new_name', '').strip()
        raw_input = sanitize_uploaded_filename(raw_input)

        original_filename = os.path.basename(file_obj.file.name)
        current_base_name, ext = os.path.splitext(original_filename)

        # We extract only the base of the new name, ignoring any extension the user may have added, to ensure that the file keeps its original extension and avoid confusion or errors that could arise from changing file extensions during renaming.
        base_name, _ = os.path.splitext(raw_input)

        # We check base name is not empty and doesn't start with a dot to prevent issues with hidden files or files without a proper name, which could lead to confusion or problems when managing files in the system.
        if not base_name or base_name.startswith('.'):
            # We keep actual name
            return JsonResponse({'new_name': current_base_name})

        new_filename = f"{base_name}{ext}"

        # If new name is the same as current, do nothing to avoid unnecessary file operations and potential issues with timestamps or file metadata that could arise from renaming a file to the same name.
        if new_filename == original_filename:
            return JsonResponse({'new_name': base_name})

        user_folder = f"uploads/{request.user.pk}"

        old_relative_path: str = file_obj.file.name
        old_path = os.path.join(settings.MEDIA_ROOT, old_relative_path)

        new_relative_path = f"{user_folder}/{new_filename}"
        new_path = os.path.join(settings.MEDIA_ROOT, new_relative_path)

        if os.path.exists(new_path):
            return JsonResponse({'error': 'Ya existe un archivo con ese nombre.'}, status=400)

        try:
            os.rename(old_path, new_path)
            file_obj.file.name = new_relative_path
            file_obj.save()
            return JsonResponse({'new_name': base_name})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class ResultsView(CustomLoginRedirectMixin, View):
    template_name = "results.html"

    def get(self, request: HttpRequest):
        executions = (
            Execution.objects
            .select_related('file', 'algorithm')
            .filter(user=request.user)
            .order_by('-execution_date')
        )

        results: List[Dict[str, Any]] = []
        for execution in executions:
            output = Output.objects.filter(execution=execution).first()
            results.append({
                'id': execution.pk,
                'original_filename': execution.snapshot_file_name if execution.snapshot_file_name else "(sin archivo)",
                'algorithm_name': execution.snapshot_alg_name if execution.snapshot_alg_name else "(sin algoritmo)",
                'status': execution.status,
                'execution_date': execution.execution_date,
                'output_id': output.pk if output else None,
            })

        return render(request, self.template_name, {'results': results})

    def post(self, request: HttpRequest):
        execution_id = request.POST.get("delete_execution")
        if execution_id:
            try:
                execution = Execution.objects.get(
                    pk=execution_id, user=request.user)
                output = Output.objects.filter(execution=execution).first()
                # We delete file from filesystem if it exists and then delete the Output record, to ensure that we don't leave orphaned files taking up space on the server after an execution is deleted, while also keeping the database clean by removing the corresponding Output record.
                if output and output.file and os.path.isfile(output.file.path):
                    os.remove(output.file.path)
                    output.delete()
                execution.delete()
            except Execution.DoesNotExist:
                pass  # Silence if not found
        return redirect("results")


class DownloadOutputView(CustomLoginRedirectMixin, View):
    def get(self, request: HttpRequest, output_id: int):
        try:
            output = Output.objects.get(
                pk=output_id, execution__user=request.user)
            if not output.file:
                raise Http404("Output sin archivo asociado.")
            return FileResponse(output.file.open('rb'), as_attachment=True, filename=output.file.name)
        except Output.DoesNotExist:
            raise Http404("Output no encontrado.")


LOG_PATH = os.path.join(settings.MEDIA_ROOT, 'envs', 'debug_install.log')


class ManageRequirementsView(CustomLoginRedirectMixin, UserPassesTestMixin, View):
    template_name = "manage_requirements.html"

    def get(self, request):
        packages = []
        if os.path.exists(REQUIREMENTS_PATH):
            with open(REQUIREMENTS_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if '==' in line:
                        name, version = line.split('==', 1)
                    else:
                        name, version = line, ''
                    packages.append({'name': name, 'version': version})

        logs = ""
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'r') as f:
                logs = f.read()

        # It only supports logs if called with ?logs_only=1, to allow fetching logs separately via AJAX without needing to load the whole page, which can be useful for real-time log updates during installation or debugging without refreshing the entire requirements management interface.
        if request.GET.get('logs_only') == '1':
            from django.http import HttpResponse
            return HttpResponse(logs)

        return render(request, self.template_name, {
            'packages': packages,
            'logs': logs
        })

    def post(self, request):
        # Recollect submitted rows
        package_names = request.POST.getlist('package_name')
        package_versions = request.POST.getlist('package_version')

        lines = []
        for name, version in zip(package_names, package_versions):
            name = name.strip()
            version = version.strip() or ''  # No version? Install latest
            if name:
                if version:
                    lines.append(f"{name}=={version}")
                else:
                    lines.append(name)

        os.makedirs(os.path.dirname(REQUIREMENTS_PATH), exist_ok=True)
        with open(REQUIREMENTS_PATH, 'w') as f:
            f.write("\n".join(lines) + "\n")

        # Run installation via Celery to avoid blocking the request and allow it to run in the background, which is especially important since installing packages can take a long time and we don't want the user to have to wait for the installation to complete before they can continue using the application or see any feedback on the installation process.
        install_requirements_task.delay()

        messages.success(
            request, "Requirements guardados y la instalación se ha iniciado en segundo plano.")
        return redirect('manage_requirements')

    def test_func(self):
        return self.request.user.is_superuser


# We save a global timestamp in memory for simplicity. It changes every time requirements_global.txt is updated, allowing us to track the last modification time of the requirements file without needing to read the file's metadata from disk every time we want to check for updates, which can improve performance when checking for changes frequently, such as during development or when monitoring the file for changes in real-time.
REQUIREMENTS_LAST_MOD = 0


class RequirementsJSONView(CustomLoginRedirectMixin, UserPassesTestMixin, View):
    def get(self, request):
        global REQUIREMENTS_LAST_MOD
        packages = []

        if REQUIREMENTS_PATH.exists():
            # Modification timestamp of the file
            ts = int(REQUIREMENTS_PATH.stat().st_mtime)

            # We only update the hash if the file has changed
            if ts != REQUIREMENTS_LAST_MOD:
                REQUIREMENTS_LAST_MOD = ts

            for line in REQUIREMENTS_PATH.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                if '==' in line:
                    name, version = line.split('==', 1)
                else:
                    name, version = line, ''
                packages.append({'name': name, 'version': version})

        return JsonResponse({'packages': packages, 'timestamp': REQUIREMENTS_LAST_MOD})

    def test_func(self):
        return self.request.user.is_superuser


class DownloadRequirementsView(CustomLoginRedirectMixin, UserPassesTestMixin, View):
    def get(self, request: HttpRequest):
        if not os.path.exists(REQUIREMENTS_PATH):
            raise Http404("El archivo requirements_global.txt no existe.")
        return FileResponse(open(REQUIREMENTS_PATH, 'rb'), as_attachment=True, filename='requirements_global.txt')

    def test_func(self):
        return self.request.user.is_superuser


class UploadRequirementsView(CustomLoginRedirectMixin, UserPassesTestMixin, View):
    def post(self, request: HttpRequest):
        file = request.FILES.get('requirements_file')
        if not file:
            return JsonResponse({'status': 'error', 'message': 'No se seleccionó ningún archivo.'}, status=400)

        if not file.name.endswith('.txt'):
            return JsonResponse({'status': 'error', 'message': 'Solo se permiten archivos .txt.'}, status=400)

        with open(REQUIREMENTS_PATH, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        install_requirements_task.delay()

        return JsonResponse({
            'status': 'ok',
            'message': f'Archivo {file.name} subido correctamente.',
            'installation_started': True
        })

    def test_func(self):
        return self.request.user.is_superuser


class CreateAlgorithmView(CustomLoginRedirectMixin, UserPassesTestMixin, CreateView):
    model = Algorithm
    form_class = AlgorithmForm
    template_name = "algorithms/create_algorithm.html"
    success_url = reverse_lazy("manage_algorithms")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        # algorithm_archive_upload_to needs instance.pk; save other fields first (see bootstrap_initial_data).
        algorithm = form.save(commit=False)
        uploaded_zip = form.cleaned_data.get("archive")
        algorithm.archive = None
        algorithm.save()
        form.save_m2m()
        if uploaded_zip:
            algorithm.archive.save(uploaded_zip.name, uploaded_zip, save=True)
        self.object = algorithm
        messages.success(self.request, "Algoritmo creado correctamente.")
        return redirect(self.get_success_url())


class ManageAlgorithmsView(CustomLoginRedirectMixin, UserPassesTestMixin, ListView):
    model = Algorithm
    template_name = "algorithms/manage_algorithms.html"
    context_object_name = "algorithms"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        project_slug = self.request.session.get('login_source')

        if not project_slug or project_slug == 'Sin proyecto':
            return Algorithm.objects.none()

        try:
            project = Project.objects.get(title=project_slug)
        except Project.DoesNotExist:
            return Algorithm.objects.none()

        return Algorithm.objects.filter(project=project)

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        project_slug = self.request.session.get('login_source')

        try:
            context['current_project'] = Project.objects.get(
                title=project_slug)
        except Project.DoesNotExist:
            context['current_project'] = None

        return context


class UpdateAlgorithmView(CustomLoginRedirectMixin, UserPassesTestMixin, UpdateView):
    model = Algorithm
    form_class = AlgorithmForm
    template_name = 'algorithms/edit_algorithm.html'
    success_url = reverse_lazy('manage_algorithms')

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        obj: Any | None = self.get_object()
        new_archive = form.cleaned_data.get('archive')
        media_root = Path(settings.MEDIA_ROOT)

        if new_archive and new_archive != obj.archive:
            pkg_root = algorithm_pkg_disk_root(media_root, obj.pk)
            extract_dir = pkg_root / "extract"
            if extract_dir.is_dir():
                shutil.rmtree(extract_dir, ignore_errors=True)

            if obj.archive and obj.archive.name:
                try:
                    old_fp = Path(obj.archive.path)
                except (NotImplementedError, ValueError):
                    old_fp = None
                if old_fp is not None and old_fp.is_file():
                    remove_legacy_extract_next_to_zip(media_root, old_fp)
                    old_fp.unlink()

        messages.success(self.request, "Algoritmo editado correctamente.")
        return super().form_valid(form)


class DeleteAlgorithmView(CustomLoginRedirectMixin, UserPassesTestMixin, DeleteView):
    model = Algorithm
    success_url = reverse_lazy("manage_algorithms")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any) -> Any:
        obj: Any = self.get_object()
        media_root = Path(settings.MEDIA_ROOT)

        pkg_root = algorithm_pkg_disk_root(media_root, obj.pk)
        if pkg_root.is_dir():
            shutil.rmtree(pkg_root, ignore_errors=True)
        elif obj.archive and obj.archive.name:
            try:
                fp = Path(obj.archive.path)
            except (NotImplementedError, ValueError):
                fp = None
            if fp is not None and fp.is_file():
                remove_legacy_extract_next_to_zip(media_root, fp)
                fp.unlink()

        return super().form_valid(form)


class CreateProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/create_project.html"
    success_url = reverse_lazy("manage_projects")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        messages.success(self.request, "Proyecto creado correctamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        # Build HTML safely: each field name and error string is escaped.
        rows = []
        for field, errors in form.errors.items():
            error_list = ", ".join(errors)
            rows.append((field, error_list))

        full_message = format_html_join(
            "<br>",
            "<strong>{}:</strong> {}",
            rows,
        )
        messages.error(self.request, full_message)

        return super().form_invalid(form)


class ManageProjectsView(CustomLoginRedirectMixin, UserPassesTestMixin, ListView):
    model = Project
    template_name = "projects/manage_projects.html"
    context_object_name = "projects"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Project.objects.all().order_by("title")


class UpdateProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/edit_project.html"
    success_url = reverse_lazy("manage_projects")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        old_title = Project.objects.values_list('title', flat=True).get(
            pk=self.object.pk
        )
        messages.success(self.request, "Proyecto actualizado correctamente.")
        response = super().form_valid(form)
        sess = self.request.session
        raw_pid = sess.get('project_id')
        try:
            session_pid = int(raw_pid) if raw_pid is not None else None
        except (TypeError, ValueError):
            session_pid = None
        login_src = (sess.get('login_source') or '')
        if session_pid == self.object.pk or old_title.lower() == login_src.lower():
            sess['login_source'] = self.object.title
            sess['source'] = self.object.title
            sess['project_id'] = self.object.pk
        return response

    def form_invalid(self, form):
        error_messages = []
        for _, errors in form.errors.items():
            # Join multiple errors for the same field
            error_list = ", ".join(errors)
            error_messages.append(f"{error_list}")

        # Join all fields' errors
        full_message = format_html("<br>".join(error_messages))

        # Display as a Django message (with HTML allowed)
        messages.error(self.request, full_message)

        return super().form_invalid(form)


class DeleteProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, DeleteView):
    model = Project
    success_url = reverse_lazy("manage_projects")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        project = self.get_object()
        pk, title = project.pk, project.title
        messages.success(
            self.request, f"Proyecto '{title}' eliminado correctamente.")
        response = super().form_valid(form)
        sess = self.request.session
        raw_pid = sess.get('project_id')
        try:
            session_pid = int(raw_pid) if raw_pid is not None else None
        except (TypeError, ValueError):
            session_pid = None
        login_src = (sess.get('login_source') or '')
        if session_pid == pk or login_src.lower() == title.lower():
            for key in ('login_source', 'project_id', 'source'):
                sess.pop(key, None)
        return response


class CreateUserProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, CreateView):
    model = UserProject
    form_class = UserProjectForm
    template_name = "projects/create_user_projects.html"
    success_url = reverse_lazy("manage_projects_permissions")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(
            self.request, "Usuario añadido correctamente al proyecto.")
        return super().form_valid(form)

    def form_invalid(self, form):
        error_messages = []
        for _, errors in form.errors.items():
            # Join multiple errors for the same field
            error_list = ", ".join(errors)
            error_messages.append(f"{error_list}")

        # Join all fields' errors
        full_message = format_html("<br>".join(error_messages))

        # Display as a Django message (with HTML allowed)
        messages.error(self.request, full_message)

        return super().form_invalid(form)


class ManageUserProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, ListView):
    model = UserProject
    template_name = "projects/manage_projects_permissions.html"
    context_object_name = "user_projects"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return UserProject.objects.select_related('user', 'project').order_by('project__title', 'user__username')


class UpdateUserProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, UpdateView):
    model = UserProject
    form_class = UserProjectForm
    template_name = "projects/edit_user_projects.html"
    success_url = reverse_lazy("manage_projects_permissions")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(
            self.request, "Relación usuario-proyecto actualizada correctamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        error_messages = []
        for _, errors in form.errors.items():
            # Join multiple errors for the same field
            error_list = ", ".join(errors)
            error_messages.append(f"{error_list}")

        # Join all fields' errors
        full_message = format_html("<br>".join(error_messages))

        # Display as a Django message (with HTML allowed)
        messages.error(self.request, full_message)

        return super().form_invalid(form)


class DeleteUserProjectView(CustomLoginRedirectMixin, UserPassesTestMixin, DeleteView):
    model = UserProject
    template_name = "projects/delete_user_project.html"
    success_url = reverse_lazy("manage_projects_permissions")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        obj = self.get_object()
        messages.success(
            self.request,
            f"La relación entre '{obj.user.username}' y el proyecto '{obj.project.title}' se eliminó correctamente."
        )
        return super().form_valid(form)

    def form_invalid(self, form: Any):
        messages.error(
            self.request, "No se pudo eliminar la relación usuario-proyecto.")
        return super().form_invalid(form)


class Custom403View(TemplateView):
    template_name = "403.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        response = super().dispatch(request, *args, **kwargs)
        response.status_code = 403
        return response


class Custom404View(TemplateView):
    template_name = "404.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        response = super().dispatch(request, *args, **kwargs)
        response.status_code = 404
        return response
