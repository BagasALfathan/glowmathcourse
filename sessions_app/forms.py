from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field

from .models import Session


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['date', 'topic']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'topic': forms.TextInput(attrs={'placeholder': 'Topik pertemuan (opsional)'}),
        }
        labels = {
            'date': 'Tanggal',
            'topic': 'Topik',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('date', css_class='w-full'),
            Field('topic', css_class='w-full'),
        )
        self.fields['topic'].required = False
