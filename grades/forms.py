from crispy_forms.helper import FormHelper
from django import forms

from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import Session

from .models import Grade


class EnrollmentChoiceField(forms.ModelChoiceField):
    """Shows student full name instead of 'student → kelas' in the dropdown."""
    def label_from_instance(self, obj):
        return obj.student.get_full_name()


class GradeForm(forms.ModelForm):
    enrollment = EnrollmentChoiceField(
        queryset=Enrollment.objects.none(),
        label='Siswa',
        empty_label='— Pilih Siswa —',
    )

    class Meta:
        model = Grade
        fields = ['enrollment', 'grade_type', 'score', 'session', 'notes']
        labels = {
            'grade_type': 'Jenis Nilai',
            'score': 'Nilai (0 – 100)',
            'session': 'Pertemuan (opsional)',
            'notes': 'Catatan (opsional)',
        }
        widgets = {
            'score': forms.NumberInput(attrs={'min': '0', 'max': '100', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, kelas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

        if kelas:
            self.fields['enrollment'].queryset = (
                Enrollment.objects
                .filter(kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False)
                .select_related('student')
                .order_by('student__last_name', 'student__first_name')
            )
            self.fields['session'].queryset = (
                Session.objects.filter(kelas=kelas).order_by('session_number')
            )
        else:
            self.fields['session'].queryset = Session.objects.none()

        self.fields['session'].required = False
        self.fields['notes'].required = False
        self.fields['session'].empty_label = '— Tidak terkait pertemuan —'

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is not None and not (0 <= score <= 100):
            raise forms.ValidationError('Nilai harus antara 0 dan 100.')
        return score
