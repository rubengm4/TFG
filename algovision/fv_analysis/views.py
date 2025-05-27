import os

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import File, Algorithm
import json


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

    def get(self, request):
        files = File.objects.all().order_by('-upload_date')
        return render(request, self.template_name, {'files': files})

    def post(self, request):
        # Verificamos si es una subida o eliminación
        if 'delete_file' in request.POST:
            file_id = request.POST.get('delete_file')
            file_obj = get_object_or_404(File, id=file_id)

            # Eliminamos el archivo del sistema de archivos
            file_path = file_obj.file.path
            if os.path.exists(file_path):
                os.remove(file_path)

            file_obj.delete()
            messages.success(request, "Archivo eliminado correctamente.")
            return redirect('file_manager')

        # Subida de archivos
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            file_type = uploaded_file.content_type
            if file_type.startswith('image/') or file_type.startswith('video/') or uploaded_file.name.endswith('.csv'):
                File.objects.create(
                    user=request.user,
                    file=uploaded_file,  # <-- el archivo real, no el nombre
                    type=file_type,
                    upload_date=timezone.now()
                )
                messages.success(request, "Archivo subido exitosamente.")
            else:
                messages.error(request, "Tipo de archivo no permitido.")
        else:
            messages.error(request, "No se seleccionó ningún archivo.")

        return redirect('file_manager')


@method_decorator(login_required, name='dispatch')
class AnalysisView(View):
    template_name = 'analysis.html'

    def get(self, request):
        files = File.objects.all()
        algorithms = Algorithm.objects.all()
        return render(request, self.template_name, {
            'files': files,
            'algorithms': algorithms
        })

    def post(self, request):
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
    def post(self, request, file_id):
        file_obj = get_object_or_404(File, id=file_id, user=request.user)
        data = json.loads(request.body)
        new_base_name = data.get('new_name')

        if not new_base_name:
            return JsonResponse({'error': 'Invalid name'}, status=400)

        # Extraer extensión original
        original_filename = os.path.basename(file_obj.file.name)
        _, ext = os.path.splitext(original_filename)

        # Limpiar cualquier extensión que el usuario haya escrito por error
        base_name, _ = os.path.splitext(new_base_name)

        # Reconstruir nuevo nombre con extensión original
        new_filename = f"{base_name}{ext}"

        old_relative_path = file_obj.file.name
        old_path = os.path.join(settings.MEDIA_ROOT, old_relative_path)

        new_relative_path = f"uploads/{new_filename}"
        new_path = os.path.join(settings.MEDIA_ROOT, new_relative_path)

        if os.path.exists(new_path):
            return JsonResponse({'error': 'Ya existe un archivo con ese nombre.'}, status=400)

        try:
            os.rename(old_path, new_path)
            file_obj.file.name = new_relative_path
            file_obj.save()
            # solo nombre base al frontend
            return JsonResponse({'new_name': base_name})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
