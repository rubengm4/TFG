import os
import json
import shutil

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpRequest, Http404, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, CreateView, ListView, DeleteView, UpdateView

from typing import Any, List, Dict

from .aux_file_func import is_size_valid, is_type_valid, extension_getter, name_change
from .models import File, Algorithm, Project, Execution, Output
from .forms import AlgorithmForm
from .tasks import ejecutar_algoritmo_task, install_requirements_task, REQUIREMENTS_PATH


class HomepageView(TemplateView):
    template_name = 'index.html'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['type', 'upload_date']


@method_decorator(login_required, name='dispatch')
class FileManagerView(LoginRequiredMixin, View):
    template_name = 'file_manager.html'

    def get(self, request: HttpRequest):
        files = File.objects.filter(user=request.user)
        return render(request, self.template_name, {'files': files})

    def post(self, request: HttpRequest):
        if 'delete_file' in request.POST:
            file_id = request.POST.get('delete_file')
            file_obj = get_object_or_404(File, id=file_id)
            file_name = os.path.basename(file_obj.file.name)

            file_path = file_obj.file.path
            if os.path.exists(file_path):
                os.remove(file_path)

            file_obj.delete()
            messages.success(
                request, f"Archivo {file_name} eliminado correctamente.")
            return redirect('file_manager')

        uploaded_files = request.FILES.getlist('files')

        # Tamaño máximo de archivo admitido (en MB)
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

        # Leer file_id guardado en sesión para preseleccionar
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
            # Caso: vengo de /files solo con file_id para preselección
            request.session['selected_file_id'] = file_id
            return redirect('analysis')

        # Caso: vengo de formulario análisis para ejecutar (file y algo)
        if not file_id or not algorithm_id:
            messages.error(request, "Debes seleccionar archivo y algoritmo.")
            return redirect('analysis')

        try:
            file = File.objects.get(id=file_id)
            algorithm = Algorithm.objects.get(id=algorithm_id)
        except (File.DoesNotExist, Algorithm.DoesNotExist):
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

        # Guardar selección para que persista si vuelves a analysis
        request.session['selected_file_id'] = file_id
        request.session['selected_algorithm_id'] = algorithm_id

        supported_types = algorithm.supported_types.all()
        supported_names = ', '.join([str(ftype) for ftype in supported_types])

        # Validar compatibilidad del archivo con el algoritmo
        if file.type not in supported_types:
            messages.error(
                request,
                f"El archivo seleccionado no es compatible con el algoritmo '{algorithm.name}'. El algoritmo solo admite archivos de tipo: {supported_names}"
            )
            return redirect('analysis')

        # Validación de segundo archivo si se requiere
        second_file = None
        if algorithm.requires_two_files:
            if not second_file_id:
                messages.error(
                    request, "Este algoritmo requiere un segundo archivo.")
                return redirect('analysis')
            try:
                second_file = File.objects.get(id=second_file_id)
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

        # Crear ejecución (pero no correrla aquí)
        now = timezone.now()
        print(now)
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
                file_id, algorithm_id, exec.id, second_file.id)
        else:
            ejecutar_algoritmo_task.delay(
                file_id, algorithm_id, exec.id)

            messages.success(
                request,
                mark_safe(
                    f"Se ha iniciado el análisis con <strong>{algorithm.name}</strong> sobre <strong>{file.filename()}</strong>. "
                    f"Puedes consultar su estado en la pestaña de "
                    f"<a href='{results_url}' style='font-weight:700; text-decoration:none; color:inherit;'>Mis Resultados</a>"
                )
            )

        return redirect('analysis')


@method_decorator(csrf_exempt, name='dispatch')
class RenameFileView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, file_id: int):
        file_obj = get_object_or_404(File, id=file_id, user=request.user)
        data = json.loads(request.body)

        raw_input = data.get('new_name', '').strip()

        original_filename = os.path.basename(file_obj.file.name)
        current_base_name, ext = os.path.splitext(original_filename)

        # Extraemos solo la base del nuevo nombre, ignorando cualquier extensión que el usuario haya puesto
        base_name, _ = os.path.splitext(raw_input)

        # Validar nombre base: no vacío y que no empiece con punto
        if not base_name or base_name.startswith('.'):
            # Se mantiene el nombre actual
            return JsonResponse({'new_name': current_base_name})

        new_filename = f"{base_name}{ext}"

        # Si el nuevo nombre es igual al actual, no hacer nada
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


