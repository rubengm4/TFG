from django import forms
from .models import Algorithm, Project, UserProject


class AlgorithmArchiveWidget(forms.ClearableFileInput):
    """Same as Django’s clearable file input but without the “clear” checkbox."""

    template_name = "analysis/widgets/algorithm_archive_input.html"


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
            'requires_two_files',
            'input_is_dir',
        ]

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'entrypoint': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'main.py'}),
            # This doesn't need a 'form-control' class, as it's a different widget
            'supported_types': forms.CheckboxSelectMultiple(),
            'requires_two_files': forms.CheckboxInput(),
            'input_is_dir': forms.CheckboxInput(),
            'archive': AlgorithmArchiveWidget(
                attrs={'class': 'form-control', 'accept': '.zip'}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        archive = cleaned_data.get("archive")
        if self.instance.pk:
            if archive is False:
                raise forms.ValidationError(
                    {
                        "archive": (
                            "No puedes eliminar el archivo ZIP del algoritmo; "
                            "sube otro ZIP para reemplazarlo."
                        )
                    }
                )
        else:
            if not archive:
                raise forms.ValidationError(
                    {"archive": "Debes adjuntar un archivo ZIP."}
                )
        return cleaned_data

    def clean_archive(self):
        archive = self.cleaned_data.get('archive')
        if archive:
            if not archive.name.endswith('.zip'):
                raise forms.ValidationError(
                    "Solo se permiten archivos con extensión .zip")
            # Optional: check max size, MIME type, etc.
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
            },
                format="%Y-%m-%d",
            ),
        }


class UserProjectForm(forms.ModelForm):
    class Meta:
        model = UserProject
        fields = ['user', 'project', 'joined_at']
        widgets = {
            'joined_at': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format="%Y-%m-%d"),
        }
