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
        }
