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
from .models import User, Role, ApprovalStatus, StudentProfile, TeacherProfile, AdminProfile

WHATSAPP_NUMBER = '6281234567890'


def _build_wa_url(full_name, role_display):
    text = (
        f'Halo admin, saya baru mendaftar di GlowMathCourse '
        f'dengan nama {full_name} sebagai {role_display}. Mohon persetujuan.'
    )
    return f'https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(text)}'


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    form = LoginForm(request.POST or None)
    context = {'form': form}

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        try:
            user_obj = User.objects.get(email=email, is_deleted=False)
            if user_obj.check_password(password):
                if user_obj.approval_status == ApprovalStatus.PENDING:
                    request.session['waiting_name'] = (
                        user_obj.get_full_name() or user_obj.username
                    )
                    request.session['waiting_role'] = user_obj.get_role_display()
                    return redirect('accounts:waiting')
                elif user_obj.approval_status == ApprovalStatus.REJECTED:
                    context['rejected_wa_url'] = _build_wa_url(
                        user_obj.get_full_name() or user_obj.username,
                        user_obj.get_role_display(),
                    )
                else:
                    # APPROVED — authenticate normally (is_active=True)
                    user = authenticate(
                        request,
                        username=user_obj.username,
                        password=password,
                    )
                    if user:
                        login(request, user)
                        next_url = request.GET.get('next', '/dashboard/')
                        return redirect(next_url)
                    else:
                        form.add_error(None, 'Email atau kata sandi salah.')
            else:
                form.add_error(None, 'Email atau kata sandi salah.')
        except User.DoesNotExist:
            form.add_error(None, 'Email atau kata sandi salah.')
        except User.MultipleObjectsReturned:
            form.add_error(
                None,
                'Terdapat lebih dari satu akun dengan email ini. Hubungi admin.',
            )

    return render(request, 'accounts/login.html', context)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')
    return render(request, 'accounts/register.html')


def register_student_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    form = StudentRegistrationForm(request.POST or None)
    context = {'form': form}

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data.get('email', '')
        username = form.cleaned_data.get('username', '')

        # Block re-registration
        existing = User.objects.filter(
            email=email, is_deleted=False
        ).exclude(approval_status=ApprovalStatus.APPROVED).first()
        if not existing and username:
            existing = User.objects.filter(
                username=username, is_deleted=False
            ).exclude(approval_status=ApprovalStatus.APPROVED).first()

        if existing:
            if existing.approval_status == ApprovalStatus.PENDING:
                request.session['waiting_name'] = (
                    existing.get_full_name() or existing.username
                )
                request.session['waiting_role'] = existing.get_role_display()
                messages.info(
                    request,
                    'Anda sudah terdaftar dan sedang menunggu persetujuan admin.',
                )
                return redirect('accounts:waiting')
            else:  # REJECTED
                context['rejected_wa_url'] = _build_wa_url(
                    existing.get_full_name() or existing.username,
                    existing.get_role_display(),
                )
                return render(request, 'accounts/register_student.html', context)

        user = form.save(commit=False)
        user.role = Role.STUDENT
        user.is_active = False
        user.approval_status = ApprovalStatus.PENDING
        user.save()

        profile = user.student_profile
        profile.level = form.cleaned_data['level']
        profile.school_name = form.cleaned_data.get('school_name', '')
        profile.school_grade = form.cleaned_data.get('school_grade')
        profile.phone = form.cleaned_data.get('phone', '')
        profile.parent_name = form.cleaned_data.get('parent_name', '')
        profile.parent_phone = form.cleaned_data.get('parent_phone', '')
        profile.address = form.cleaned_data.get('address', '')
        profile.save()

        request.session['waiting_name'] = user.get_full_name() or user.username
        request.session['waiting_role'] = user.get_role_display()
        return redirect('accounts:waiting')

    return render(request, 'accounts/register_student.html', context)


def register_teacher_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    form = TeacherRegistrationForm(request.POST or None)
    context = {'form': form}

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data.get('email', '')
        username = form.cleaned_data.get('username', '')

        # Block re-registration
        existing = User.objects.filter(
            email=email, is_deleted=False
        ).exclude(approval_status=ApprovalStatus.APPROVED).first()
        if not existing and username:
            existing = User.objects.filter(
                username=username, is_deleted=False
            ).exclude(approval_status=ApprovalStatus.APPROVED).first()

        if existing:
            if existing.approval_status == ApprovalStatus.PENDING:
                request.session['waiting_name'] = (
                    existing.get_full_name() or existing.username
                )
                request.session['waiting_role'] = existing.get_role_display()
                messages.info(
                    request,
                    'Anda sudah terdaftar dan sedang menunggu persetujuan admin.',
                )
                return redirect('accounts:waiting')
            else:  # REJECTED
                context['rejected_wa_url'] = _build_wa_url(
                    existing.get_full_name() or existing.username,
                    existing.get_role_display(),
                )
                return render(request, 'accounts/register_teacher.html', context)

        user = form.save(commit=False)
        user.role = Role.TEACHER
        user.is_active = False
        user.approval_status = ApprovalStatus.PENDING
        user.save()

        profile = user.teacher_profile
        profile.education = form.cleaned_data.get('education', '')
        profile.specialization = form.cleaned_data.get('specialization', '')
        profile.bio = form.cleaned_data.get('bio', '')
        profile.experience_years = form.cleaned_data.get('experience_years') or 0
        profile.phone = form.cleaned_data.get('phone', '')
        profile.address = form.cleaned_data.get('address', '')
        profile.save()

        request.session['waiting_name'] = user.get_full_name() or user.username
        request.session['waiting_role'] = user.get_role_display()
        return redirect('accounts:waiting')

    return render(request, 'accounts/register_teacher.html', context)


def waiting_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:router')

    name = request.session.get('waiting_name', '')
    role = request.session.get('waiting_role', '')
    wa_url = _build_wa_url(name, role) if name else f'https://wa.me/{WHATSAPP_NUMBER}'

    return render(request, 'accounts/waiting.html', {
        'waiting_name': name,
        'waiting_role': role,
        'wa_url': wa_url,
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
        if user_valid and profile_valid:
            user_form.save()
            if profile_form:
                profile_form.save()
            messages.success(request, 'Profil berhasil diperbarui!')
            return redirect('accounts:profile')

    return render(request, 'accounts/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'Anda telah berhasil keluar.')
    return redirect('accounts:login')
