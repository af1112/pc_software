from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.conf import settings
from .models import UserProfile
from .forms import LanguageSettingsForm, UserCreateForm, UserPermissionsForm
from django.utils.translation import activate
from django.utils.translation import gettext as _
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.models import User, Permission
from django.shortcuts import resolve_url
from apps.organizations.models import Organization
from urllib.parse import urlparse


DEFAULT_RESET_PASSWORD = 'Aa@123456'


class CustomLoginView(auth_views.LoginView):
    template_name = 'registration/login.html'

    def _sanitize_next_target(self, target):
        if not target:
            return ''

        target = str(target).strip()
        if not target:
            return ''

        if not url_has_allowed_host_and_scheme(
            url=target,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return ''

        parsed = urlparse(target)
        path = (parsed.path or '').lower()
        blocked_exact = {'/favicon.ico'}
        blocked_prefixes = ('/static/', '/media/', '/.well-known/')
        blocked_ext = ('.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.map')

        if path in blocked_exact:
            return ''
        if any(path.startswith(prefix) for prefix in blocked_prefixes):
            return ''
        if path.endswith(blocked_ext):
            return ''

        return target

    def _resolve_next_target(self):
        redirect_field = self.redirect_field_name
        query_next = self.request.GET.get(redirect_field)
        post_next = self.request.POST.get(redirect_field)
        session_next = self.request.session.get('post_login_redirect', '')
        referer = self.request.META.get('HTTP_REFERER', '')
        referer_quick = '/attendance/quick/' if '/attendance/quick/' in referer else ''
        candidates = [query_next, post_next, self.get_redirect_url(), session_next, referer_quick]
        for candidate in candidates:
            valid_target = self._sanitize_next_target(candidate)
            if valid_target:
                return valid_target
        return ''

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            next_target = self._resolve_next_target()
            if next_target:
                request.session['post_login_redirect'] = next_target
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_value = self._resolve_next_target() or ''
        debug_forced = str(self.request.GET.get('debug', '')).lower() in {'1', 'true', 'yes', 'on'}
        context['next_value'] = next_value
        context['session_next'] = self.request.session.get('post_login_redirect', '')
        context['referer'] = self.request.META.get('HTTP_REFERER', '')
        context['debug_login'] = settings.DEBUG or debug_forced
        if settings.DEBUG:
            print(
                "DEBUG LOGIN CONTEXT "
                f"next={next_value!r} "
                f"session_next={self.request.session.get('post_login_redirect', '')!r} "
                f"referer={self.request.META.get('HTTP_REFERER', '')!r} "
                f"path={self.request.get_full_path()!r}"
            )
        return context

    def get_success_url(self):
        force_quick = self.request.session.pop('force_quick_after_login', False)
        candidate_targets = [
            self.request.GET.get(self.redirect_field_name, ''),
            self.request.POST.get(self.redirect_field_name, ''),
            self.request.session.get('post_login_redirect', ''),
        ]
        has_quick_target = any(str(target).startswith('/attendance/quick') for target in candidate_targets if target)

        if force_quick or has_quick_target:
            if settings.DEBUG:
                print("DEBUG LOGIN SUCCESS forced_quick_redirect=True")
            self.request.session['last_login_redirect_debug'] = {
                'reason': 'force_quick' if force_quick else 'quick_target',
                'post_next': self.request.POST.get(self.redirect_field_name, ''),
                'get_next': self.request.GET.get(self.redirect_field_name, ''),
                'session_next': self.request.session.get('post_login_redirect', ''),
                'final_redirect': '/attendance/quick/',
            }
            self.request.session.pop('post_login_redirect', None)
            return resolve_url('hr_attendance:quick_clock')

        redirect_to = self._resolve_next_target()
        if settings.DEBUG:
            print(
                "DEBUG LOGIN SUCCESS "
                f"post_next={self.request.POST.get(self.redirect_field_name, '')!r} "
                f"session_next={self.request.session.get('post_login_redirect', '')!r} "
                f"redirect_to={redirect_to!r}"
            )
        if redirect_to:
            self.request.session['last_login_redirect_debug'] = {
                'reason': 'resolved_redirect',
                'post_next': self.request.POST.get(self.redirect_field_name, ''),
                'get_next': self.request.GET.get(self.redirect_field_name, ''),
                'session_next': self.request.session.get('post_login_redirect', ''),
                'final_redirect': redirect_to,
            }
            self.request.session.pop('post_login_redirect', None)
            return redirect_to
        self.request.session['last_login_redirect_debug'] = {
            'reason': 'fallback_login_redirect_url',
            'post_next': self.request.POST.get(self.redirect_field_name, ''),
            'get_next': self.request.GET.get(self.redirect_field_name, ''),
            'session_next': self.request.session.get('post_login_redirect', ''),
            'final_redirect': resolve_url(settings.LOGIN_REDIRECT_URL),
        }
        return resolve_url(settings.LOGIN_REDIRECT_URL)


def is_admin(user):
    return user.is_superuser or user.is_staff


def is_superuser_only(user):
    return user.is_authenticated and user.is_superuser

@login_required
def profile_view(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    org = getattr(profile, 'organization', None) if profile else None
    role = getattr(profile, 'role', None) if profile else None
    perms = user.user_permissions.all().order_by('name')

    is_fa = str(getattr(request, 'LANGUAGE_CODE', '')).lower().startswith('fa')
    if is_fa:
        role_labels = {
            'admin': 'مدیر',
            'supervisor': 'سرپرست',
            'user': 'کاربر',
        }
    else:
        role_labels = {
            'admin': _('Admin'),
            'supervisor': _('Supervisor'),
            'user': _('User'),
        }
    profile_role_label = role_labels.get(role, role or '-')

    if is_fa:
        perm_labels = {
            'can_access_expenses': 'دسترسی مدیریت هزینه‌ها',
            'can_access_ticketing': 'دسترسی سیستم تیکتینگ',
            'can_access_attendance': 'دسترسی حضور و غیاب',
            'can_access_personnel': 'دسترسی پرسنل و حقوق',
            'can_access_projects': 'دسترسی کنترل پروژه',
            'can_access_dms': 'دسترسی مدیریت اسناد',
            'can_access_ai': 'دسترسی موتور هوش مصنوعی',
            'can_access_menu': 'دسترسی منوی دیجیتال',
            'can_access_club': 'دسترسی باشگاه مشتریان',
        }
    else:
        perm_labels = {
            'can_access_expenses': _('Expense Manager Access'),
            'can_access_ticketing': _('Ticketing System Access'),
            'can_access_attendance': _('Attendance Access'),
            'can_access_personnel': _('Personnel & Payroll Access'),
            'can_access_projects': _('Project Control Access'),
            'can_access_dms': _('Document DMS Access'),
            'can_access_ai': _('AI Engine Access'),
            'can_access_menu': _('Digital Menu Access'),
            'can_access_club': _('Customer Club Access'),
        }
    profile_permission_labels = [perm_labels.get(p.codename, p.name) for p in perms]

    return render(
        request,
        'users/profile.html',
        {
            'profile_user': user,
            'profile_org': org,
            'profile_role': role,
            'profile_role_label': profile_role_label,
            'profile_permissions': perms,
            'profile_permission_labels': profile_permission_labels,
        },
    )


@login_required
def settings_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = LanguageSettingsForm(request.POST, instance=profile)
        if form.is_valid():
            user_profile = form.save()
            # Clear the session cache to force context processor to re-calculate
            settings_key = f'user_settings_{request.user.id}'
            if settings_key in request.session:
                del request.session[settings_key]
            # Activate the new language immediately for this request
            activate(user_profile.preferred_language)
            messages.success(request, _('Language settings updated successfully.'))
            return redirect('users:settings')
    else:
        form = LanguageSettingsForm(instance=profile)

    return render(request, 'users/settings.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def user_list(request):
    users = User.objects.select_related('profile', 'profile__organization').all().order_by('-date_joined')

    selected_org = None
    organizations = []

    if request.user.is_superuser:
        organizations = list(Organization.objects.order_by('name'))
        org_id = request.GET.get('org_id')
        if org_id:
            try:
                selected_org = Organization.objects.get(id=org_id)
                users = users.filter(profile__organization_id=selected_org.id)
            except Exception:
                selected_org = None
    else:
        try:
            org = request.user.profile.organization
            if org:
                selected_org = org
                users = users.filter(profile__organization=org)
            else:
                users = User.objects.none()
        except UserProfile.DoesNotExist:
            users = User.objects.none()

        # Hierarchy: supervisors only see their direct reports (and never admins/superusers)
        try:
            role = getattr(request.user.profile, 'role', 'user')
        except Exception:
            role = 'user'

        if role == 'supervisor':
            users = users.filter(profile__supervisor=request.user).exclude(is_superuser=True).exclude(profile__role='admin')

    return render(
        request,
        'users/user_list.html',
        {
            'users': users,
            'organizations': organizations,
            'selected_org': selected_org,
        },
    )

@login_required
@user_passes_test(is_admin)
def user_create(request):
    if request.method == 'POST':
        user_form = UserCreateForm(request.POST)
        perm_form = UserPermissionsForm(request.POST)
        selected_supervisor = request.POST.get('supervisor')
        try:
            selected_supervisor = int(selected_supervisor) if selected_supervisor else None
        except Exception:
            selected_supervisor = None
        if user_form.is_valid() and perm_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()
            
            # Create profile for new user with selected language and role
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.preferred_language = user_form.cleaned_data.get('preferred_language', 'en')
            profile.role = user_form.cleaned_data.get('role', 'user')
            if request.user.is_superuser:
                profile.organization = user_form.cleaned_data.get('organization')
            else:
                try:
                    profile.organization = request.user.profile.organization
                except UserProfile.DoesNotExist:
                    profile.organization = None

            # Hierarchy assignment (only meaningful for role=user)
            selected_supervisor_id = request.POST.get('supervisor')
            profile.supervisor = None
            if profile.role == 'user':
                if request.user.is_superuser:
                    if selected_supervisor_id:
                        try:
                            candidate = User.objects.select_related('profile').get(id=int(selected_supervisor_id))
                            if (
                                getattr(candidate.profile, 'role', None) == 'supervisor'
                                and candidate.profile.organization_id == profile.organization_id
                            ):
                                profile.supervisor = candidate
                        except Exception:
                            profile.supervisor = None
                else:
                    try:
                        current_role = getattr(request.user.profile, 'role', 'user')
                    except Exception:
                        current_role = 'user'
                    if current_role == 'supervisor':
                        profile.supervisor = request.user
                    elif current_role == 'admin':
                        if selected_supervisor_id:
                            try:
                                candidate = User.objects.select_related('profile').get(id=int(selected_supervisor_id))
                                if (
                                    candidate.profile.organization_id == profile.organization_id
                                    and candidate.profile.role == 'supervisor'
                                ):
                                    profile.supervisor = candidate
                            except Exception:
                                profile.supervisor = None
            profile.save()
            
            # Update user staff status based on role
            if profile.role in ['admin', 'supervisor']:
                user.is_staff = True
                user.save()
            
            # We need the ContentType for UserProfile since that's where perms are defined
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_model(UserProfile)
            
            # Save permissions
            for field, value in perm_form.cleaned_data.items():
                if field == 'REQUIRE_PHOTO':
                    profile.require_photo = value
                    profile.save()
                    continue
                    
                if value:
                    perm_codename = field.lower()
                    try:
                        # Find the permission specifically for our model
                        permission = Permission.objects.filter(
                            codename=perm_codename,
                            content_type=content_type
                        ).first()
                        
                        if not permission:
                            # Create if missing
                            permission = Permission.objects.create(
                                codename=perm_codename,
                                name=f'Can access {perm_codename.split("_")[-1].capitalize()}',
                                content_type=content_type,
                            )
                        
                        user.user_permissions.add(permission)
                        # Also add to staff_user's group or direct perms if they are staff
                        if user.is_staff:
                            user.user_permissions.add(permission)
                    except Exception as e:
                        print(f"DEBUG: Error adding permission {perm_codename}: {e}")
            
            # CLEAR CACHE AFTER SAVING
            settings_key = f'user_settings_{user.id}'
            if settings_key in request.session:
                del request.session[settings_key]
            
            messages.success(request, _('User created successfully.'))
            return redirect('users:user_list')
    else:
        user_form = UserCreateForm()
        perm_form = UserPermissionsForm()
        selected_supervisor = None

    supervisors = User.objects.none()
    selected_org_id = None
    if request.user.is_superuser:
        try:
            selected_org = user_form.cleaned_data.get('organization') if request.method == 'POST' else None
        except Exception:
            selected_org = None
        selected_org_id = selected_org.id if selected_org else None
        supervisors = User.objects.select_related('profile').filter(profile__role='supervisor')
        supervisors = supervisors.order_by('username')
    else:
        try:
            org = request.user.profile.organization
        except Exception:
            org = None
        if org:
            selected_org_id = org.id
            supervisors = User.objects.select_related('profile').filter(profile__organization=org, profile__role='supervisor').order_by('username')

    try:
        current_role = getattr(request.user.profile, 'role', 'user')
    except Exception:
        current_role = 'user'

    can_assign_organization = request.user.is_superuser
    can_assign_supervisor = request.user.is_superuser or current_role == 'admin'

    return render(request, 'users/user_form.html', {
        'user_form': user_form,
        'perm_form': perm_form,
        'title': _('Create New User'),
        'LANGUAGES': settings.LANGUAGES,
        'ROLES': UserProfile.ROLE_CHOICES,
        'supervisors': supervisors,
        'selected_supervisor': selected_supervisor,
        'selected_org_id': selected_org_id,
        'can_assign_organization': can_assign_organization,
        'can_assign_supervisor': can_assign_supervisor,
    })

@login_required
@user_passes_test(is_admin)
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)

    if not request.user.is_superuser:
        try:
            current_org = request.user.profile.organization
        except UserProfile.DoesNotExist:
            current_org = None
        if not current_org or profile.organization_id != current_org.id:
            messages.error(request, _('You do not have permission to edit this user.'))
            return redirect('users:user_list')

    if request.method == 'POST':
        # Update basic info
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update profile language and role
        profile.preferred_language = request.POST.get('preferred_language', profile.preferred_language)
        profile.role = request.POST.get('role', profile.role)
        if request.user.is_superuser:
            selected_org_id = request.POST.get('organization')
            profile.organization = Organization.objects.filter(id=selected_org_id).first() if selected_org_id else None
        else:
            try:
                profile.organization = request.user.profile.organization
            except UserProfile.DoesNotExist:
                profile.organization = None

        # Hierarchy assignment (only meaningful for role=user)
        selected_supervisor_id = request.POST.get('supervisor')
        profile.supervisor = None
        if profile.role == 'user':
            if request.user.is_superuser:
                if selected_supervisor_id:
                    try:
                        candidate = User.objects.select_related('profile').get(id=int(selected_supervisor_id))
                        if (
                            candidate.id != user.id
                            and getattr(candidate.profile, 'role', None) == 'supervisor'
                            and candidate.profile.organization_id == profile.organization_id
                        ):
                            profile.supervisor = candidate
                    except Exception:
                        profile.supervisor = None
            else:
                try:
                    current_role = getattr(request.user.profile, 'role', 'user')
                except Exception:
                    current_role = 'user'
                if current_role == 'supervisor':
                    profile.supervisor = request.user
                elif current_role == 'admin':
                    if selected_supervisor_id:
                        try:
                            candidate = User.objects.select_related('profile').get(id=int(selected_supervisor_id))
                            if (
                                candidate.id != user.id
                                and candidate.profile.organization_id == profile.organization_id
                                and candidate.profile.role == 'supervisor'
                            ):
                                profile.supervisor = candidate
                        except Exception:
                            profile.supervisor = None

        profile.save()
        
        # Update user staff status based on role
        if profile.role in ['admin', 'supervisor']:
            user.is_staff = True
        else:
            user.is_staff = False
        user.save()
        
        perm_form = UserPermissionsForm(request.POST)
        if perm_form.is_valid():
            # Clear existing permissions and add new ones
            user.user_permissions.clear()
            
            # We need the ContentType for UserProfile since that's where perms are defined
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_model(UserProfile)
            
            for field, value in perm_form.cleaned_data.items():
                if field == 'REQUIRE_PHOTO':
                    profile.require_photo = value
                    profile.save()
                    continue

                if value:
                    perm_codename = field.lower()
                    try:
                        # Find the permission specifically for our model
                        permission = Permission.objects.filter(
                            codename=perm_codename,
                            content_type=content_type
                        ).first()
                        
                        if not permission:
                            # Create if missing
                            permission = Permission.objects.create(
                                codename=perm_codename,
                                name=f'Can access {perm_codename.split("_")[-1].capitalize()}',
                                content_type=content_type,
                            )
                        
                        user.user_permissions.add(permission)
                    except Exception as e:
                        print(f"DEBUG: Error adding permission {perm_codename}: {e}")
            
            messages.success(request, _('User updated successfully.'))
            # Clear the session cache for the edited user
            settings_key = f'user_settings_{user.id}'
            if settings_key in request.session:
                del request.session[settings_key]
            return redirect('users:user_list')
        else:
            messages.error(request, _('Please correct the errors below.'))
    else:
        perm_form = UserPermissionsForm(user=user)

    selected_org = profile.organization
    if request.user.is_superuser and request.method == 'POST':
        posted_org_id = request.POST.get('organization')
        selected_org = Organization.objects.filter(id=posted_org_id).first() if posted_org_id else None

    if request.user.is_superuser:
        organizations = Organization.objects.order_by('name')
        supervisors = User.objects.select_related('profile').filter(profile__role='supervisor')
        if selected_org:
            supervisors = supervisors.filter(profile__organization=selected_org)
        supervisors = supervisors.exclude(id=user.id).order_by('username')
    else:
        organizations = Organization.objects.none()
        supervisors = (
            User.objects.select_related('profile')
            .filter(profile__organization=profile.organization, profile__role='supervisor')
            .exclude(id=user.id)
            .order_by('username')
            if profile.organization_id
            else User.objects.none()
        )
    
    try:
        current_role = getattr(request.user.profile, 'role', 'user')
    except Exception:
        current_role = 'user'

    can_assign_organization = request.user.is_superuser
    can_assign_supervisor = request.user.is_superuser or current_role == 'admin'

    return render(request, 'users/user_form.html', {
        'edit_user': user,
        'perm_form': perm_form,
        'title': _('Edit User'),
        'LANGUAGES': settings.LANGUAGES,
        'ROLES': UserProfile.ROLE_CHOICES,
        'organizations': organizations,
        'selected_org_id': selected_org.id if selected_org else None,
        'supervisors': supervisors,
        'selected_supervisor': profile.supervisor_id,
        'can_assign_organization': can_assign_organization,
        'can_assign_supervisor': can_assign_supervisor,
    })

@login_required
@user_passes_test(is_admin)
def user_delete(request, pk):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=pk)
        try:
            target_profile = user.profile
        except UserProfile.DoesNotExist:
            target_profile = None

        if not request.user.is_superuser:
            try:
                current_org = request.user.profile.organization
            except UserProfile.DoesNotExist:
                current_org = None
            if not current_org or not target_profile or target_profile.organization_id != current_org.id:
                messages.error(request, _('You do not have permission to delete this user.'))
                return redirect('users:user_list')

        if user == request.user:
            messages.error(request, _('You cannot delete yourself.'))
        else:
            user.delete()
            messages.success(request, _('User deleted successfully.'))
    return redirect('users:user_list')


@login_required
@user_passes_test(is_superuser_only)
def user_reset_password(request, pk):
    if request.method != 'POST':
        return redirect('users:user_list')

    target_user = get_object_or_404(User, pk=pk)
    target_user.set_password(DEFAULT_RESET_PASSWORD)
    target_user.save(update_fields=['password'])

    messages.success(
        request,
        _('Password for %(username)s was reset to %(password)s. Ask the user to change it after login.')
        % {'username': target_user.username, 'password': DEFAULT_RESET_PASSWORD},
    )
    return redirect('users:user_list')
