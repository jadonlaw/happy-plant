from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Turn an existing, verified Happy Plant account into the admin. Usage: python manage.py make_admin you@email.com"

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **opts):
        email = opts["email"].strip().lower()
        user = get_user_model().objects.filter(username=email).first()
        if not user:
            raise CommandError(f"No account for {email}. Sign up first.")
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(self.style.SUCCESS(f"{email} is now an admin. Log in at /admin/ with this email."))
