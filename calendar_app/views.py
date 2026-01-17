from django.shortcuts import render
from django.utils import timezone
import calendar
from datetime import datetime, timedelta

def calendar_view(request):
    # Get year and month from request, default to current
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    # Create calendar object
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    # Get current date for highlighting
    today = timezone.now().date()

    # Calculate previous and next month
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    context = {
        'calendar': cal,
        'month_name': month_name,
        'year': year,
        'month': month,
        'today': today,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'weekday_names': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    }

    return render(request, 'calendar_app/calendar.html', context)
