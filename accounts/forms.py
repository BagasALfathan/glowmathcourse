from django import forms
from django.contrib.auth.forms import UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML

from .models import (
    User, Level, Education, Role, ApprovalStatus,
    StudentProfile, TeacherProfile, AdminProfile,
)


# ── Auth forms ────────────────────────────────────────────────────────────────

class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'contoh@email.com', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Kata Sandi',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('email'),
            Field('password'),
        )


class StudentRegistrationForm(UserCreationForm):
    level = forms.ChoiceField(choices=Level.choices, label='Jenjang')
    school_name = forms.CharField(max_length=200, label='Nama Sekolah', required=False)
    school_grade = forms.IntegerField(
        label='Kelas (1–12)', min_value=1, max_value=12, required=False
    )
    phone = forms.CharField(max_length=20, label='No. HP Siswa', required=False)
    parent_name = forms.CharField(max_length=150, label='Nama Orang Tua', required=False)
    parent_phone = forms.CharField(max_length=20, label='No. HP Orang Tua', required=False)
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), label='Alamat', required=False
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['first_name'].label = 'Nama Depan'
        self.fields['last_name'].label = 'Nama Belakang'
        self.fields['username'].label = 'Username'
        self.fields['email'].label = 'Email'
        self.fields['password1'].label = 'Kata Sandi'
        self.fields['password2'].label = 'Konfirmasi Kata Sandi'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('<p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Informasi Akun</p>'),
            Row(
                Column('first_name', css_class='md:col-span-1'),
                Column('last_name', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('username', css_class='md:col-span-1'),
                Column('email', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('password1', css_class='md:col-span-1'),
                Column('password2', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            HTML('<p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 mt-6">Informasi Profil</p>'),
            Row(
                Column('level', css_class='md:col-span-1'),
                Column('school_grade', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('school_name'),
            Row(
                Column('phone', css_class='md:col-span-1'),
                Column('parent_name', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('parent_phone'),
            Field('address'),
        )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if User.objects.filter(email__iexact=email, is_deleted=False).exists():
            raise forms.ValidationError('Email sudah terdaftar.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username, is_deleted=False).exists():
            raise forms.ValidationError('Username sudah terdaftar.')
        return username


class TeacherRegistrationForm(UserCreationForm):
    education = forms.ChoiceField(
        choices=[('', '---------')] + list(Education.choices),
        label='Pendidikan Terakhir',
        required=False,
    )
    specialization = forms.CharField(
        max_length=200, label='Spesialisasi / Mata Pelajaran', required=False
    )
    bio = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), label='Bio Singkat', required=False
    )
    experience_years = forms.IntegerField(
        label='Pengalaman Mengajar (tahun)', min_value=0, initial=0, required=False
    )
    phone = forms.CharField(max_length=20, label='No. HP', required=False)
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), label='Alamat', required=False
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['first_name'].label = 'Nama Depan'
        self.fields['last_name'].label = 'Nama Belakang'
        self.fields['username'].label = 'Username'
        self.fields['email'].label = 'Email'
        self.fields['password1'].label = 'Kata Sandi'
        self.fields['password2'].label = 'Konfirmasi Kata Sandi'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('<p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Informasi Akun</p>'),
            Row(
                Column('first_name', css_class='md:col-span-1'),
                Column('last_name', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('username', css_class='md:col-span-1'),
                Column('email', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Row(
                Column('password1', css_class='md:col-span-1'),
                Column('password2', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            HTML('<p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 mt-6">Informasi Profil</p>'),
            Row(
                Column('education', css_class='md:col-span-1'),
                Column('experience_years', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('specialization'),
            Field('bio'),
            Field('phone'),
            Field('address'),
        )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if User.objects.filter(email__iexact=email, is_deleted=False).exists():
            raise forms.ValidationError('Email sudah terdaftar.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username, is_deleted=False).exists():
            raise forms.ValidationError('Username sudah terdaftar.')
        return username


# ── Profile edit forms ────────────────────────────────────────────────────────

class ProfileUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['first_name'].label = 'Nama Depan'
        self.fields['last_name'].label = 'Nama Belakang'
        self.fields['email'].label = 'Email'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='md:col-span-1'),
                Column('last_name', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('email'),
        )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        qs = User.objects.filter(email__iexact=email, is_deleted=False)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Email sudah digunakan akun lain.')
        return email


class StudentProfileEditForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['level', 'school_name', 'school_grade', 'phone',
                  'parent_name', 'parent_phone', 'address']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['level'].label = 'Jenjang'
        self.fields['level'].required = True
        self.fields['school_name'].label = 'Nama Sekolah'
        self.fields['school_grade'].label = 'Kelas (1–12)'
        self.fields['phone'].label = 'No. HP Siswa'
        self.fields['parent_name'].label = 'Nama Orang Tua'
        self.fields['parent_phone'].label = 'No. HP Orang Tua'
        self.fields['address'].label = 'Alamat'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('level', css_class='md:col-span-1'),
                Column('school_grade', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('school_name'),
            Row(
                Column('phone', css_class='md:col-span-1'),
                Column('parent_name', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('parent_phone'),
            Field('address'),
        )


class TeacherProfileEditForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['education', 'specialization', 'bio', 'experience_years', 'phone', 'address']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['education'].label = 'Pendidikan Terakhir'
        self.fields['specialization'].label = 'Spesialisasi / Mata Pelajaran'
        self.fields['bio'].label = 'Bio Singkat'
        self.fields['experience_years'].label = 'Pengalaman Mengajar (tahun)'
        self.fields['phone'].label = 'No. HP'
        self.fields['address'].label = 'Alamat'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('education', css_class='md:col-span-1'),
                Column('experience_years', css_class='md:col-span-1'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4',
            ),
            Field('specialization'),
            Field('bio'),
            Field('phone'),
            Field('address'),
        )


class AdminProfileEditForm(forms.ModelForm):
    class Meta:
        model = AdminProfile
        fields = ['phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].label = 'No. HP'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(Field('phone'))
