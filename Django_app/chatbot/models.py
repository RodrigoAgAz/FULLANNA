# Models for your app
# chatbot/models.py
from django.db import models

class Patient(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    discharge_date = models.DateTimeField(null=True, blank=True)  # New field

    def __str__(self):
        return f"{self.name} ({self.email})"