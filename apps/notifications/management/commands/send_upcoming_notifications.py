"""
Management command to send upcoming event notifications
Usage: python manage.py send_upcoming_notifications
"""
from django.core.management.base import BaseCommand
from apps.notifications.signals import send_upcoming_event_notifications


class Command(BaseCommand):
    help = 'Send notifications for upcoming events'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to send upcoming event notifications...'))
        
        try:
            send_upcoming_event_notifications()
            self.stdout.write(
                self.style.SUCCESS('Successfully sent upcoming event notifications')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error sending notifications: {str(e)}')
            )
