# Beautiful Django Calendar App

A simple and beautifully designed Django application for displaying a calendar in an authentic and modern way.

## Features

- **Modern Design**: Beautiful gradient-based UI with smooth animations
- **Monthly View**: Display calendar in a clean monthly grid format
- **Today Highlighting**: Current date is highlighted with a distinctive style
- **Easy Navigation**: Navigate between months with Previous/Next buttons
- **Responsive**: Works perfectly on desktop and mobile devices
- **Clean Code**: Well-organized Django structure following best practices

## Installation

1. Install Django (if not already installed):
```bash
pip install django
```

2. Run migrations:
```bash
python manage.py migrate
```

## Running the Application

Start the development server:
```bash
python manage.py runserver
```

Then open your browser and navigate to:
```
http://127.0.0.1:8000/
```

## Project Structure

```
calendar_project/
├── calendar_app/           # Main calendar application
│   ├── templates/          # HTML templates
│   │   └── calendar_app/
│   │       └── calendar.html
│   ├── views.py           # Calendar views
│   └── urls.py            # App URL configuration
├── calendar_project/       # Project settings
│   ├── settings.py        # Django settings
│   └── urls.py            # Main URL configuration
└── manage.py              # Django management script
```

## Features in Detail

### Calendar View
- Displays the current month by default
- Shows all days in a 7-column grid (Monday to Sunday)
- Empty cells for days outside the current month

### Navigation
- **Previous**: Go to the previous month
- **Today**: Jump back to the current month
- **Next**: Go to the next month

### Styling
- Purple gradient theme
- Hover effects on calendar days
- Pulse animation on today's date
- Smooth transitions and modern aesthetics

## Technology Stack

- **Backend**: Django 5.2
- **Frontend**: HTML5, CSS3
- **Python**: 3.11+
- **Database**: SQLite (default Django database)

## Customization

You can customize the calendar appearance by editing the CSS in:
```
calendar_app/templates/calendar_app/calendar.html
```

The color scheme uses a purple gradient, but you can easily change the colors in the CSS section.

## License

This is a simple demonstration project for educational purposes.
