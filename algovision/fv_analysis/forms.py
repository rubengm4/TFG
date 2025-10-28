from django import forms
from .models import Algorithm, Project, UserProject


class AlgorithmForm(forms.ModelForm):
    class Meta:
        model = Algorithm
        fields = [
            'name',
            'project',
            'version',
            'description',
            'archive',
            'entrypoint',
            'supported_types',
            'requires_two_files'
        ]

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'entrypoint': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'main.py'}),
            'supported_types': forms.CheckboxSelectMultiple(),  # Este no usa form-control
            'requires_two_files': forms.CheckboxInput(),
            'archive': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.zip'})
        }

    def clean_archive(self):
        archive = self.cleaned_data.get('archive')
        if archive:
            if not archive.name.endswith('.zip'):
                raise forms.ValidationError(
                    "Solo se permiten archivos con extensión .zip")
            # Opcional: validar tamaño máximo, tipo MIME, etc.
        return archive

    def clean_supported_types(self):
        supported_types = self.cleaned_data.get('supported_types')
        if not supported_types or supported_types.count() == 0:
            raise forms.ValidationError(
                "Debes seleccionar al menos un tipo soportado."
            )
        return supported_types


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "start_date"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "w-full border border-gray-300 rounded-lg p-2",
                "placeholder": "Título del proyecto"
            }),
            "description": forms.Textarea(attrs={
                "class": "w-full border border-gray-300 rounded-lg p-2",
                "rows": 4,
                "placeholder": "Descripción del proyecto"
            }),
            "start_date": forms.DateInput(attrs={
                "class": "w-full border border-gray-300 rounded-lg p-2",
                "type": "date"
            }),
        }


class UserProjectForm(forms.ModelForm):
    class Meta:
        model = UserProject
        fields = ['user', 'project', 'joined_at']
        widgets = {
            'joined_at': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
