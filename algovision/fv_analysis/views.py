import os

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import File, Algorithm
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
        files = File.objects.filter(user=request.user).order_by('-upload_date')
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
        files = File.objects.all().filter(user=request.user)
        algorithms = Algorithm.objects.all()
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

        # TODO: Ejecutar análisis (interpretar archivo python y devolver resultado)
        file = File.objects.get(id=file_id)
        algorithm = Algorithm.objects.get(id=algorithm_id)
        messages.success(
            request, f"Análisis con {algorithm.name} ejecutado sobre {file.file.name}")

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
