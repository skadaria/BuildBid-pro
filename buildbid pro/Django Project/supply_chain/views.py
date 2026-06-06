# supply_chain/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Count
from datetime import date, timedelta
from django.utils.text import slugify


from .models import (
    UserProfile, Council, Project, WorkPackage, 
    Bid, ContractorTeam, TeamAssignment, ProjectReport
)
from .forms import (
    UserRegistrationForm, UserProfileForm, ProjectForm, 
    WorkPackageForm, BidForm, ProfileEditForm, PasswordChangeForm
)
from .report_utils import generate_project_report, generate_pdf_report


def home(request):
    """Home page with project statistics and featured projects."""
    total_projects = Project.objects.filter(status='published').count()
    active_packages = WorkPackage.objects.filter(is_active=True).count()
    total_contractors = UserProfile.objects.filter(user_type='contractor').count()
    completed_projects = Project.objects.filter(status='completed').count()
    
    featured_projects = Project.objects.filter(status='published').order_by('-created_at')[:3]
    
    context = {
        'total_projects': total_projects,
        'active_packages': active_packages,
        'total_contractors': total_contractors,
        'completed_projects': completed_projects,
        'featured_projects': featured_projects,
    }
    
    return render(request, 'supply_chain/home.html', context)


def project_list(request):
    """List all published projects with filtering."""
    # If user is a council, only show their own projects
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.user_type == 'council':
                projects = Project.objects.filter(
                    created_by=request.user,
                    status='published'
                ).order_by('-created_at')
            else:
                # For contractors and others, show all published projects
                projects = Project.objects.filter(status='published').order_by('-created_at')
        except UserProfile.DoesNotExist:
            # If profile doesn't exist, show all published projects
            projects = Project.objects.filter(status='published').order_by('-created_at')
    else:
        # For non-authenticated users, show all published projects
        projects = Project.objects.filter(status='published').order_by('-created_at')
    
    # Filtering
    category = request.GET.get('category')
    location = request.GET.get('location')
    budget_min = request.GET.get('budget_min')
    budget_max = request.GET.get('budget_max')
    
    if category:
        projects = projects.filter(work_packages__category=category).distinct()
    if location:
        projects = projects.filter(location__icontains=location)
    if budget_min:
        projects = projects.filter(budget__gte=budget_min)
    if budget_max:
        projects = projects.filter(budget__lte=budget_max)
    
    # Pagination
    paginator = Paginator(projects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': WorkPackage.CATEGORIES,
    }
    return render(request, 'supply_chain/project_list.html', context)


