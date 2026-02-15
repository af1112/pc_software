# from apps.organizations.models import Organization
from django.utils.translation import activate as i18n_activate
from django.utils import timezone as dj_timezone
from zoneinfo import ZoneInfo
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout

class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = getattr(request.user, 'profile', None)
                if profile:
                    # Language
                    lang = profile.preferred_language
                    i18n_activate(lang)
                    request.LANGUAGE_CODE = lang
                    # Timezone (per organization)
                    org = getattr(profile, 'organization', None)
                    if org and org.timezone:
                        try:
                            dj_timezone.activate(ZoneInfo(org.timezone))
                        except Exception:
                            dj_timezone.activate(dj_timezone.get_default_timezone())
            except Exception:
                pass
        response = self.get_response(request)
        return response

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Use hardcoded paths to avoid NoReverseMatch during early boot/migration
        exempt_urls = [
            '/accounts/login/',
            '/accounts/register/',
            '/',
            '/run-migrations/',
        ]
        
        if not request.user.is_authenticated and request.path not in exempt_urls and not request.path.startswith('/static/'):
            return redirect('/accounts/login/')
            
        response = self.get_response(request)
        return response

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        if request.user.is_authenticated:
            try:
                if hasattr(request.user, 'profile'):
                    profile = request.user.profile
                    request.organization = getattr(profile, 'organization', None)
            except Exception:
                pass

        if request.user.is_authenticated and not request.user.is_superuser:
            org = getattr(request, 'organization', None)
            if org:
                today = dj_timezone.now().date()
                expired = (org.subscription_end_date and org.subscription_end_date < today) or not org.is_active
                if expired:
                    logout(request)
                    messages.error(request, "Subscription for your organization has expired. Please contact support.")
                    return redirect('/accounts/login/')
        
        response = self.get_response(request)
        return response
