import re
import urllib.parse

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from .forms import (
    LoginForm, StudentRegistrationForm, TeacherRegistrationForm,
    ProfileUserForm, StudentProfileEditForm, TeacherProfileEditForm, AdminProfileEditForm,
)
from .models import (
    User, Role, ApprovalStatus, Level, Gender, Education,
    StudentProfile, TeacherProfile, TeacherJenjang, AdminProfile,
)

WHATSAPP_NUMBER = '6281234567890'


def _build_wa_url(full_name, role_display):
    text = (
        f'Halo admin, saya baru mendaftar di GlowMathCourse '
        f'dengan nama {full_name} sebagai {role_display}. Mohon persetujuan.'
    )
    return f'https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(text)}'


# ─── 3-portal login (role-strict) ──────────────────────────────────────────────

_PORTAL_BY_ROLE = {
    Role.STUDENT: ('/', 'siswa'),
    Role.TEACHER: ('/guru/login/', 'guru'),
    Role.ADMIN:   ('/admin/login/', 'admin'),
}


def _wrong_portal_message(actual_role, expected_role):
    """Return Indonesian error guiding user to the correct portal."""
    target_url, target_label = _PORTAL_BY_ROLE.get(actual_role, ('/', actual_role.lower()))
    return (
        f'Akun {target_label} harus login di portal {target_label}. '
        f'<a href="{target_url}" class="font-semibold underline">Buka portal {target_label} →</a>'
    )


def _resolve_user(username_or_email):
    """Look up a User by username OR email (case-insensitive on email)."""
    if not username_or_email:
        return None
    return (
        User.objects.filter(username=username_or_email, is_deleted=False).first()
        or User.objects.filter(email__iexact=username_or_email, is_deleted=False).first()
    )


def _do_role_login(request, expected_role, template_name, dashboard_url, extra_context=None):
    """Shared login handler: enforce role match, approval status, and auth."""
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    context = {**(extra_context or {})}

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''

        user_obj = _resolve_user(username)
        if user_obj is None or not user_obj.check_password(password):
            messages.error(request, 'Username atau kata sandi salah.')
            return render(request, template_name, context)

        if user_obj.role != expected_role:
            messages.error(request, _wrong_portal_message(user_obj.role, expected_role), extra_tags='safe')
            return render(request, template_name, context)

        if user_obj.approval_status == ApprovalStatus.PENDING:
            # Log the user in so the waiting page can show their info, then redirect.
            # Force-activate for the session (is_active stays False persistently).
            if not user_obj.is_active:
                user_obj.backend = 'django.contrib.auth.backends.ModelBackend'
                user_obj.is_active = True
                user_obj.save(update_fields=['is_active'])
            user = authenticate(request, username=user_obj.username, password=password)
            if user is None:
                # Fall back: log them in directly using the model backend
                user_obj.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user_obj)
            else:
                login(request, user)
            request.session['waiting_name'] = user_obj.get_full_name() or user_obj.username
            request.session['waiting_role'] = user_obj.get_role_display()
            return redirect('accounts:waiting')

        if user_obj.approval_status == ApprovalStatus.REJECTED:
            context['rejected_wa_url'] = _build_wa_url(
                user_obj.get_full_name() or user_obj.username,
                user_obj.get_role_display(),
            )
            messages.error(
                request,
                'Pendaftaran Anda ditolak admin. Silakan hubungi admin untuk informasi lebih lanjut.',
            )
            return render(request, template_name, context)

        user = authenticate(request, username=user_obj.username, password=password)
        if user is None:
            messages.error(request, 'Username atau kata sandi salah.')
            return render(request, template_name, context)

        login(request, user)
        return redirect(request.GET.get('next') or dashboard_url)

    return render(request, template_name, context)


def login_student_view(request):
    return _do_role_login(
        request,
        expected_role=Role.STUDENT,
        template_name='accounts/login_student.html',
        dashboard_url='/dashboard/student/',
    )


def login_teacher_view(request):
    return _do_role_login(
        request,
        expected_role=Role.TEACHER,
        template_name='accounts/login_teacher.html',
        dashboard_url='/dashboard/teacher/',
    )


