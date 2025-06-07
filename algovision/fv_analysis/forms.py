# forms.py
from django import forms
from .models import Algorithm


class AlgorithmForm(forms.ModelForm):
    class Meta:
        model = Algorithm
        fields = ['name', 'file', 'project', 'version', 'description']
