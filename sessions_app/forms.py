from django import forms
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field

from .models import Session

# Python weekday(): 0=Mon … 5=Sat, 6=Sun
_WEEKDAY_TO_DAY = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['date', 'start_time', 'end_time', 'topic', 'capacity']
        widgets = {
            'date':       forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time':   forms.TimeInput(attrs={'type': 'time'}),
            'topic':      forms.TextInput(attrs={'placeholder': 'Topik pertemuan (opsional)'}),
            'capacity':   forms.NumberInput(attrs={'min': '1', 'placeholder': 'Misal: 10'}),
        }
        labels = {
            'date':       'Tanggal*',
            'start_time': 'Jam Mulai*',
            'end_time':   'Jam Selesai*',
            'topic':      'Topik',
            'capacity':   'Kapasitas Peserta*',
        }

    def __init__(self, *args, kelas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kelas = kelas
        today_str = timezone.localdate().isoformat()

        is_new = not self.instance.pk
        if is_new:
            self.fields['date'].widget.attrs['min'] = today_str
            if not args[0]:  # no POST data → default today
                self.fields['date'].initial = today_str
            if kelas:
                cap = kelas.capacity
                self.fields['capacity'].initial = cap if cap and cap > 0 else None

        self.fields['topic'].required = False
        self.fields['capacity'].required = True
        self.fields['start_time'].required = True
        self.fields['end_time'].required = True

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('date', css_class='w-full'),
            Field('start_time', css_class='w-full'),
            Field('end_time', css_class='w-full'),
            Field('topic', css_class='w-full'),
            Field('capacity', css_class='w-full'),
        )

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if not date:
            return date

        if self.instance.pk:
            # Editing — block date change if bookings/attendance exist
            original_date = (
                Session.objects.filter(pk=self.instance.pk)
                .values_list('date', flat=True)
                .first()
            )
            if date != original_date:
                has_bookings = self.instance.bookings.filter(status='BOOKED').exists()
                has_attendance = self.instance.attendances.exists()
                if has_bookings or has_attendance:
                    raise forms.ValidationError(
                        'Tanggal tidak dapat diubah karena pertemuan ini '
                        'sudah memiliki pendaftar atau catatan absensi.'
                    )
        else:
            # New session — must not be in the past
            today = timezone.localdate()
            if date < today:
                raise forms.ValidationError('Tanggal pertemuan tidak boleh sebelum hari ini.')

        # Validate date falls on a scheduled (operating hours) day
        if self.kelas:
            schedules = list(self.kelas.schedules.all())
            if schedules:
                scheduled_days = {s.day for s in schedules}
                day_name = _WEEKDAY_TO_DAY[date.weekday()]
                if day_name not in scheduled_days:
                    day_labels = [
                        s.get_day_display()
                        for s in sorted(schedules, key=lambda s: _WEEKDAY_TO_DAY.index(s.day))
                    ]
                    raise forms.ValidationError(
                        f'Tanggal harus jatuh pada hari {" atau ".join(day_labels)}.'
                    )
        return date

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity is not None and capacity < 1:
            raise forms.ValidationError('Kapasitas harus minimal 1 peserta.')
        return capacity

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        date = cleaned_data.get('date')

        # Basic sanity: end > start
        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', 'Jam selesai harus setelah jam mulai.')
            return cleaned_data

        if date and start_time and end_time and self.kelas:
            day_name = _WEEKDAY_TO_DAY[date.weekday()]
            schedule = self.kelas.schedules.filter(day=day_name).first()

            if schedule:
                # Validate times fall within operating hours
                if start_time < schedule.start_time:
                    self.add_error(
                        'start_time',
                        f'Jam mulai harus dalam jam operasional kelas '
                        f'({schedule.start_time.strftime("%H:%M")}–{schedule.end_time.strftime("%H:%M")}).',
                    )
                if end_time > schedule.end_time:
                    self.add_error(
                        'end_time',
                        f'Jam selesai harus dalam jam operasional kelas '
                        f'({schedule.start_time.strftime("%H:%M")}–{schedule.end_time.strftime("%H:%M")}).',
                    )

            # Overlap check: no overlap with other sessions on same date/class
            if not self.errors:
                pk = self.instance.pk if self.instance.pk else None
                overlapping_qs = Session.objects.filter(
                    kelas=self.kelas,
                    date=date,
                ).exclude(status='CANCELLED')
                if pk:
                    overlapping_qs = overlapping_qs.exclude(pk=pk)

                for other in overlapping_qs:
                    if other.start_time and other.end_time:
                        if start_time < other.end_time and end_time > other.start_time:
                            self.add_error(
                                None,
                                f'Pertemuan tidak boleh tumpang tindih dengan pertemuan lain di hari yang sama '
                                f'(Pertemuan ke-{other.session_number}: '
                                f'{other.start_time.strftime("%H:%M")}–{other.end_time.strftime("%H:%M")}).',
                            )
                            break

        return cleaned_data