def project_detail(request, project_id):
    """View project details and its work packages."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check if user is a council - if so, they can only view their own projects
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.user_type == 'council' and project.created_by != request.user:
                messages.error(request, 'You do not have permission to view this project.')
                return redirect('dashboard')
        except UserProfile.DoesNotExist:
            pass
    
    # If project is not published and user is not the creator or contractor, deny access
    if project.status != 'published' and request.user != project.created_by:
        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                if profile.user_type != 'contractor':
                    messages.error(request, 'You do not have permission to view this project.')
                    return redirect('dashboard')
            except UserProfile.DoesNotExist:
                return redirect('complete_profile')
        else:
            return redirect('login')
    
    work_packages = project.work_packages.filter(is_active=True)
    
    # Check if user can bid (contractors only)
    can_bid = False
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            can_bid = (profile.user_type == 'contractor')
        except UserProfile.DoesNotExist:
            pass
    
    context = {
        'project': project,
        'work_packages': work_packages,
        'can_bid': can_bid,
    }
    return render(request, 'supply_chain/project_detail.html', context)


@login_required
def create_project(request):
    """Council users can create new projects."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council':
            messages.error(request, 'Only council members can create projects.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Please complete your profile first.')
        return redirect('complete_profile')
    
    # Calculate default dates
    today = date.today()
    next_month = today + timedelta(days=30)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            
            # Get or create council for this user
            try:
                user_council = Council.objects.get(user=request.user)
            except Council.DoesNotExist:
                # Create council if doesn't exist
                from django.utils.text import slugify
                user_council = Council.objects.create(
                    name=profile.company_name or f"{request.user.username}'s Council",
                    contact=profile.contact_number or request.user.email,
                    contact_email=request.user.email,
                    slug=slugify(profile.company_name or f"{request.user.username}-council"),
                    address=profile.address or "Address not specified",
                    user=request.user
                )
            
            # Assign the council user to the project
            project.council_user = request.user
            
            # Ensure status is published
            if not project.status:
                project.status = 'published'
                
            project.save()
            
            messages.success(request, f'Project "{project.title}" created successfully!')
            return redirect('project_detail', project_id=project.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        initial_data = {
            'start_date': today,
            'end_date': next_month,
            'status': 'published'
        }
        form = ProjectForm(initial=initial_data, user=request.user)
    
    context = {
        'form': form,
        'today': today,
        'next_month': next_month,
    }
    return render(request, 'supply_chain/create_project.html', context)


@login_required
def pending_bids(request):
    """View all pending bids for council projects."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council':
            messages.error(request, 'Only council members can review bids.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Get bids for projects created by this council user
    pending_bids_list = Bid.objects.filter(
        work_package__project__created_by=request.user,
        status='submitted'
    ).select_related('work_package', 'work_package__project', 'contractor', 'contractor__userprofile')
    
    context = {
        'pending_bids': pending_bids_list,
    }
    return render(request, 'supply_chain/pending_bids.html', context)


@login_required
def update_bid_status(request, bid_id):
    """Update bid status (approve/reject)."""
    bid = get_object_or_404(Bid, id=bid_id)
    
    # Check permission
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council' or bid.work_package.project.created_by != request.user:
            messages.error(request, 'You do not have permission to update this bid.')
            return redirect('view_package_bids', package_id=bid.work_package.id)
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in ['approved', 'rejected']:
            old_status = bid.status
            bid.status = new_status
            bid.save()
            
            # If approving a bid, reject all other bids for this work package
            if new_status == 'approved':
                Bid.objects.filter(
                    work_package=bid.work_package,
                    status='submitted'
                ).exclude(id=bid.id).update(status='rejected')
            
            messages.success(request, f'Bid has been {new_status}.')
        else:
            messages.error(request, 'Invalid status.')
    
    return redirect('view_package_bids', package_id=bid.work_package.id)


@login_required
def view_bids(request, project_id):
    """View all bids for a specific project."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permission
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council' or project.created_by != request.user:
            return HttpResponseForbidden("You don't have permission to view these bids.")
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Get all bids for this project
    bids = Bid.objects.filter(
        work_package__project=project
    ).select_related('work_package', 'contractor')
    
    context = {
        'project': project,
        'bids': bids,
    }
    return render(request, 'supply_chain/project_bids.html', context)


@login_required
def edit_project(request, project_id):
    """Edit an existing project."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permission - only project creator (council user) can edit
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council' or project.created_by != request.user:
            messages.error(request, 'You do not have permission to edit this project.')
            return redirect('project_detail', project_id=project.id)
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    if request.method == 'POST':
        try:
            # Update project fields
            project.title = request.POST.get('title')
            project.description = request.POST.get('description')
            project.budget = request.POST.get('budget')
            project.location = request.POST.get('location')
            project.start_date = request.POST.get('start_date')
            project.end_date = request.POST.get('end_date')
            project.status = request.POST.get('status')
            
            # Handle file upload if provided
            if 'blueprint' in request.FILES:
                project.blueprint = request.FILES['blueprint']
            
            project.save()
            messages.success(request, f'Project "{project.title}" updated successfully!')
            return redirect('project_detail', project_id=project.id)
            
        except Exception as e:
            messages.error(request, f'Error updating project: {str(e)}')
    
    # GET request - show form with current project data
    return render(request, 'supply_chain/edit_project.html', {
        'project': project
    })


@login_required
def create_work_package(request, project_id):
    """Create work packages for a project."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permission
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type not in ['council', 'admin'] or project.created_by != request.user:
            messages.error(request, 'You do not have permission to add work packages.')
            return redirect('project_detail', project_id=project.id)
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    if request.method == 'POST':
        form = WorkPackageForm(request.POST, user=request.user, project=project)
        if form.is_valid():
            work_package = form.save()
            messages.success(request, 'Work package created successfully!')
            return redirect('project_detail', project_id=project.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = WorkPackageForm(user=request.user, project=project)
    
    return render(request, 'supply_chain/create_work_package.html', {
        'form': form,
        'project': project
    })

@login_required
def submit_bid(request, package_id):
    """Contractors submit bids for work packages."""
    work_package = get_object_or_404(WorkPackage, id=package_id, is_active=True)
    
    # Check if user is a contractor
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'contractor':
            messages.error(request, 'Only contractors can submit bids.')
            return redirect('project_detail', project_id=work_package.project.id)
    except UserProfile.DoesNotExist:
        messages.error(request, 'Please complete your profile first.')
        return redirect('complete_profile')
    
    # Check if deadline has passed
    if work_package.deadline < timezone.now().date():
        messages.error(request, 'Bidding deadline has passed for this work package.')
        return redirect('project_detail', project_id=work_package.project.id)
    
    # Check if already bid
    existing_bid = Bid.objects.filter(work_package=work_package, contractor=request.user).first()
    if existing_bid:
        messages.info(request, 'You have already submitted a bid for this package.')
        return redirect('my_bids')
    
    if request.method == 'POST':
        # Pass work_package to the form
        form = BidForm(request.POST, request.FILES, user=request.user, work_package=work_package)
        if form.is_valid():
            bid = form.save()
            messages.success(request, 'Bid submitted successfully!')
            return redirect('my_bids')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # Pass work_package to the form
        form = BidForm(user=request.user, work_package=work_package)
    
    context = {
        'work_package': work_package,
        'form': form,
    }
    return render(request, 'supply_chain/submit_bid.html', context)
@login_required
def my_bids(request):
    """View all bids submitted by the contractor."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'contractor':
            return HttpResponseForbidden("Only contractors can view bids.")
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    bids = Bid.objects.filter(contractor=request.user).order_by('-submitted_at')
    
    # Count bids by status
    pending_count = bids.filter(status='pending').count()
    approved_count = bids.filter(status='approved').count()
    rejected_count = bids.filter(status='rejected').count()
    
    context = {
        'bids': bids,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'supply_chain/my_bids.html', context)


@login_required
def view_package_bids(request, package_id):
    """Council/Management view all bids for a work package."""
    work_package = get_object_or_404(WorkPackage, id=package_id)
    
    # Check permission
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type not in ['council', 'admin']:
            messages.error(request, "You don't have permission to view bids.")
            return redirect('project_detail', project_id=work_package.project.id)
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Check if council user owns this project
    if profile.user_type == 'council' and work_package.project.created_by != request.user:
        messages.error(request, "You can only view bids for your own projects.")
        return redirect('dashboard')
    
    bids = Bid.objects.filter(work_package=work_package).order_by('amount')
    
    context = {
        'work_package': work_package,
        'bids': bids,
    }
    return render(request, 'supply_chain/view_bids.html', context)


@login_required
def manage_team(request, project_id):
    """Manage contractor team for a project."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permission
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type not in ['council', 'admin'] or project.created_by != request.user:
            return HttpResponseForbidden("You don't have permission to manage teams for this project.")
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Get or create team
    team, created = ContractorTeam.objects.get_or_create(
        project=project,
        defaults={'team_name': f"Team for {project.title}", 'created_by': request.user}
    )
    
    # Get approved bids for this project
    approved_bids = Bid.objects.filter(
        work_package__project=project,
        status='approved'
    )
    
    # Get current assignments
    assignments = team.assignments.all()
    
    context = {
        'project': project,
        'team': team,
        'approved_bids': approved_bids,
        'assignments': assignments,
    }
    return render(request, 'supply_chain/manage_team.html', context)


def all_councils(request):
    """List all councils."""
    councils = Council.objects.all()
    context = {'councils': councils}
    return render(request, 'supply_chain/all_councils_list.html', context)


def hello_world_index(request):
    """Simple hello world."""
    return HttpResponse("Hello World! This is the main index of the Supply Chain project")


# ========== AUTHENTICATION VIEWS ==========
def register(request):
    """User registration - ONLY FOR CONTRACTORS (using form)."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Save user without creating profile in form
                user = form.save()
                
                # Update the auto-created UserProfile with company and contact info
                profile = UserProfile.objects.get(user=user)
                profile.user_type = 'contractor'
                profile.company_name = form.cleaned_data['company_name']
                profile.contact_number = form.cleaned_data['contact_number']
                profile.save()
                
                # Store success message in session for login page
                request.session['registration_success'] = True
                request.session['registration_username'] = user.username
                request.session.modified = True
                
                # Redirect to login page
                return redirect('login')
                
            except Exception as e:
                # Handle any errors - log and show error
                form = UserRegistrationForm()
                context = {'form': form, 'error': f'Error: {str(e)}'}
                return render(request, 'supply_chain/register.html', context)
        else:
            # Form has validation errors - display them
            context = {'form': form}
            return render(request, 'supply_chain/register.html', context)
    else:
        form = UserRegistrationForm()
    
    return render(request, 'supply_chain/register.html', {'form': form})

def user_login(request):
    """User login."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        account_type = request.POST.get('account_type')
        
        if not username or not password or not account_type:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'supply_chain/login.html')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if the selected account type matches the user's actual profile
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.user_type != account_type:
                    messages.error(request, f'This account is registered as a {profile.user_type}, not a {account_type}. Please select the correct account type.')
                    return render(request, 'supply_chain/login.html')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found. Please contact support.')
                return render(request, 'supply_chain/login.html')
            
            login(request, user)
            messages.success(request, 'Login successful!')
            # Clear registration success flag
            request.session.pop('registration_success', None)
            request.session.pop('registration_username', None)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'supply_chain/login.html')


