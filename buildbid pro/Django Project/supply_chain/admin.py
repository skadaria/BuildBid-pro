# supply_chain/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.urls import reverse
from .models import (
    UserProfile, Council, Project, WorkPackage, 
    Bid, ContractorTeam, Document, ProjectReport
)
from .forms import AdminUserCreationForm

# Unregister Group - not used in this application
admin.site.unregister(Group)

# ========== CUSTOM ADMIN SITE ==========
class CustomAdminSite(admin.AdminSite):
    """Custom admin site with improved filter display"""
    site_header = "BuildBid Pro Administration"
    site_title = "BuildBid Pro Admin"
    
    def each_context(self, request):
        context = super().each_context(request)
        # Add custom CSS for sidebar filters
        context['extra_css'] = ['admin/css/filters_sidebar.css']
        return context

# Replace default admin site with custom one
admin.site.__class__ = CustomAdminSite

# ========== USER ADMIN CUSTOMIZATION ==========
class CustomUserAdmin(UserAdmin):
    add_form = AdminUserCreationForm  # Use your custom form for ADDING users
    
    # FIXED: Add user_type to list_display
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_user_type', 'get_company_name', 'is_staff', 'is_active')
    list_filter = ('userprofile__user_type', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'userprofile__company_name')
    
    # Fields to show in "Add User" form (using AdminUserCreationForm)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 
                      'user_type', 'company_name', 'contact_number', 'address', 
                      'registration_number'),
        }),
    )
    
    # Fields to show in "Change User" form (keep original)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 
                                   'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    def get_user_type(self, obj):
        """Helper method to display user_type in list view"""
        if hasattr(obj, 'userprofile'):
            return obj.userprofile.get_user_type_display()
        return "No profile"
    get_user_type.short_description = 'User Type'
    
    def get_company_name(self, obj):
        """Helper method to display company_name in list view"""
        if hasattr(obj, 'userprofile') and obj.userprofile.company_name:
            return obj.userprofile.company_name
        return "-"
    get_company_name.short_description = 'Company'
    
    # Override get_form to handle the custom form properly
    def get_form(self, request, obj=None, **kwargs):
        """
        Use custom form for user creation, and default form for editing.
        """
        defaults = {}
        if obj is None:  # Creating a new user
            defaults['form'] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)
    
    def save_model(self, request, obj, form, change):
        """Override save_model to handle council_user assignment"""
        super().save_model(request, obj, form, change)
        
        # Get user type and council user from form
        user_type = form.cleaned_data.get('user_type')
        council_user = form.cleaned_data.get('council_user')
        
        # Update or create UserProfile
        if hasattr(obj, 'userprofile'):
            profile = obj.userprofile
        else:
            profile = UserProfile(user=obj)
            
        profile.user_type = user_type
        profile.company_name = form.cleaned_data.get('company_name', '')
        profile.contact_number = form.cleaned_data.get('contact_number', '')
        profile.address = form.cleaned_data.get('address', '')
        profile.registration_number = form.cleaned_data.get('registration_number', '')
        profile.save()
        
        # Handle council assignment if council user was selected
        if council_user:
            council = Council.objects.filter(user=council_user).first()
            if council:
                council.user = obj
                council.save()

# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ========== OTHER MODEL ADMIN REGISTRATIONS ==========

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'council_user', 'status', 'budget', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'council_user', 'created_at')
    search_fields = ('title', 'description', 'location', 'council_user__username', 'council_user__userprofile__company_name')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('status',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('council_user', 'title', 'description', 'budget', 'location')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'status')
        }),
        ('Files', {
            'fields': ('blueprint',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WorkPackage)
class WorkPackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'category', 'estimated_budget', 'deadline', 'is_active')
    list_filter = ('category', 'is_active', 'deadline', 'created_at')
    search_fields = ('title', 'description', 'project__title')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('bid_id_short', 'work_package', 'contractor', 'amount', 'status', 'submitted_at')
    list_filter = ('status', 'submitted_at', 'work_package__category')
    search_fields = ('bid_id', 'contractor__username', 'work_package__title')
    readonly_fields = ('bid_id', 'submitted_at', 'updated_at')
    list_editable = ('status',)
    
    def bid_id_short(self, obj):
        return str(obj.bid_id)[:8]
    bid_id_short.short_description = 'Bid ID'


@admin.register(ContractorTeam)
class ContractorTeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'project', 'get_project_council', 'get_team_size', 'created_by', 'created_at')
    list_filter = ('created_at', 'project__created_by')
    search_fields = ('team_name', 'project__title', 'created_by__username', 'project__created_by__username')
    readonly_fields = ('created_at', 'get_accepted_contractors_display')
    
    fieldsets = (
        ('Team Information', {
            'fields': ('team_name', 'project', 'created_by', 'created_at')
        }),
        ('Accepted Contractors', {
            'fields': ('get_accepted_contractors_display',),
            'description': 'Shows all contractors whose bids have been approved for this project'
        }),
    )
    
    def get_queryset(self, request):
        """Get all contractor teams and create them if they don't exist"""
        from .models import Project
        
        # Get all existing teams
        teams = super().get_queryset(request)
        
        # Create teams for projects that don't have them yet
        for project in Project.objects.all():
            ContractorTeam.objects.get_or_create(
                project=project,
                defaults={
                    'team_name': f"Team for {project.title}",
                    'created_by': project.created_by
                }
            )
        
        # Return all teams (now including newly created ones)
        return super().get_queryset(request)
    
    def get_project_council(self, obj):
        """Display the council that created the project"""
        if obj.project and obj.project.created_by:
            return obj.project.created_by.username
        return "Unknown"
    get_project_council.short_description = 'Council'
    
    def get_team_size(self, obj):
        """Display number of accepted contractors"""
        from .models import Bid
        if obj.project:
            count = Bid.objects.filter(
                work_package__project=obj.project,
                status='approved'
            ).count()
            return f"{count} contractor{'s' if count != 1 else ''}"
        return "No members"
    get_team_size.short_description = 'Team Size'
    
    def get_accepted_contractors_display(self, obj):
        """Display list of accepted contractors with their details"""
        from .models import Bid
        
        if not obj.project:
            return "No project assigned"
        
        contractors = []
        for work_package in obj.project.work_packages.all():
            accepted_bids = Bid.objects.filter(
                work_package=work_package,
                status='approved'
            ).select_related('contractor', 'contractor__userprofile')
            
            for bid in accepted_bids:
                contractor = bid.contractor
                profile = contractor.userprofile if hasattr(contractor, 'userprofile') else None
                contractors.append({
                    'name': contractor.username,
                    'company': profile.company_name if profile else 'N/A',
                    'package': work_package.title,
                    'amount': bid.amount,
                    'contact': profile.contact_number if profile else 'N/A'
                })
        
        if not contractors:
            return "No accepted contractors yet"
        
        # Format as readable text
        display_text = "\n\n".join([
            f"📌 Package: {c['package']}\n"
            f"   Contractor: {c['name']}\n"
            f"   Company: {c['company']}\n"
            f"   Bid Amount: ${c['amount']}\n"
            f"   Contact: {c['contact']}"
            for c in contractors
        ])
        
        return display_text
    get_accepted_contractors_display.short_description = 'Accepted Contractors'
    
    def has_add_permission(self, request):
        """Disable manual team creation"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable team deletion"""
        return False