def login_admin_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    context = {}

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''

        user_obj = _resolve_user(username)
        if user_obj is None or not user_obj.check_password(password):
            messages.error(request, 'Autentikasi gagal.')
            return render(request, 'accounts/login_admin.html', context)

        if user_obj.role != Role.ADMIN:
            messages.error(request, 'Akun ini bukan akun admin. Akses ditolak.')
            return render(request, 'accounts/login_admin.html', context)

        if user_obj.approval_status != ApprovalStatus.APPROVED:
            messages.error(request, 'Akun admin tidak aktif. Hubungi superadmin.')
            return render(request, 'accounts/login_admin.html', context)

        user = authenticate(request, username=user_obj.username, password=password)
        if user is None:
            messages.error(request, 'Autentikasi gagal.')
            return render(request, 'accounts/login_admin.html', context)

        login(request, user)

        # Log every successful admin login with IP + user agent
        try:
            from activity_logs.models import ActivityLog
            ActivityLog.objects.create(
                user=user,
                action='ADMIN_LOGIN',
                target_type='user',
                target_id=user.pk,
                ip_address=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
            )
        except Exception:
            pass  # never block login on logging failure

        return redirect(request.GET.get('next') or '/dashboard/admin/')

    return render(request, 'accounts/login_admin.html', context)


def _client_ip(request):
    """Best-effort client IP, honouring X-Forwarded-For when present."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# Backward-compat alias for any code still importing `login_view`
login_view = login_student_view


def register_view(request):
    # Legacy hub — student is the default registration flow now
    if request.user.is_authenticated:
        return redirect('dashboard:router')
    return redirect('accounts:register')


_PHONE_RE = re.compile(r'^(\+?62|0)\d{8,13}$')


def _norm_phone(raw):
    if not raw:
        return ''
    p = raw.strip().replace(' ', '').replace('-', '')
    if p.startswith('+62'):
        p = '0' + p[3:]
    elif p.startswith('62'):
        p = '0' + p[2:]
    return p


def _parse_register_payload(post, is_teacher):
    """Validate + normalise the wizard POST payload. Returns (data_dict, error_list)."""
    from django.core.exceptions import ValidationError as _DjangoValidationError
    from django.contrib.auth.password_validation import validate_password

    errors = []
    g = lambda k: (post.get(k) or '').strip()

    username = g('username')
    email = g('email')
    password = g('password')
    password2 = g('password2')
    full_name = g('full_name')
    phone = _norm_phone(g('phone'))

    # Step 1: account
    if not re.fullmatch(r'[A-Za-z0-9_]{3,30}', username):
        errors.append('Username 3-30 karakter, hanya huruf/angka/underscore.')
    if '@' not in email or '.' not in email.split('@')[-1]:
        errors.append('Email tidak valid.')
    if password != password2:
        errors.append('Konfirmasi kata sandi tidak cocok.')
    try:
        validate_password(password)
    except _DjangoValidationError as exc:
        errors.append(' '.join(exc.messages))

    # Step 2 (common): identity
    if not full_name or len(full_name) < 2:
        errors.append('Nama lengkap wajib diisi.')
    if not _PHONE_RE.match(phone):
        errors.append('Nomor WA tidak valid (gunakan format 08xxx atau +62xxx).')

    data = {
        'username': username, 'email': email, 'password': password,
        'full_name': full_name, 'phone': phone,
    }

    if not is_teacher:
        level = g('level')
        if level not in Level.values:
            errors.append('Jenjang wajib dipilih.')
        gender = g('gender')
        if gender and gender not in Gender.values:
            errors.append('Pilihan jenis kelamin tidak valid.')
        dob_raw = g('date_of_birth')
        try:
            from datetime import datetime as _dt
            dob = _dt.strptime(dob_raw, '%Y-%m-%d').date() if dob_raw else None
        except ValueError:
            errors.append('Format tanggal lahir tidak valid.')
            dob = None
        school_grade_raw = g('school_grade')
        try:
            school_grade = int(school_grade_raw) if school_grade_raw else None
        except ValueError:
            school_grade = None
        school_name = g('school_name')
        if not school_name:
            errors.append('Asal sekolah wajib diisi (atau tulis "—").')
        parent_name = g('parent_name')
        parent_phone = _norm_phone(g('parent_phone'))
        if not parent_name:
            errors.append('Nama orang tua wajib diisi.')
        if not _PHONE_RE.match(parent_phone):
            errors.append('Nomor WA orang tua tidak valid.')
        parent_email = g('parent_email')

        data.update({
            'level': level, 'gender': gender, 'date_of_birth': dob,
            'school_name': school_name, 'school_grade': school_grade,
            'parent_name': parent_name, 'parent_phone': parent_phone,
            'address': parent_email,  # store parent_email in address field until a dedicated column exists
        })
    else:
        education = g('education')
        if education and education not in Education.values:
            errors.append('Pilihan pendidikan tidak valid.')
        try:
            experience_years = int(g('experience_years') or '0')
        except ValueError:
            experience_years = 0
        specialization = g('specialization')
        if not specialization:
            errors.append('Spesialisasi wajib diisi.')
        jenjang_levels = [lvl for lvl in post.getlist('jenjang_levels') if lvl in Level.values]
        if not jenjang_levels:
            errors.append('Pilih minimal satu jenjang yang dapat Anda ajar.')
        bio = g('bio')[:500]
        rate_raw = g('hourly_rate').replace('.', '').replace(',', '').replace('Rp', '').strip()
        try:
            from decimal import Decimal
            hourly_rate = Decimal(rate_raw) if rate_raw else None
        except Exception:
            hourly_rate = None
        bank_account = g('bank_account')

        data.update({
            'education': education, 'experience_years': experience_years,
            'specialization': specialization, 'jenjang_levels': jenjang_levels,
            'bio': bio, 'hourly_rate': hourly_rate, 'bank_account': bank_account,
        })

    return data, errors


def register_student_view(request):
    """Step-cards register wizard for students.
    Templates submit all 3 step's fields in one final POST."""
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    if request.method != 'POST':
        return render(request, 'accounts/register_student.html', {
            'level_choices': Level.choices,
            'gender_choices': Gender.choices,
        })

    data, errors = _parse_register_payload(request.POST, is_teacher=False)

    if not errors:
        # Block re-registration
        existing = (
            User.objects
            .filter(email__iexact=data['email'], is_deleted=False)
            .exclude(approval_status=ApprovalStatus.APPROVED)
            .first()
            or User.objects
            .filter(username=data['username'], is_deleted=False)
            .exclude(approval_status=ApprovalStatus.APPROVED)
            .first()
        )
        if existing:
            if existing.approval_status == ApprovalStatus.PENDING:
                request.session['waiting_name'] = existing.get_full_name() or existing.username
                request.session['waiting_role'] = existing.get_role_display()
                messages.info(request, 'Anda sudah terdaftar dan menunggu persetujuan admin.')
                return redirect('accounts:waiting')
            errors.append('Akun ini pernah ditolak admin. Silakan hubungi admin.')

    if not errors:
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['full_name'],
            last_name='',
            role=Role.STUDENT,
            is_active=False,
            approval_status=ApprovalStatus.PENDING,
            phone=data['phone'],
        )
        profile = user.student_profile
        profile.level = data['level']
        profile.school_name = data['school_name']
        profile.school_grade = data['school_grade']
        profile.date_of_birth = data['date_of_birth']
        profile.gender = data['gender']
        profile.parent_name = data['parent_name']
        profile.parent_phone = data['parent_phone']
        profile.address = data.get('address', '')
        profile.save()

        request.session['waiting_name'] = user.get_full_name() or user.username
        request.session['waiting_role'] = user.get_role_display()
        return redirect('accounts:waiting')

    for msg in errors:
        messages.error(request, msg)
    return render(request, 'accounts/register_student.html', {
        'form_data': request.POST,
        'level_choices': Level.choices,
        'gender_choices': Gender.choices,
    })