@login_required
def user_logout(request):
    """User logout."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
def dashboard(request):
    """User dashboard based on role."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        
        if profile.user_type == 'contractor':
            # Contractor dashboard
            active_bids = Bid.objects.filter(contractor=request.user, status='submitted').count()
            approved_bids = Bid.objects.filter(contractor=request.user, status='approved').count()
            
            context = {
                'profile': profile,
                'active_bids': active_bids,
                'approved_bids': approved_bids,
            }
            return render(request, 'supply_chain/dashboard_contractor.html', context)
            
        elif profile.user_type == 'council':
            # Council dashboard
            council_projects = Project.objects.filter(created_by=request.user)
            
            # Calculate pending bids for THIS council user's projects
            pending_bids_count = Bid.objects.filter(
                work_package__project__created_by=request.user,
                status='submitted'
            ).count()
            
            context = {
                'profile': profile,
                'council_projects': council_projects,
                'pending_bids': pending_bids_count,
            }
            return render(request, 'supply_chain/dashboard_council.html', context)
            
        elif profile.user_type == 'admin':
            return redirect('/admin/')
            
        else:
            context = {'profile': profile}
            return render(request, 'supply_chain/dashboard.html', context)
        
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')


@login_required
def complete_profile(request):
    """Complete user profile after registration."""
    if request.method == 'POST':
        try:
            profile = UserProfile.objects.get(user=request.user)
            form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        except UserProfile.DoesNotExist:
            form = UserProfileForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        try:
            profile = UserProfile.objects.get(user=request.user)
            form = UserProfileForm(instance=profile, user=request.user)
        except UserProfile.DoesNotExist:
            form = UserProfileForm(user=request.user)
    
    return render(request, 'supply_chain/complete_profile.html', {'form': form})


