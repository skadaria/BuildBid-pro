# supply_chain/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid
from datetime import date, timedelta


# models.py - UserProfile should NOT have created_at
class UserProfile(models.Model):
    USER_TYPES = [
        ('admin', 'Admin'),
        ('council', 'Council'),
        ('contractor', 'Contractor'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='contractor')
    company_name = models.CharField(max_length=200, blank=True, default='')
    contact_number = models.CharField(max_length=20, blank=True, default='')
    address = models.TextField(blank=True, default='')
    registration_number = models.CharField(max_length=100, blank=True, default='')
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
   
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} ({self.get_user_type_display()})"


class Council(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    contact_email = models.EmailField()
    slug = models.SlugField(max_length=100, unique=True)
    address = models.TextField(default='Address not specified')
    website = models.URLField(blank=True, default='')
    logo = models.ImageField(upload_to='council_logos/', blank=True, null=True)
    
    # ADD THIS LINE to link council to a user
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='council_profile'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} Council'


class Project(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('completed', 'Completed'),
    ]
    
    council_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, limit_choices_to={'userprofile__user_type': 'council'}, related_name='projects_managed')
    title = models.CharField(max_length=200, default='New Project')
    description = models.TextField(default='Project description')
    budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    location = models.CharField(max_length=200, default='Location not specified')
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=date.today() + timedelta(days=30))  # 30 days from now
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    blueprint = models.FileField(upload_to='blueprints/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


class WorkPackage(models.Model):
    CATEGORIES = [
        ('electrician','Electrician'),
        ('plumber','Plumber'),
        ('concrete','Concrete'),
        ('finishing','Finishing'),
        ('furnishing','Furnishing'),
        ('technician','Technician'),
        ('other', 'Other'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='work_packages')
    title = models.CharField(max_length=200, default='New Work Package')
    description = models.TextField(default='Work package description')
    category = models.CharField(max_length=50, choices=CATEGORIES, default='other')
    estimated_budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    deadline = models.DateField(default=date.today() + timedelta(days=14))  # 14 days from now
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['deadline']
    
    def __str__(self):
        return f'{self.title} - {self.get_category_display()}'


class Bid(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    bid_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    work_package = models.ForeignKey(WorkPackage, on_delete=models.CASCADE, related_name='bids')
    contractor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids_submitted')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    proposed_timeline = models.IntegerField(help_text="Timeline in days", default=7)
    experience_summary = models.TextField(default='Experience summary')
    certifications = models.FileField(upload_to='bid_certifications/', blank=True, null=True)
    insurance_document = models.FileField(upload_to='bid_insurance/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['amount']
        unique_together = ['work_package', 'contractor']
    
    def __str__(self):
        return f'Bid #{self.bid_id.hex[:8]} - {self.work_package.title}'


class ContractorTeam(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='team')
    team_name = models.CharField(max_length=200, default='Project Team')
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'Team for {self.project.title}'
    
    class Meta:
        verbose_name = 'Project Team'
        verbose_name_plural = 'Project Teams'


class TeamAssignment(models.Model):
    team = models.ForeignKey(ContractorTeam, on_delete=models.CASCADE, related_name='assignments')
    contractor = models.ForeignKey(User, on_delete=models.CASCADE)
    work_package = models.ForeignKey(WorkPackage, on_delete=models.CASCADE)
    bid = models.ForeignKey(Bid, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')
    
    class Meta:
        unique_together = ['team', 'work_package']
    
    def __str__(self):
        return f'{self.contractor.username} - {self.work_package.title}'


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('blueprint', 'Blueprint'),
        ('contract', 'Contract'),
        ('certificate', 'Certificate'),
        ('insurance', 'Insurance'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=200, default='Document')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    file = models.FileField(upload_to='project_documents/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    work_package = models.ForeignKey(WorkPackage, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    
    def __str__(self):
        return self.title


class ProjectReport(models.Model):
    """
    Comprehensive project report model tracking:
    - Project Overview (budget, timeline, status)
    - Financial Report (costs, variances)
    - Bidding Analytics (bid counts, acceptance rates)
    - Progress/Timeline (milestones, completion %)
    - Contractor Performance (ratings, reliability)
    - Work Package Status (individual package progress)
    """
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='report')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Project Overview Data
    total_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_spending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    completion_percentage = models.IntegerField(default=0)  # 0-100
    
    # Financial Report Data
    budget_variance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # positive = under budget
    total_bids_received = models.IntegerField(default=0)
    total_bids_accepted = models.IntegerField(default=0)
    average_bid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Bidding Analytics
    bid_acceptance_rate = models.FloatField(default=0)  # percentage
    top_performing_contractor = models.CharField(max_length=200, blank=True)
    
    # Timeline Data
    days_until_deadline = models.IntegerField(default=0)
    is_on_schedule = models.BooleanField(default=True)
    
    # Summary Statistics
    total_work_packages = models.IntegerField(default=0)
    completed_packages = models.IntegerField(default=0)
    in_progress_packages = models.IntegerField(default=0)
    pending_packages = models.IntegerField(default=0)
    
    # PDF/Export Data
    report_data = models.JSONField(default=dict)  # Store detailed JSON for export
    
    class Meta:
        verbose_name = 'Project Report'
        verbose_name_plural = 'Project Reports'
    
    def __str__(self):
        return f'Report for {self.project.title} - {self.generated_at.strftime("%Y-%m-%d")}'