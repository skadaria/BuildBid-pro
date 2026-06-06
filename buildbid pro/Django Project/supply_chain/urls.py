# supply_chain/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('councils/', views.all_councils, name='councils'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # User dashboard and profile
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/complete/', views.complete_profile, name='complete_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    
    # Project management (Council/Admin only)
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/<int:project_id>/packages/create/', 
         views.create_work_package, name='create_work_package'),
    
    # Bidding system
    path('packages/<int:package_id>/bid/', views.submit_bid, name='submit_bid'),
    path('bids/<int:bid_id>/update/', views.update_bid_status, name='update_bid_status'),

    # My bids (for contractors)
    path('my-bids/', views.my_bids, name='my_bids'),

    # Project editing
    path('projects/<int:project_id>/edit/', views.edit_project, name='edit_project'),

    # Bid review for council
    path('bids/pending/', views.pending_bids, name='pending_bids'),
    path('projects/<int:project_id>/bids/', views.view_bids, name='view_bids'),  # CHANGED
    path('packages/<int:package_id>/bids/', views.view_package_bids, name='view_package_bids'),
    
    # Team management
    path('projects/<int:project_id>/team/', views.manage_team, name='manage_team'),
    path('teams/', views.view_teams, name='view_teams'),
    path('teams/<int:project_id>/', views.view_project_teams, name='view_project_teams'),
    
    # Project Reports
    path('reports/', views.view_reports, name='view_reports'),
    path('projects/<int:project_id>/report/', views.view_project_report, name='view_project_report'),
    path('projects/<int:project_id>/report/download-pdf/', views.download_project_report_pdf, name='download_project_report_pdf'),
    
    # Hello world
    path('hello/', views.hello_world_index, name='hello_world'),
]