def register_teacher_view(request):
    """Step-cards register wizard for teachers."""
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    if request.method != 'POST':
        return render(request, 'accounts/register_teacher.html', {
            'level_choices': Level.choices,
            'education_choices': Education.choices,
        })

    data, errors = _parse_register_payload(request.POST, is_teacher=True)

    if not errors:
        existing = (
            User.objects
            .filter(email__iexact=data['email'], is_deleted=False)
            .exclude(approval_status=ApprovalStatus.APPROVED)
            .first()
            or User.objects
            .filter(username=data['username'], is_deleted=False)
            .exclude(approval_status=ApprovalStatus.APPROVED)
            .first()
        )
        if existing:
            if existing.approval_status == ApprovalStatus.PENDING:
                request.session['waiting_name'] = existing.get_full_name() or existing.username
                request.session['waiting_role'] = existing.get_role_display()
                messages.info(request, 'Anda sudah terdaftar dan menunggu persetujuan admin.')
                return redirect('accounts:waiting')
            errors.append('Akun ini pernah ditolak admin. Silakan hubungi admin.')

    if not errors:
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['full_name'],
            last_name='',
            role=Role.TEACHER,
            is_active=False,
            approval_status=ApprovalStatus.PENDING,
            phone=data['phone'],
        )
        profile = user.teacher_profile
        profile.education = data['education']
        profile.experience_years = data['experience_years']
        profile.specialization = data['specialization']
        profile.bio = data['bio']
        profile.hourly_rate = data['hourly_rate']
        profile.bank_account = data['bank_account']
        profile.save()
        profile.set_jenjang(data['jenjang_levels'])

        request.session['waiting_name'] = user.get_full_name() or user.username
        request.session['waiting_role'] = user.get_role_display()
        return redirect('accounts:waiting')

    for msg in errors:
        messages.error(request, msg)
    return render(request, 'accounts/register_teacher.html', {
        'form_data': request.POST,
        'level_choices': Level.choices,
        'education_choices': Education.choices,
    })



