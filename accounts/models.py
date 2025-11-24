from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model for team members."""
    display_name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.display_name or self.username
