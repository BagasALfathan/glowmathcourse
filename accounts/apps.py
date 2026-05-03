from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        import accounts.signals  # noqa: F401
        _patch_form_messages()


def _patch_form_messages():
    from django import forms

    forms.Field.default_error_messages['required'] = 'Field ini wajib diisi.'

    forms.CharField.default_error_messages.update({
        'max_length': 'Terlalu panjang (maks. %(limit_value)d karakter).',
        'min_length': 'Terlalu pendek (min. %(limit_value)d karakter).',
    })

    forms.EmailField.default_error_messages['invalid'] = 'Email tidak valid.'

    forms.IntegerField.default_error_messages.update({
        'invalid': 'Masukkan angka yang valid.',
        'max_value': 'Pastikan nilai ini tidak lebih dari %(limit_value)s.',
        'min_value': 'Pastikan nilai ini tidak kurang dari %(limit_value)s.',
    })

    forms.DecimalField.default_error_messages.update({
        'invalid': 'Masukkan angka desimal yang valid.',
        'max_value': 'Pastikan nilai ini tidak lebih dari %(limit_value)s.',
        'min_value': 'Pastikan nilai ini tidak kurang dari %(limit_value)s.',
    })

    forms.DateField.default_error_messages['invalid'] = 'Masukkan tanggal yang valid (YYYY-MM-DD).'
    forms.TimeField.default_error_messages['invalid'] = 'Masukkan waktu yang valid (HH:MM).'

    forms.ChoiceField.default_error_messages['invalid_choice'] = 'Pilihan tidak valid.'

    # Password length validator message
    from django.contrib.auth.password_validation import MinimumLengthValidator
    MinimumLengthValidator.get_help_text = lambda self: (  # type: ignore[method-assign]
        f'Password minimal {self.min_length} karakter.'
    )
