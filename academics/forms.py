from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field

from .models import Kelas, AcademicPeriod, Subject


class KelasForm(forms.ModelForm):
    class Meta:
        model = Kelas
        fields = [
            'name', 'subject', 'academic_period', 'level',
            'capacity', 'total_sessions', 'start_date', 'end_date',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['academic_period'].queryset = AcademicPeriod.objects.filter(is_active=True)
        self.fields['subject'].queryset = (
            Subject.objects.filter(is_active=True).select_related('category')
        )
        self.fields['name'].label = 'Nama Kelas'
        self.fields['subject'].label = 'Mata Pelajaran'
        self.fields['academic_period'].label = 'Periode Akademik'
        self.fields['level'].label = 'Jenjang'
        self.fields['capacity'].label = 'Kapasitas (maks. siswa)'
        self.fields['total_sessions'].label = 'Total Pertemuan'
        self.fields['start_date'].label = 'Tanggal Mulai'
        self.fields['end_date'].label = 'Tanggal Selesai'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('name'),
            Row(
                Column('subject', css_class='md:col-span-1'),
                Column('academic_period', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('level', css_class='md:col-span-1'),
                Column('capacity', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('total_sessions', css_class='md:col-span-1'),
                Column(css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('start_date', css_class='md:col-span-1'),
                Column('end_date', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
        )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'Tanggal selesai harus setelah tanggal mulai.')
        return cleaned


class KelasEditForm(forms.ModelForm):
    """Same as KelasForm but excludes academic_period (cannot be changed after creation)."""

    class Meta:
        model = Kelas
        fields = [
            'name', 'subject', 'level',
            'capacity', 'total_sessions', 'start_date', 'end_date',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = (
            Subject.objects.filter(is_active=True).select_related('category')
        )
        self.fields['name'].label = 'Nama Kelas'
        self.fields['subject'].label = 'Mata Pelajaran'
        self.fields['level'].label = 'Jenjang'
        self.fields['capacity'].label = 'Kapasitas (maks. siswa)'
        self.fields['total_sessions'].label = 'Total Pertemuan'
        self.fields['start_date'].label = 'Tanggal Mulai'
        self.fields['end_date'].label = 'Tanggal Selesai'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('name'),
            Row(
                Column('subject', css_class='md:col-span-1'),
                Column('level', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('capacity', css_class='md:col-span-1'),
                Column('total_sessions', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('start_date', css_class='md:col-span-1'),
                Column('end_date', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
        )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'Tanggal selesai harus setelah tanggal mulai.')
        return cleaned
