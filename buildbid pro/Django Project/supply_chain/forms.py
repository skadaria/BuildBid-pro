# supply_chain/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import UserProfile, Project, WorkPackage, Bid, Council
from datetime import date, timedelta


class AdminUserCreationForm(UserCreationForm):
    """Custom form for creating users in admin with profile fields."""
    
    # Use the same choices as defined in UserProfile model
    user_type = forms.ChoiceField(
        choices=UserProfile.USER_TYPES,
        initial='contractor',
        required=True,
        help_text="Select the type of user account"
    )
    company_name = forms.CharField(
        max_length=200, 
        required=False,
        help_text="Company/Organization name (optional for council users)"
    )
    contact_number = forms.CharField(
        max_length=20, 
        required=True,
        help_text="Required: Contact phone number"
    )
    address = forms.CharField(
        max_length=500, 
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Optional: Company/Organization address"
    )
    registration_number = forms.CharField(
        max_length=100, 
        required=False,
        help_text="Optional: Registration/License number"
    )
    council_user = forms.ModelChoiceField(
        queryset=User.objects.filter(userprofile__user_type='council'),
        required=False,
        help_text="Optional: Select a council user to link this user to a council"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove fields from the form that we don't want
        if 'first_name' in self.fields:
            del self.fields['first_name']
        if 'last_name' in self.fields:
            del self.fields['last_name']
        
        # Make email required
        self.fields['email'].required = True
        
        # Check if user_type is council and make company_name optional
        user_type = self.initial.get('user_type') or self.data.get('user_type')
        
        if user_type == 'council':
            # For council users, company name is optional
            self.fields['company_name'].required = False
            self.fields['company_name'].help_text = "Company/Organization name (optional for council)"
            self.fields['company_name'].widget.attrs.update({
                'placeholder': 'Enter company/organization name (optional)'
            })
        else:
            # For other users, company name is required
            self.fields['company_name'].required = True
            self.fields['company_name'].help_text = "Required: Company/Organization name"
            self.fields['company_name'].widget.attrs.update({
                'placeholder': 'Enter company/organization name *'
            })
        
        self.fields['contact_number'].widget.attrs.update({
            'placeholder': 'Enter phone number *'
        })
    
    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name', '').strip()
        user_type = self.cleaned_data.get('user_type')
        
        # Company name is optional for council users
        if user_type == 'council':
            return company_name
        
        # Company name is required for other user types
        if not company_name:
            raise ValidationError("Company/Organization name is required.")
        return company_name
        return company_name
    
    def clean_contact_number(self):
        contact_number = self.cleaned_data.get('contact_number', '').strip()
        if not contact_number:
            raise ValidationError("Contact phone number is required.")
        # Basic phone number validation (optional)
        if len(contact_number) < 7:
            raise ValidationError("Please enter a valid phone number.")
        return contact_number
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Set email if provided
        if self.cleaned_data.get('email'):
            user.email = self.cleaned_data['email']
        
        # Save the user first
        if commit:
            user.save()
            
            # Create or update UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.user_type = self.cleaned_data['user_type']
            profile.company_name = self.cleaned_data['company_name']
            profile.contact_number = self.cleaned_data['contact_number']
            profile.address = self.cleaned_data.get('address', '')
            profile.registration_number = self.cleaned_data.get('registration_number', '')
            profile.save()
            
            # AUTO-CREATE COUNCIL if user_type is council
            if self.cleaned_data['user_type'] == 'council':
                # Use company name as council name
                council_name = self.cleaned_data['company_name']
                
                # Generate slug
                council_slug = slugify(council_name)
                
                # Ensure slug is unique
                counter = 1
                original_slug = council_slug
                while Council.objects.filter(slug=council_slug).exists():
                    council_slug = f"{original_slug}-{counter}"
                    counter += 1
                
                Council.objects.get_or_create(
                    user=user,
                    defaults={
                        'name': council_name,
                        'contact': self.cleaned_data['contact_number'],
                        'contact_email': user.email,
                        'slug': council_slug
                    }
                )
            
            # If user_type is admin, make user staff and superuser
            if self.cleaned_data['user_type'] == 'admin':
                user.is_staff = True
                user.is_superuser = True
                user.save()
        
        return user



class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    # HIDDEN field - always contractor for frontend registration
    user_type = forms.CharField(
        widget=forms.HiddenInput(),
        initial='contractor',
        required=False
    )
    
    company_name = forms.CharField(
        max_length=200, 
        required=True,
        help_text="Required: Your company name"
    )
    
    contact_number = forms.CharField(
        max_length=20, 
        required=True,
        help_text="Required: Contact phone number"
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 
                 'user_type', 'company_name', 'contact_number',
                 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remove the user_type field from visible fields (it's hidden)
        self.fields['user_type'].widget = forms.HiddenInput()
        self.fields['user_type'].initial = 'contractor'
        
        # Add placeholders for required fields
        self.fields['company_name'].widget.attrs.update({
            'placeholder': 'Enter your company name *',
            'required': 'required'
        })
        self.fields['contact_number'].widget.attrs.update({
            'placeholder': 'Enter your phone number *',
            'required': 'required'
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': 'Enter your email *'
        })
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Choose a username *'
        })
        self.fields['first_name'].widget.attrs.update({
            'placeholder': 'Enter first name *'
        })
        self.fields['last_name'].widget.attrs.update({
            'placeholder': 'Enter last name *'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email
    
    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name', '').strip()
        if not company_name:
            raise ValidationError("Company name is required.")
        return company_name
    
    def clean_contact_number(self):
        contact_number = self.cleaned_data.get('contact_number', '').strip()
        if not contact_number:
            raise ValidationError("Contact phone number is required.")
        # Basic phone number validation
        if len(contact_number) < 7:
            raise ValidationError("Please enter a valid phone number (at least 7 digits).")
        return contact_number
    
    def clean(self):
        cleaned_data = super().clean()
        # Force user_type to be 'contractor' for frontend registration
        cleaned_data['user_type'] = 'contractor'
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Profile creation removed from here - will be done in view
        
        return user
class UserProfileForm(forms.ModelForm):
    # Make email part of the profile form
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    # Make these fields required in profile editing too
    company_name = forms.CharField(
        max_length=200, 
        required=True,
        help_text="Required: Company/Organization name"
    )
    contact_number = forms.CharField(
        max_length=20, 
        required=True,
        help_text="Required: Contact phone number"
    )
    
    class Meta:
        model = UserProfile
        fields = ['user_type', 'company_name', 'contact_number', 'address', 'profile_image']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
    
    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name', '').strip()
        if not company_name:
            raise ValidationError("Company/Organization name is required.")
        return company_name
    
    def clean_contact_number(self):
        contact_number = self.cleaned_data.get('contact_number', '').strip()
        if not contact_number:
            raise ValidationError("Contact phone number is required.")
        return contact_number
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update user fields
        if self.user:
            self.user.email = self.cleaned_data['email']
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            if commit:
                self.user.save()
        
        if commit:
            profile.save()
            
            # Update Council if user_type is council
            if profile.user_type == 'council':
                council, created = Council.objects.get_or_create(
                    user=profile.user,
                    defaults={
                        'name': profile.company_name,
                        'contact': profile.contact_number,
                        'contact_email': profile.user.email,
                        'slug': slugify(profile.company_name)
                    }
                )
                if not created:
                    council.name = profile.company_name
                    council.contact = profile.contact_number
                    council.contact_email = profile.user.email
                    council.save()
        
        return profile


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'budget', 'location', 'status', 
                 'start_date', 'end_date', 'blueprint']
        
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Store user as instance variable
        super().__init__(*args, **kwargs)
        
        # Set default dates for new projects
        if not self.instance.pk:
            self.fields['start_date'].initial = date.today()
            self.fields['end_date'].initial = date.today() + timedelta(days=30)
    
    def clean_end_date(self):
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise ValidationError("End date cannot be before start date.")
        return end_date
class AdminProjectForm(forms.ModelForm):
    """Separate form for admin users who need to select council user"""
    class Meta:
        model = Project
        fields = ['council_user', 'title', 'description', 'budget', 'location', 'status', 
                 'start_date', 'end_date', 'blueprint']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default dates for new projects
        if not self.instance.pk:
            self.fields['start_date'].initial = date.today()
            self.fields['end_date'].initial = date.today() + timedelta(days=30)
        
        # Filter to show only council users
        if 'council_user' in self.fields:
            self.fields['council_user'].queryset = User.objects.filter(userprofile__user_type='council')


class WorkPackageForm(forms.ModelForm):
    class Meta:
        model = WorkPackage
        fields = ['title', 'description', 'category', 'estimated_budget', 'deadline']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)  # Get project from kwargs
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Hide the project field - it will be auto-assigned
        self.fields['project'] = forms.ModelChoiceField(
            queryset=Project.objects.none(),
            widget=forms.HiddenInput(),
            required=False
        )
        
        # Set default deadline
        if not self.instance.pk:
            self.fields['deadline'].initial = date.today() + timedelta(days=14)
        
        # If project is provided, set it as initial value
        if self.project:
            self.fields['project'].initial = self.project.id
            self.fields['project'].queryset = Project.objects.filter(id=self.project.id)
    
    def save(self, commit=True):
        work_package = super().save(commit=False)
        
        # Auto-assign project if provided
        if self.project:
            work_package.project = self.project
        
        if commit:
            work_package.save()
        
        return work_package


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount', 'proposed_timeline', 'experience_summary', 'certifications', 'insurance_document']
        widgets = {
            'experience_summary': forms.Textarea(attrs={'rows': 4}),
            'proposed_timeline': forms.NumberInput(attrs={'min': 1, 'max': 365}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.work_package = kwargs.pop('work_package', None)  # Get work package from kwargs
        super().__init__(*args, **kwargs)
        
        
        if 'work_package' in self.fields:
            del self.fields['work_package']
        
        # Set default proposed timeline (7 days)
        if not self.instance.pk:
            self.fields['proposed_timeline'].initial = 7
    
    def save(self, commit=True):
        bid = super().save(commit=False)
        
        # Assign contractor if user is provided
        if self.user:
            bid.contractor = self.user
        
        # Assign work package if provided
        if self.work_package:
            bid.work_package = self.work_package
        
        if commit:
            bid.save()
        
        return bid

class UserEditForm(forms.ModelForm):
    """Form for editing basic user information"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class CouncilSelectionForm(forms.Form):
    """Form for selecting a council (e.g., when creating a project)"""
    council = forms.ModelChoiceField(
        queryset=Council.objects.all(),
        empty_label="Select a council",
        required=True,
        label="Council"
    )


class ProfileEditForm(forms.ModelForm):
    """Form for users to edit their profile information"""
    email = forms.EmailField(required=True, label="Email Address")
    first_name = forms.CharField(max_length=30, required=False, label="First Name")
    last_name = forms.CharField(max_length=30, required=False, label="Last Name")
    
    class Meta:
        model = UserProfile
        fields = ['company_name', 'contact_number', 'address', 'registration_number', 'profile_image']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update user email and name
        if self.user:
            self.user.email = self.cleaned_data.get('email', self.user.email)
            self.user.first_name = self.cleaned_data.get('first_name', self.user.first_name)
            self.user.last_name = self.cleaned_data.get('last_name', self.user.last_name)
            
            if commit:
                self.user.save()
        
        if commit:
            profile.save()
        
        return profile


class PasswordChangeForm(forms.Form):
    """Form for users to change their password"""
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if self.user and not self.user.check_password(old_password):
            raise ValidationError("Your old password was entered incorrectly.")
        return old_password
    
    def clean_new_password2(self):
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise ValidationError("The two password fields didn't match.")
            if len(new_password1) < 8:
                raise ValidationError("Your password must be at least 8 characters long.")
        
        return new_password2