def waiting_view(request):
    """Show pending-approval status. Used by both newly-registered (anon, session-based)
    and PENDING users who just tried to log in (authenticated)."""
    if request.user.is_authenticated:
        if request.user.approval_status == ApprovalStatus.APPROVED:
            return redirect('dashboard:router')
        # PENDING/REJECTED: show waiting card with real user info
        user = request.user
        name = user.get_full_name() or user.username
        wa_url = _build_wa_url(name, user.get_role_display())
        return render(request, 'accounts/waiting.html', {
            'waiting_user': user,
            'waiting_name': name,
            'waiting_role': user.get_role_display(),
            'wa_url': wa_url,
            'wa_admin_number': WHATSAPP_NUMBER,
        })

    # Anonymous fallback: just-completed registration flow uses session
    name = request.session.get('waiting_name', '')
    role = request.session.get('waiting_role', '')
    wa_url = _build_wa_url(name, role) if name else f'https://wa.me/{WHATSAPP_NUMBER}'
    return render(request, 'accounts/waiting.html', {
        'waiting_user': None,
        'waiting_name': name,
        'waiting_role': role,
        'wa_url': wa_url,
        'wa_admin_number': WHATSAPP_NUMBER,
    })


@login_required
def profile_view(request):
    user = request.user
    profile = None
    if user.role == Role.STUDENT:
        profile, _ = StudentProfile.objects.get_or_create(user=user)
    elif user.role == Role.TEACHER:
        profile, _ = TeacherProfile.objects.get_or_create(user=user)
    elif user.role == Role.ADMIN:
        profile, _ = AdminProfile.objects.get_or_create(user=user)
    return render(request, 'accounts/profile.html', {'profile': profile})


@login_required
def profile_edit_view(request):
    user = request.user
    user_form = ProfileUserForm(request.POST or None, instance=user)

    if user.role == Role.STUDENT:
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        profile_form = StudentProfileEditForm(request.POST or None, instance=profile)
    elif user.role == Role.TEACHER:
        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        profile_form = TeacherProfileEditForm(request.POST or None, instance=profile)
    elif user.role == Role.ADMIN:
        profile, _ = AdminProfile.objects.get_or_create(user=user)
        profile_form = AdminProfileEditForm(request.POST or None, instance=profile)
    else:
        profile_form = None

    if request.method == 'POST':
        user_valid = user_form.is_valid()
        profile_valid = profile_form.is_valid() if profile_form else True

        photo_err = None
        if user.role == Role.TEACHER:
            photo_file = request.FILES.get('photo')
            if photo_file:
                if photo_file.size > 2 * 1024 * 1024:
                    photo_err = 'Ukuran foto maksimal 2 MB.'
                else:
                    ext = photo_file.name.rsplit('.', 1)[-1].lower()
                    if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                        photo_err = 'Format foto harus JPG, PNG, atau WebP.'

        if user_valid and profile_valid and not photo_err:
            user_form.save()
            if profile_form:
                saved_profile = profile_form.save(commit=False)
                if user.role == Role.TEACHER:
                    if request.POST.get('remove_photo') == '1':
                        if saved_profile.photo:
                            saved_profile.photo.delete(save=False)
                        saved_profile.photo = None
                    elif 'photo' in request.FILES:
                        saved_profile.photo = request.FILES['photo']
                saved_profile.save()
            messages.success(request, 'Profil berhasil diperbarui!')
            return redirect('accounts:profile')
        elif photo_err:
            messages.error(request, photo_err)

    return render(request, 'accounts/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })


def forgot_password_student_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')
    return render(request, 'accounts/forgot_password_student.html', {
        'wa_number': WHATSAPP_NUMBER,
    })


def forgot_password_teacher_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')
    return render(request, 'accounts/forgot_password_teacher.html', {
        'wa_number': WHATSAPP_NUMBER,
    })


# Backward-compat alias (URLs still using forgot_password_view kwarg form)
def forgot_password_view(request, role='STUDENT'):
    if role == 'TEACHER':
        return forgot_password_teacher_view(request)
    return forgot_password_student_view(request)


@login_required
def change_password_view(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '').strip()
        new_pw = request.POST.get('new_password', '').strip()
        confirm = request.POST.get('confirm_password', '').strip()

        if not request.user.check_password(current):
            messages.error(request, 'Kata sandi saat ini tidak benar.')
        elif len(new_pw) < 8:
            messages.error(request, 'Kata sandi baru minimal 8 karakter.')
        elif new_pw != confirm:
            messages.error(request, 'Konfirmasi kata sandi tidak cocok.')
        else:
            request.user.set_password(new_pw)
            request.user.save()
            # Re-authenticate so session stays valid after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Kata sandi berhasil diubah!')
            return redirect('accounts:profile')

    return render(request, 'accounts/change_password.html')


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'Anda telah berhasil keluar.')
    return redirect('/')
