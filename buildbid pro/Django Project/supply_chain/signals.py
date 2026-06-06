# supply_chain/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Create UserProfile when a new User is created.
    Update it when User is saved.
    """
    if created:
        # Determine user_type based on user permissions
        user_type = 'contractor'  # default
        if instance.is_superuser:
            user_type = 'admin'
        
        UserProfile.objects.create(
            user=instance,
            user_type=user_type
        )
    else:
        # Update existing profile for superusers
        try:
            profile = instance.userprofile
            if instance.is_superuser and profile.user_type != 'admin':
                profile.user_type = 'admin'
                profile.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance, user_type='contractor')