@login_required
def project_bids(request, project_id):
    """View all bids for a specific project."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permission
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council' or project.created_by != request.user:
            return HttpResponseForbidden("You don't have permission to view these bids.")
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Get all work packages for this project
    work_packages = project.work_packages.all()
    
    # Get bids for each work package
    bids_by_package = []
    for package in work_packages:
        bids = package.bids.all().select_related('contractor')
        if bids.exists():
            bids_by_package.append({
                'package': package,
                'bids': bids
            })
    
    context = {
        'project': project,
        'bids_by_package': bids_by_package,
    }
    return render(request, 'supply_chain/project_bids.html', context)


# Additional function for project list (simplified)
def project_list_simple(request):
    """List all projects."""
    projects = Project.objects.all().order_by('-created_at')[:10]
    context = {
        'projects': projects,
    }
    return render(request, 'supply_chain/project_list.html', context)


# ========== PROFILE MANAGEMENT ==========
@login_required
def edit_profile(request):
    """Allow users to edit their profile information."""
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        messages.error(request, 'Please complete your profile first.')
        return redirect('complete_profile')
    
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('edit_profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProfileEditForm(instance=profile, user=request.user)
    
    context = {
        'form': form,
        'profile': profile,
    }
    return render(request, 'supply_chain/edit_profile.html', context)


@login_required
def view_teams(request):
    """View teams (accepted contractors) for council projects organized by project."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council':
            messages.error(request, 'Only council members can view teams.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Get all projects created by this council user
    council_projects = Project.objects.filter(created_by=request.user).prefetch_related(
        'work_packages'
    )
    
    # Build project teams data
    projects_with_teams = []
    for project in council_projects:
        teams_data = {}
        
        # Get all accepted bids for this project's work packages
        for work_package in project.work_packages.all():
            accepted_bids = Bid.objects.filter(
                work_package=work_package,
                status='approved'
            ).select_related('contractor', 'contractor__userprofile')
            
            if accepted_bids.exists():
                if work_package.id not in teams_data:
                    teams_data[work_package.id] = {
                        'package': work_package,
                        'contractors': []
                    }
                
                for bid in accepted_bids:
                    teams_data[work_package.id]['contractors'].append({
                        'bid': bid,
                        'user': bid.contractor,
                        'profile': bid.contractor.userprofile
                    })
        
        if teams_data:
            projects_with_teams.append({
                'project': project,
                'teams': list(teams_data.values())
            })
    
    context = {
        'projects_with_teams': projects_with_teams,
    }
    return render(request, 'supply_chain/view_teams.html', context)

@login_required
def view_project_teams(request, project_id):
    """View teams for a specific project."""
    project = get_object_or_404(Project, id=project_id)
    
    # Check permission - user must be the creator of the project
    if project.created_by != request.user:
        messages.error(request, 'You do not have permission to view this project\'s teams.')
        return redirect('view_teams')
    
    teams_data = {}
    
    # Get all accepted bids for this project's work packages
    for work_package in project.work_packages.all():
        accepted_bids = Bid.objects.filter(
            work_package=work_package,
            status='approved'
        ).select_related('contractor', 'contractor__userprofile')
        
        if accepted_bids.exists():
            if work_package.id not in teams_data:
                teams_data[work_package.id] = {
                    'package': work_package,
                    'contractors': []
                }
            
            for bid in accepted_bids:
                teams_data[work_package.id]['contractors'].append({
                    'bid': bid,
                    'user': bid.contractor,
                    'profile': bid.contractor.userprofile
                })
    
    context = {
        'project': project,
        'teams': list(teams_data.values()),
    }
    return render(request, 'supply_chain/view_project_teams.html', context)

@login_required
def change_password(request):
    """Allow users to change their password."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['new_password1'])
            request.user.save()
            messages.success(request, 'Your password has been changed successfully!')
            # Re-login user after password change
            from django.contrib.auth import authenticate, login
            user = authenticate(username=request.user.username, password=form.cleaned_data['new_password1'])
            if user is not None:
                login(request, user)
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = PasswordChangeForm(user=request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'supply_chain/change_password.html', context)


# ========== PROJECT REPORT VIEWS ==========

@login_required
def view_project_report(request, project_id):
    """
    View project report with comprehensive analytics.
    Only available for council users and admins.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions - only council/admin can view reports
    user_profile = request.user.userprofile if hasattr(request.user, 'userprofile') else None
    is_council_or_admin = (
        user_profile and user_profile.user_type in ['council', 'admin']
    ) or request.user.is_staff or request.user.is_superuser
    
    if not is_council_or_admin:
        messages.error(request, 'You do not have permission to view this report.')
        return redirect('project_detail', project_id=project_id)
    
    # Generate report
    report, report_data = generate_project_report(project, request.user)
    
    context = {
        'project': project,
        'report': report,
        'report_data': report_data,
        'package_bids': report_data.get('package_bids', []),
        'total_recommended_cost': report_data.get('total_recommended_cost', 0),
    }
    
    return render(request, 'supply_chain/project_report.html', context)


@login_required
def view_reports(request):
    """View all project reports for council projects."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.user_type != 'council':
            messages.error(request, 'Only council members can view reports.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    
    # Get all projects created by this council user
    council_projects = Project.objects.filter(created_by=request.user).prefetch_related(
        'work_packages'
    )
    
    # Build projects data with bid counts
    projects_with_data = []
    for project in council_projects:
        total_bids = 0
        accepted_bids = 0
        
        for work_package in project.work_packages.all():
            bids = Bid.objects.filter(work_package=work_package)
            total_bids += bids.count()
            accepted_bids += bids.filter(status='approved').count()
        
        projects_with_data.append({
            'project': project,
            'total_bids': total_bids,
            'accepted_bids': accepted_bids,
        })
    
    return render(request, 'supply_chain/view_reports.html', {
        'projects_with_data': projects_with_data,
    })


@login_required
def download_project_report_pdf(request, project_id):
    """
    Download project report as PDF.
    Only available for council users and admins.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Check permissions
    user_profile = request.user.userprofile if hasattr(request.user, 'userprofile') else None
    is_council_or_admin = (
        user_profile and user_profile.user_type in ['council', 'admin']
    ) or request.user.is_staff or request.user.is_superuser
    
    if not is_council_or_admin:
        return HttpResponseForbidden('You do not have permission to download this report.')
    
    # Generate report
    report, _ = generate_project_report(project, request.user)
    
    try:
        # Generate PDF
        pdf_buffer = generate_pdf_report(report, project)
        
        # Create HTTP response
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Project_Report_{project.title}_{date.today()}.pdf"'
        
        return response
    except ImportError as e:
        messages.error(request, f'PDF generation error: {str(e)}')
        return redirect('view_project_report', project_id=project_id)
