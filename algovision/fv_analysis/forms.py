from django import forms
from .models import Algorithm


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
            'supported_types'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'entrypoint': forms.TextInput(attrs={'placeholder': 'main.py'}),
            'supported_types': forms.CheckboxSelectMultiple(),
            'archive': forms.ClearableFileInput(attrs={'accept': '.zip'})
        }

    def clean_archive(self):
        archive = self.cleaned_data.get('archive')
        if archive:
            if not archive.name.endswith('.zip'):
                raise forms.ValidationError(
                    "Solo se permiten archivos con extensión .zip")
            # Opcional: validar tamaño máximo, tipo MIME, etc.
        return archive
