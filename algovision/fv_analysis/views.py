import os

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView

from .models import File, Algorithm


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
