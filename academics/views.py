from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

from accounts.decorators import role_required
from .models import Kelas, Schedule, KelasStatus, Day
from .forms import KelasForm


@role_required('TEACHER')
def teacher_classes_list(request):
    status_filter = request.GET.get('status', '')
    qs = (
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False)
        .select_related('subject', 'academic_period')
        .prefetch_related('schedules')
    )
    if status_filter and status_filter in KelasStatus.values:
        qs = qs.filter(status=status_filter)

    return render(request, 'academics/teacher_classes.html', {
        'klasses': qs,
        'status_filter': status_filter,
        'KelasStatus': KelasStatus,
    })


@role_required('TEACHER')
def teacher_class_create(request):
    form = KelasForm(request.POST or None)
    schedule_errors = []
    posted_schedules = []

    if request.method == 'POST':
        # Parse schedule rows from POST
        i = 0
        while f'schedule_day_{i}' in request.POST:
            posted_schedules.append({
                'day': request.POST.get(f'schedule_day_{i}', '').strip(),
                'start_time': request.POST.get(f'schedule_start_time_{i}', '').strip(),
                'end_time': request.POST.get(f'schedule_end_time_{i}', '').strip(),
                'room': request.POST.get(f'schedule_room_{i}', '').strip(),
            })
            i += 1

        # Validate schedules
        if not posted_schedules:
            schedule_errors.append('Minimal satu jadwal harus ditambahkan.')
        else:
            for idx, sched in enumerate(posted_schedules, start=1):
                if not sched['day']:
                    schedule_errors.append(f'Jadwal {idx}: Hari wajib dipilih.')
                if not sched['start_time']:
                    schedule_errors.append(f'Jadwal {idx}: Jam mulai wajib diisi.')
                if not sched['end_time']:
                    schedule_errors.append(f'Jadwal {idx}: Jam selesai wajib diisi.')
                elif sched['start_time'] and sched['end_time'] and sched['start_time'] >= sched['end_time']:
                    schedule_errors.append(f'Jadwal {idx}: Jam selesai harus lebih besar dari jam mulai.')

        if form.is_valid() and not schedule_errors:
            with transaction.atomic():
                kelas = form.save(commit=False)
                kelas.teacher = request.user
                kelas.save()
                for sched in posted_schedules:
                    Schedule.objects.create(
                        kelas=kelas,
                        day=sched['day'],
                        start_time=sched['start_time'],
                        end_time=sched['end_time'],
                        room=sched['room'],
                    )
            messages.success(request, 'Kelas berhasil dibuat!')
            return redirect('academics:teacher_classes')

    return render(request, 'academics/teacher_class_create.html', {
        'form': form,
        'schedule_errors': schedule_errors,
        'posted_schedules': posted_schedules,
        'day_choices': Day.choices,
    })
