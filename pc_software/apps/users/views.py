from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from .models import UserProfile
from .forms import LanguageSettingsForm, UserCreateForm, UserPermissionsForm
from django.utils.translation import activate
from django.utils.translation import gettext as _
from django.contrib.auth.models import User, Permission
from apps.organizations.models import Organization

def is_admin(user):
    return user.is_superuser or user.is_staff

@login_required
def profile_view(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    org = getattr(profile, 'organization', None) if profile else None
    role = getattr(profile, 'role', None) if profile else None
    perms = user.user_permissions.all().order_by('name')
    return render(
        request,
        'users/profile.html',
        {
            'profile_user': user,
            'profile_org': org,
            'profile_role': role,
            'profile_permissions': perms,
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
    
    return render(request, 'users/user_form.html', {
        'user_form': user_form,
        'perm_form': perm_form,
        'title': _('Create New User'),
        'LANGUAGES': settings.LANGUAGES,
        'ROLES': UserProfile.ROLE_CHOICES
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
    
    return render(request, 'users/user_form.html', {
        'edit_user': user,
        'perm_form': perm_form,
        'title': _('Edit User'),
        'LANGUAGES': settings.LANGUAGES,
        'ROLES': UserProfile.ROLE_CHOICES
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
