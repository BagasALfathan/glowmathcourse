"""Course Materials — teacher upload/manage + student read-only views.

Reuses the teacher-photo upload pattern (size + extension validation in the
view; `FileField` on the model). Hard-delete is used here (no `is_deleted`
column on the model); soft-delete is reserved for User/Kelas/Enrollment
per project convention.
"""
import os

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from academics.models import Kelas
from activity_logs.utils import log_activity
from enrollments.models import Enrollment
from sessions_app.models import Session

from .models import CourseMaterial, FileType, detect_file_type


MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTS = {
    'pdf',
    'jpg', 'jpeg', 'png', 'gif', 'webp',
    'mp4', 'mov', 'webm',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'zip',
}


def _ext(filename):
    return (filename.rsplit('.', 1)[-1] if '.' in filename else '').lower()


# ── Teacher ────────────────────────────────────────────────────────────────

@role_required('TEACHER')
def teacher_materials(request, kelas_id):
    """Teacher manages materials for ONE class they own.

    POST = upload new material; GET = list + upload form.
    """
    teacher_profile = request.user.teacher_profile
    kelas = get_object_or_404(
        Kelas.objects.select_related('subject'),
        pk=kelas_id,
        teacher_profile=teacher_profile,
        is_deleted=False,
    )

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        session_id = request.POST.get('session') or ''
        is_visible = request.POST.get('is_visible') == '1'
        upload = request.FILES.get('file')

        err = None
        if not title:
            err = 'Judul wajib diisi.'
        elif not upload:
            err = 'File wajib diunggah.'
        elif upload.size > MAX_FILE_SIZE:
            err = f'Ukuran file maksimal {MAX_FILE_SIZE // (1024 * 1024)} MB.'
        elif _ext(upload.name) not in ALLOWED_EXTS:
            err = 'Tipe file tidak didukung. Gunakan PDF, gambar, video, atau dokumen Office.'

        session_obj = None
        if not err and session_id:
            session_obj = Session.objects.filter(
                pk=session_id, kelas=kelas,
            ).first()
            if session_obj is None:
                err = 'Sesi tidak valid untuk kelas ini.'

        if err:
            messages.error(request, err)
        else:
            material = CourseMaterial.objects.create(
                kelas=kelas,
                session=session_obj,
                uploaded_by=request.user,
                title=title,
                description=description,
                file=upload,
                file_type=detect_file_type(upload.name),
                is_visible=is_visible,
            )
            log_activity(request.user, 'created', 'course_material', material.pk)
            messages.success(request, f'✓ Materi "{material.title}" berhasil diunggah.')
            return redirect('course_materials:teacher_materials', kelas_id=kelas.pk)

    materials = (
        CourseMaterial.objects
        .filter(kelas=kelas)
        .select_related('session', 'uploaded_by')
        .order_by('-created_at')
    )
    sessions = (
        Session.objects
        .filter(kelas=kelas)
        .order_by('session_number')
    )
    return render(request, 'course_materials/teacher_list.html', {
        'kelas': kelas,
        'materials': materials,
        'sessions': sessions,
        'max_mb': MAX_FILE_SIZE // (1024 * 1024),
    })


@role_required('TEACHER')
@require_POST
def delete_material(request, pk):
    """Hard-delete a material the teacher owns (file removed from disk)."""
    teacher_profile = request.user.teacher_profile
    material = get_object_or_404(
        CourseMaterial,
        pk=pk,
        kelas__teacher_profile=teacher_profile,
        kelas__is_deleted=False,
    )
    kelas_id = material.kelas_id
    title = material.title
    if material.file:
        try:
            material.file.delete(save=False)
        except Exception:
            pass
    material.delete()
    log_activity(request.user, 'deleted', 'course_material', pk)
    messages.success(request, f'✓ Materi "{title}" dihapus.')
    return redirect('course_materials:teacher_materials', kelas_id=kelas_id)


@role_required('TEACHER')
@require_POST
def toggle_visibility(request, pk):
    """Flip is_visible. Hidden materials are invisible to students."""
    teacher_profile = request.user.teacher_profile
    material = get_object_or_404(
        CourseMaterial,
        pk=pk,
        kelas__teacher_profile=teacher_profile,
        kelas__is_deleted=False,
    )
    material.is_visible = not material.is_visible
    material.save(update_fields=['is_visible', 'updated_at'])
    state = 'ditampilkan' if material.is_visible else 'disembunyikan'
    messages.success(request, f'✓ Materi "{material.title}" {state}.')
    return redirect('course_materials:teacher_materials', kelas_id=material.kelas_id)


# ── Student ────────────────────────────────────────────────────────────────

@role_required('STUDENT')
def student_materials(request, enrollment_id):
    """Student views (read-only) the visible materials of a class they are
    actively enrolled in. Grouped by session.
    """
    student_profile = request.user.student_profile
    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            'kelas__subject',
            'kelas__teacher_profile__user',
        ),
        pk=enrollment_id,
        student_profile=student_profile,
        is_deleted=False,
        kelas__is_deleted=False,
    )
    kelas = enrollment.kelas

    visible_materials = list(
        CourseMaterial.objects
        .filter(kelas=kelas, is_visible=True)
        .select_related('session', 'uploaded_by')
        .order_by('session__session_number', '-created_at')
    )

    # Group by session (None → "Umum")
    groups = {}
    order = []
    for m in visible_materials:
        key = m.session_id if m.session_id else 0
        if key not in groups:
            groups[key] = {
                'session': m.session if m.session_id else None,
                'materials': [],
            }
            order.append(key)
        groups[key]['materials'].append(m)

    grouped = [groups[k] for k in order]

    return render(request, 'course_materials/student_list.html', {
        'enrollment': enrollment,
        'kelas': kelas,
        'grouped': grouped,
        'total': len(visible_materials),
    })