class ResultsView(LoginRequiredMixin, View):
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
                # Eliminar archivo del sistema de archivos
                if output and output.file and os.path.isfile(output.file.path):
                    os.remove(output.file.path)
                    output.delete()
                execution.delete()
                # TODO: DECIDIR SI QUEREMOS ELIMINAR EJECUCIONES O MARCAR COMO DELETED
            except Execution.DoesNotExist:
                pass  # Silenciar si no se encuentra
        return redirect("results")


class DownloadOutputView(LoginRequiredMixin, View):
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


class ManageRequirementsView(LoginRequiredMixin, UserPassesTestMixin, View):
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

        # Soporta solo logs si se llama con ?logs_only=1
        if request.GET.get('logs_only') == '1':
            from django.http import HttpResponse
            return HttpResponse(logs)

        return render(request, self.template_name, {
            'packages': packages,
            'logs': logs
        })

    def post(self, request):
        # Recolectar filas enviadas
        package_names = request.POST.getlist('package_name')
        package_versions = request.POST.getlist('package_version')

        lines = []
        for name, version in zip(package_names, package_versions):
            name = name.strip()
            version = version.strip() or ''  # si no hay version, se instala latest
            if name:
                if version:
                    lines.append(f"{name}=={version}")
                else:
                    lines.append(name)

        # Guardar en requirements_global.txt
        os.makedirs(os.path.dirname(REQUIREMENTS_PATH), exist_ok=True)
        with open(REQUIREMENTS_PATH, 'w') as f:
            f.write("\n".join(lines) + "\n")

        # Lanzar instalación via Celery
        install_requirements_task.delay()

        messages.success(
            request, "Requirements guardados y la instalación se ha iniciado en segundo plano.")
        return redirect('manage_requirements')

    def test_func(self):
        return self.request.user.is_superuser


# Guardamos un timestamp global en memoria para simplicidad
# Cada vez que se actualiza requirements_global.txt se cambia
REQUIREMENTS_LAST_MOD = 0


class RequirementsJSONView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request):
        global REQUIREMENTS_LAST_MOD
        packages = []

        if REQUIREMENTS_PATH.exists():
            # timestamp de modificación del archivo
            ts = int(REQUIREMENTS_PATH.stat().st_mtime)

            # solo actualizamos el hash si cambió
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


class CreateAlgorithmView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Algorithm
    form_class = AlgorithmForm
    template_name = "algorithms/create_algorithm.html"
    # Ajusta a tu vista de listado
    success_url = reverse_lazy("manage_algorithms")

    def test_func(self):
        return self.request.user.is_superuser


class ManageAlgorithmsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
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


class UpdateAlgorithmView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Algorithm
    form_class = AlgorithmForm
    template_name = 'algorithms/edit_algorithm.html'
    success_url = reverse_lazy('manage_algorithms')

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any):
        obj: Any | None = self.get_object()
        new_archive = form.cleaned_data.get('archive')

        # Verificamos si el archivo ha cambiado
        if new_archive and new_archive != obj.archive:
            # Ruta del archivo anterior
            old_file_path = obj.archive.path
            # Carpeta asociada (sin la extensión .zip)
            old_folder_path = os.path.splitext(old_file_path)[0]

            # Eliminar el archivo anterior si existe
            if os.path.isfile(old_file_path):
                os.remove(old_file_path)

            # Eliminar la carpeta asociada si existe
            if os.path.isdir(old_folder_path):
                shutil.rmtree(old_folder_path)

        messages.success(self.request, "Algoritmo editado correctamente.")
        return super().form_valid(form)


class DeleteAlgorithmView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Algorithm
    success_url = reverse_lazy("manage_algorithms")

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form: Any) -> Any:
        # Access the object to be deleted
        obj: Any = self.get_object()

        # Delete the associated file if it exists
        if obj.archive:
            file_path = obj.archive.path
            if os.path.isfile(file_path):
                os.remove(file_path)

            # Ruta a la carpeta con el mismo nombre (sin extensión .zip)
            folder_path = os.path.splitext(file_path)[0]
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)

        # Proceed with the usual deletion (calls obj.delete())
        return super().form_valid(form)

# Errores


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
