from django.http import FileResponse, Http404
import os
import subprocess

from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import File, Algorithm, Project, Execution, Output
import json
import uuid


ALLOWED_EXTENSIONS = {
    'csv': 'CSV',
    'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image',
    'mp4': 'Video', 'mov': 'Video', 'avi': 'Video',
}


class HomepageView(TemplateView):
    template_name = 'index.html'


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

            file_path = file_obj.file.path
            if os.path.exists(file_path):
                os.remove(file_path)

            file_obj.delete()
            messages.success(request, "Archivo eliminado correctamente.")
            return redirect('file_manager')

        uploaded_file = request.FILES.get('file')
        if uploaded_file is not None:
            file_type = getattr(uploaded_file, 'content_type', None)
            if file_type and (file_type.startswith('image/') or file_type.startswith('video/') or uploaded_file.name.endswith('.csv')):
                # Obtener nombre base y extensión
                base_name, ext = os.path.splitext(uploaded_file.name)

                # Revisar si ya existe un archivo con el mismo nombre para este usuario
                existing_names = File.objects.filter(
                    user=request.user).values_list('file', flat=True)
                # Los nombres en existing_names pueden ser rutas, extraemos solo el nombre del archivo
                existing_file_names = [
                    os.path.basename(n) for n in existing_names]

                final_name = uploaded_file.name
                was_renamed = False

                if final_name in existing_file_names:
                    # Generar un nombre único con sufijo aleatorio
                    final_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
                    was_renamed = True

                # Modificar el archivo cargado para cambiarle el nombre en memoria antes de guardar
                uploaded_file.name = final_name

                File.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    type=file_type,
                    upload_date=timezone.now()
                )

                if was_renamed:
                    messages.info(
                        request, f"El archivo ya existía y fue renombrado a '{final_name}'.")
                else:
                    messages.success(request, "Archivo subido exitosamente.")
            else:
                messages.error(request, "Tipo de archivo no permitido.")
        else:
            messages.error(request, "No se seleccionó ningún archivo.")

        return redirect('file_manager')


@method_decorator(login_required, name='dispatch')
class AnalysisView(View):
    template_name = 'analysis.html'

    def get(self, request: HttpRequest):
        # Get the project
        project_id = request.session.get('login_source')
        project = Project.objects.get(title=project_id)

        files = File.objects.filter(user=request.user)
        algorithms = Algorithm.objects.all().filter(project_id=project.pk)
        return render(request, self.template_name, {
            'files': files,
            'algorithms': algorithms
        })

    def post(self, request: HttpRequest):
        file_id = request.POST.get('file')
        algorithm_id = request.POST.get('algorithm')

        if not file_id or not algorithm_id:
            messages.error(request, "Debes seleccionar archivo y algoritmo.")
            return redirect('analysis')

        file = File.objects.get(id=file_id)
        algorithm = Algorithm.objects.get(id=algorithm_id)

        input_path = file.file.path
        media_root = settings.MEDIA_ROOT

        rel_path = os.path.relpath(input_path, media_root)
        parts = rel_path.split(os.sep)
        user_id = parts[1]

        filename, ext = os.path.splitext(parts[-1])
        output_dir = os.path.join(media_root, 'outputs', user_id)
        os.makedirs(output_dir, exist_ok=True)

        # Obtener la fecha y hora actual
        now = datetime.now()

        # Formatear como "YYYYMMDD_HHMMSS"
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        output_filename = f"{filename}_{algorithm.name}_{timestamp}_out{ext}"
        output_path = os.path.join(output_dir, output_filename)

        algorithm_script_path = algorithm.file.path  # Asegúrate que la ruta es correcta

        try:
            # Creamos Execution en base de datos
            exec = Execution.objects.create(execution_date=now, status="IN PROCESS",
                                            algorithm_id=algorithm_id, file_id=file_id, user=request.user)
            # Ejecutar el script python: python script.py input_path output_path
            subprocess.run(
                ['python', algorithm_script_path, input_path, output_path],
                check=True
            )

            # Guardamos los cambios en la base de datos
            exec.status = "COMPLETED"
            exec.save(update_fields=['status'])

            # Crear Output
            # rel_output_path = os.path.relpath(output_path, settings.MEDIA_ROOT)
            Output.objects.create(
                execution=exec,
                file=f"outputs/{user_id}/{output_filename}",
                output_date=now
            )

            messages.success(
                request,
                mark_safe(
                    f"Análisis con <strong>{algorithm.name}</strong> ejecutado sobre <strong>{file.filename()}</strong>. "
                    f"<a href='{reverse('results')}' class='btn btn-sm btn-link'>Ver resultados</a>"
                )
            )
        except subprocess.CalledProcessError as e:
            # Buscamos la ejecución fallida
            exec = Execution.objects.get(
                execution_date=now, algorithm_id=algorithm_id, file_id=file_id, user=request.user)
            exec.status = "FAILED"
            messages.error(request, f"Error al ejecutar el algoritmo: {e}")

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

        old_relative_path = file_obj.file.name
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

        results = []
        for execution in executions:
            output = Output.objects.filter(execution=execution).first()
            results.append({
                'id': execution.id,
                'original_filename': execution.file.filename,
                'algorithm_name': execution.algorithm.name,
                'execution_date': execution.execution_date,
                'output_id': output.id if output else None,
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
            except Execution.DoesNotExist:
                pass  # Silenciar si no se encuentra
        return redirect("results")


class DownloadOutputView(LoginRequiredMixin, View):
    def get(self, request, output_id):
        try:
            output = Output.objects.get(
                pk=output_id, execution__user=request.user)
            if not output.file:
                raise Http404("Output sin archivo asociado.")
            return FileResponse(output.file.open('rb'), as_attachment=True, filename=output.file.name)
        except Output.DoesNotExist:
            raise Http404("Output no encontrado.")
