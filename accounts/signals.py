from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, StudentProfile, TeacherProfile, AdminProfile, Role


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.role == Role.STUDENT:
        StudentProfile.objects.get_or_create(user=instance)
    elif instance.role == Role.TEACHER:
        TeacherProfile.objects.get_or_create(user=instance)
    elif instance.role == Role.ADMIN:
        AdminProfile.objects.get_or_create(user=instance)
