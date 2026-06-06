# supply_chain/report_utils.py
"""
Report generation utilities for project analytics and reporting
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Count, Sum, Avg, Q
from .models import Project, ProjectReport, Bid, WorkPackage, TeamAssignment


def generate_project_report(project, user=None):
    """
    Generate comprehensive project report with:
    1. Project Overview (budget, timeline, completion %)
    2. Financial Report (costs, variances)
    3. Bidding Analytics (bid counts, acceptance rates)
    4. Timeline/Progress (milestones, completion %)
    5. Work Package Status
    """
    # Calculate project overview
    total_budget = project.budget
    
    # Calculate actual spending (from approved bids)
    approved_bids = Bid.objects.filter(
        work_package__project=project,
        status='approved'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    actual_spending = approved_bids
    budget_variance = total_budget - actual_spending
    
    # Calculate completion percentage based on team assignments
    total_packages = project.work_packages.count()
    completed_packages = TeamAssignment.objects.filter(
        work_package__project=project
    ).count()
    
    completion_percentage = (
        (completed_packages / total_packages * 100) if total_packages > 0 else 0
    )
    
    # Bidding Analytics
    all_bids = Bid.objects.filter(work_package__project=project)
    total_bids_received = all_bids.count()
    total_bids_accepted = all_bids.filter(status='approved').count()
    
    average_bid_amount = all_bids.aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
    
    bid_acceptance_rate = (
        (total_bids_accepted / total_bids_received * 100) if total_bids_received > 0 else 0
    )
    
    # Find top performing contractor
    top_contractor_data = all_bids.filter(
        status='approved'
    ).values('contractor__username').annotate(
        count=Count('id')
    ).order_by('-count').first()
    
    top_performing_contractor = (
        top_contractor_data['contractor__username'] if top_contractor_data else ''
    )
    
    # Timeline data
    today = date.today()
    days_until_deadline = (project.end_date - today).days
    is_on_schedule = days_until_deadline > 0
    
    # Work package bids analysis
    package_bids_analysis = []
    total_recommended_cost = Decimal('0')
    
    for pkg in project.work_packages.all():
        pkg_bids = Bid.objects.filter(work_package=pkg).order_by('amount')
        
        if pkg_bids.exists():
            lowest_bid = pkg_bids.first()
            highest_bid = pkg_bids.last()
            avg_bid = pkg_bids.aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
            
            package_bids_analysis.append({
                'package_id': pkg.id,
                'package_title': pkg.title,
                'total_bids': pkg_bids.count(),
                'lowest_bid_amount': float(lowest_bid.amount),
                'lowest_bid_contractor': lowest_bid.contractor.username,
                'highest_bid_amount': float(highest_bid.amount),
                'average_bid_amount': float(avg_bid),
                'estimated_budget': float(pkg.estimated_budget),
                'profitable_bid': lowest_bid.id,  # Lowest bid is most profitable for council
                'all_bids': [
                    {
                        'id': b.id,
                        'contractor': b.contractor.username,
                        'amount': float(b.amount),
                        'status': b.status,
                        'is_profitable': b.id == lowest_bid.id
                    } for b in pkg_bids
                ]
            })
            total_recommended_cost += lowest_bid.amount
    
    # Build detailed report data
    report_data = {
        'project_title': project.title,
        'project_id': project.id,
        'generated_date': str(date.today()),
        'project_overview': {
            'title': project.title,
            'status': project.get_status_display(),
            'location': project.location,
            'start_date': str(project.start_date),
            'end_date': str(project.end_date),
        },
        'financial': {
            'total_budget': str(total_budget),
            'actual_spending': str(actual_spending),
            'budget_variance': str(budget_variance),
            'variance_percentage': f"{(budget_variance / total_budget * 100) if total_budget else 0:.2f}%",
        },
        'bidding': {
            'total_bids_received': total_bids_received,
            'total_bids_accepted': total_bids_accepted,
            'average_bid_amount': str(average_bid_amount),
            'acceptance_rate': f"{bid_acceptance_rate:.2f}%",
        },
        'progress': {
            'days_until_deadline': days_until_deadline,
            'on_schedule': is_on_schedule,
        },
        'package_bids': package_bids_analysis,
        'total_recommended_cost': str(total_recommended_cost),
    }
    
    # Create or update ProjectReport
    report, created = ProjectReport.objects.update_or_create(
        project=project,
        defaults={
            'generated_by': user,
            'total_budget': total_budget,
            'actual_spending': actual_spending,
            'completion_percentage': int(completion_percentage),
            'budget_variance': budget_variance,
            'total_bids_received': total_bids_received,
            'total_bids_accepted': total_bids_accepted,
            'average_bid_amount': average_bid_amount,
            'bid_acceptance_rate': bid_acceptance_rate,
            'top_performing_contractor': '',
            'days_until_deadline': days_until_deadline,
            'is_on_schedule': is_on_schedule,
            'total_work_packages': total_packages,
            'completed_packages': completed_packages,
            'in_progress_packages': 0,
            'pending_packages': 0,
            'report_data': report_data,
        }
    )
    
    return report, report_data


def get_work_package_details(project):
    """Get detailed breakdown of each work package"""
    packages = project.work_packages.all()
    package_details = []
    
    for pkg in packages:
        bids = Bid.objects.filter(work_package=pkg)
        assignment = TeamAssignment.objects.filter(work_package=pkg).first()
        
        package_details.append({
            'title': pkg.title,
            'category': pkg.get_category_display(),
            'budget': str(pkg.estimated_budget),
            'deadline': str(pkg.deadline),
            'bids_count': bids.count(),
            'accepted_bids': bids.filter(status='approved').count(),
            'assigned_contractor': assignment.contractor.username if assignment else 'Not Assigned',
            'bid_amounts': [str(b.amount) for b in bids.order_by('amount')],
        })
    
    return package_details


def generate_pdf_report(report, project, report_data=None):
    """
    Generate PDF report using reportlab
    Returns: PDF buffer ready for download
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib import colors
        from io import BytesIO
        
        # Create PDF buffer
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Use provided report_data or fallback to empty dict
        if report_data is None:
            report_data = {}
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=30,
            alignment=1,  # Center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=12,
            spaceBefore=12,
        )
        
        # Title
        elements.append(Paragraph(f"Project Report: {project.title}", title_style))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Project Overview Section
        elements.append(Paragraph("Project Overview", heading_style))
        overview_data = [
            ['Status', f"{project.get_status_display()}"],
            ['Location', project.location],
            ['Start Date', str(project.start_date)],
            ['End Date', str(project.end_date)],
        ]
        overview_table = Table(overview_data, colWidths=[2 * inch, 4 * inch])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(overview_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Financial Report Section
        elements.append(Paragraph("Financial Report", heading_style))
        financial_data = [
            ['Metric', 'Amount'],
            ['Total Budget', f"${report.total_budget:,.2f}"],
            ['Actual Spending', f"${report.actual_spending:,.2f}"],
            ['Budget Variance', f"${report.budget_variance:,.2f}"],
            ['Average Bid Amount', f"${report.average_bid_amount:,.2f}"],
        ]
        financial_table = Table(financial_data, colWidths=[3 * inch, 3 * inch])
        financial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(financial_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Bidding Analytics Section
        elements.append(Paragraph("Bidding Analytics", heading_style))
        bidding_data = [
            ['Metric', 'Value'],
            ['Total Bids Received', str(report.total_bids_received)],
            ['Total Bids Accepted', str(report.total_bids_accepted)],
            ['Acceptance Rate', f"{report.bid_acceptance_rate:.2f}%"],
        ]
        bidding_table = Table(bidding_data, colWidths=[3 * inch, 3 * inch])
        bidding_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(bidding_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Timeline Section
        elements.append(Paragraph("Timeline & Schedule", heading_style))
        timeline_data = [
            ['Metric', 'Value'],
            ['Days Until Deadline', str(report.days_until_deadline)],
            ['On Schedule', 'Yes' if report.is_on_schedule else 'No'],
        ]
        timeline_table = Table(timeline_data, colWidths=[3 * inch, 3 * inch])
        timeline_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0891b2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(timeline_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Package Bids Section
        elements.append(Paragraph("Package Bids & Profitability Analysis", heading_style))
        if report_data.get('package_bids'):
            for pkg in report_data['package_bids']:
                # Package header
                elements.append(Paragraph(f"<b>{pkg['package_title']}</b> (Estimated Budget: ${pkg['estimated_budget']:,.2f})", styles['Normal']))
                
                # Recommended bid
                pkg_data = [
                    ['Contractor', 'Bid Amount', '% of Budget'],
                    [pkg['lowest_bid_contractor'], f"${pkg['lowest_bid_amount']:,.2f}", f"{(pkg['lowest_bid_amount']/pkg['estimated_budget']*100):.1f}%"],
                ]
                pkg_table = Table(pkg_data, colWidths=[2.5 * inch, 2.5 * inch, 1.5 * inch])
                pkg_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f0f0f0')),
                ]))
                elements.append(pkg_table)
                
                # All bids
                all_bids_data = [['Contractor', 'Bid Amount']]
                for bid in pkg['all_bids']:
                    status_marker = " (RECOMMENDED)" if bid['is_profitable'] else ""
                    all_bids_data.append([bid['contractor'] + status_marker, f"${bid['amount']:,.2f}"])
                
                all_bids_table = Table(all_bids_data, colWidths=[3 * inch, 3 * inch])
                all_bids_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b7280')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ]))
                elements.append(all_bids_table)
                elements.append(Spacer(1, 0.2 * inch))
            
            # Summary
            elements.append(Paragraph(f"<b>Total Recommended Cost:</b> ${report_data.get('total_recommended_cost', 0)}", styles['Normal']))
        else:
            elements.append(Paragraph("No bids available for analysis", styles['Normal']))
        elements.append(Spacer(1, 0.3 * inch))
        
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        return pdf_buffer
        
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF generation. "
            "Install it with: pip install reportlab"
        )