@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_type', 'uploaded_by', 'get_uploader_type', 'uploaded_at', 'file_link')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('title', 'uploaded_by__username')
    readonly_fields = ('uploaded_at',)
    
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)
        return "No file"
    file_link.short_description = 'File'
    
    def get_uploader_type(self, obj):
        """Show the user type of the uploader"""
        if hasattr(obj.uploaded_by, 'userprofile'):
            return obj.uploaded_by.userprofile.get_user_type_display()
        return "Unknown"
    get_uploader_type.short_description = 'Uploader Type'
    
    def changelist_view(self, request, extra_context=None):
        """Override to include all documents: regular, bid documents, and blueprints"""
        from .models import Bid, Project
        
        response = super().changelist_view(request, extra_context)
        
        # Get all documents and add them to result list
        if hasattr(response, 'context_data') and 'cl' in response.context_data:
            cl = response.context_data['cl']
            
            # Create virtual document objects from all sources
            virtual_docs = []
            
            # 1. Add bid documents (certifications and insurance)
            for bid in Bid.objects.select_related('contractor', 'contractor__userprofile').all():
                if bid.certifications:
                    doc = Document()
                    doc.id = f"bid_{bid.bid_id}_cert"
                    doc.title = f"Bid {str(bid.bid_id)[:8]} - Certification"
                    doc.document_type = 'certificate'
                    doc.file = bid.certifications
                    doc.uploaded_by = bid.contractor
                    doc.uploaded_at = bid.submitted_at
                    virtual_docs.append(doc)
                
                if bid.insurance_document:
                    doc = Document()
                    doc.id = f"bid_{bid.bid_id}_ins"
                    doc.title = f"Bid {str(bid.bid_id)[:8]} - Insurance"
                    doc.document_type = 'insurance'
                    doc.file = bid.insurance_document
                    doc.uploaded_by = bid.contractor
                    doc.uploaded_at = bid.submitted_at
                    virtual_docs.append(doc)
            
            # 2. Add project blueprints
            for project in Project.objects.select_related('council_user', 'council_user__userprofile').all():
                if project.blueprint:
                    doc = Document()
                    doc.id = f"project_{project.id}_blueprint"
                    doc.title = f"Project: {project.title} - Blueprint"
                    doc.document_type = 'blueprint'
                    doc.file = project.blueprint
                    doc.uploaded_by = project.council_user if project.council_user else project.created_by
                    doc.uploaded_at = project.created_at
                    virtual_docs.append(doc)
            
            # Add virtual documents to the result list
            original_result_list = list(cl.result_list) if hasattr(cl, 'result_list') else []
            cl.result_list = original_result_list + virtual_docs
            
            # Update result count
            response.context_data['cl'].result_count = len(cl.result_list)
            response.context_data['full_result_count'] = len(cl.result_list)
        
        return response



@admin.register(ProjectReport)
class ProjectReportAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'generated_at', 'completion_percentage', 
        'total_budget', 'actual_spending', 'budget_variance', 
        'view_report_link', 'download_pdf_link'
    )
    list_filter = ('generated_at', 'project__status')
    search_fields = ('project__title', 'generated_by__username')
    readonly_fields = (
        'project', 'generated_by', 'generated_at', 'updated_at',
        'total_budget', 'actual_spending', 'completion_percentage',
        'budget_variance', 'total_bids_received', 'total_bids_accepted',
        'average_bid_amount', 'bid_acceptance_rate', 'top_performing_contractor',
        'days_until_deadline', 'is_on_schedule', 'total_work_packages',
        'completed_packages', 'in_progress_packages', 'pending_packages',
        'report_summary_display'
    )
    
    fieldsets = (
        ('Project Information', {
            'fields': ('project', 'generated_by', 'generated_at', 'updated_at')
        }),
        ('Project Overview', {
            'fields': ('total_budget', 'actual_spending', 'completion_percentage', 'budget_variance')
        }),
        ('Bidding Analytics', {
            'fields': ('total_bids_received', 'total_bids_accepted', 'average_bid_amount', 
                      'bid_acceptance_rate', 'top_performing_contractor')
        }),
        ('Timeline & Schedule', {
            'fields': ('days_until_deadline', 'is_on_schedule')
        }),
        ('Work Package Status', {
            'fields': ('total_work_packages', 'completed_packages', 'in_progress_packages', 'pending_packages')
        }),
        ('Report Summary', {
            'fields': ('report_summary_display',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Auto-generate reports for all projects that don't have one"""
        from .models import Project
        
        # Create reports for all projects that don't have one yet
        for project in Project.objects.all():
            ProjectReport.objects.get_or_create(
                project=project,
                defaults={
                    'generated_by': project.created_by
                }
            )
        
        return super().get_queryset(request)
    
    def view_report_link(self, obj):
        """Link to view report in HTML format"""
        url = reverse('view_project_report', args=[obj.project.id])
        return format_html('<a class="button" href="{}">View Report</a>', url)
    view_report_link.short_description = 'View'
    
    def download_pdf_link(self, obj):
        """Link to download report as PDF"""
        url = reverse('download_project_report_pdf', args=[obj.project.id])
        return format_html('<a class="button" href="{}">Download PDF</a>', url)
    download_pdf_link.short_description = 'Download'
    
    def report_summary_display(self, obj):
        """Display report summary"""
        if obj.report_data:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{}</pre>',
                str(obj.report_data)
            )
        return "No detailed data available"
    report_summary_display.short_description = 'Detailed Report Data'
    
    def has_add_permission(self, request):
        """Reports are auto-generated, disable manual creation"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion of reports"""
        return True