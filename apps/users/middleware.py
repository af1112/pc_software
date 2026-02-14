# from apps.organizations.models import Organization

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import activate

class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # Use preferred_language from profile
                lang = request.user.profile.preferred_language
                activate(lang)
                request.LANGUAGE_CODE = lang
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
            '/run-migrations/',
        ]
        
        # Check if the path is an exempt URL
        is_exempt = any(request.path == url or request.path.startswith(url) for url in exempt_urls)

        if not request.user.is_authenticated and not is_exempt and not request.path.startswith('/static/'):
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
                    # Avoid direct import to prevent circular issues or early crashes
                    request.organization = getattr(profile, 'organization', None)
            except Exception:
                # Handle cases where DB migration hasn't been run yet
                pass
        
        response = self.get_response(request)
        return response
