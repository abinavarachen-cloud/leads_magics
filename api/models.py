# models.py
from django.db import models

class Company(models.Model):
    # Company Information
    company_name = models.CharField(max_length=100)
    domain = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=150, null=True, blank=True)
    industry = models.CharField(max_length=100, null=True, blank=True)
    company_email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Companies"
    
    def __str__(self):
        return self.company_name

class Client(models.Model):
    NURTURING_STAGES = [
        ('hot', 'Hot - Highly Interested'),
        ('warm', 'Warm - Moderately Interested'),
        ('cold', 'Cold - Not Interested'),
    ]
    STATUS_CHOICES = [
        ('lost', 'Lost'),
        ('won', 'Won'),
    ]
    
    # Foreign Key to Company
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='clients',
        null=True, 
        blank=True
    )
    
    # Contact Information
    client = models.CharField(max_length=100, null=True, blank=True)
    job_role = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    social_media = models.JSONField(null=True, blank=True, default=dict)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        null=True,
        blank=True
    )
    remarks = models.TextField(null=True, blank=True)
    lead_owner = models.CharField(max_length=100, null=True, blank=True)
    nurturing_stage = models.CharField(
        max_length=10, 
        choices=NURTURING_STAGES, 
        default='warm',
        null=True, 
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.client or f"Client {self.id}"


class Folder(models.Model):
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']   
        verbose_name = "Folder"
        verbose_name_plural = "Folders"

    def __str__(self):
        return self.name
    
class List(models.Model):
    name = models.CharField(max_length=100)
    folder = models.ForeignKey(
        Folder,
        related_name='lists',
        on_delete=models.SET_NULL,  # or CASCADE if you want lists deleted with folder
        null=True,
        blank=True
    )
    clients = models.ManyToManyField(Client, related_name='lists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def count(self):
        """Dynamic count of clients in the list"""
        return self.clients.count()
