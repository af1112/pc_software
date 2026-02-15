def user_settings(request):
    if request.user.is_authenticated:
        # Check session first to avoid DB hit every time
        settings_key = f'user_settings_{request.user.id}'
        cached_settings = request.session.get(settings_key)
        
        if cached_settings:
            # Safety: drop legacy cache that mistakenly stored model instances
            try:
                if isinstance(cached_settings, dict) and 'organization' in cached_settings:
                    del request.session[settings_key]
                else:
                    # Invalidate cache if org settings changed
                    try:
                        org = request.user.profile.organization
                        org_updated_at = org.updated_at.isoformat() if org and getattr(org, 'updated_at', None) else None
                    except Exception:
                        org_updated_at = None

                    if cached_settings.get('org_updated_at') == org_updated_at:
                        return cached_settings
                    del request.session[settings_key]
            except Exception:
                del request.session[settings_key]
            
        if hasattr(request.user, 'profile'):
            try:
                profile = request.user.profile
                org = profile.organization
                role = getattr(profile, 'role', 'user')
                role_is_manager = role in ['admin', 'supervisor']
                settings_data = {
                    'user_currency_code': profile.currency_code,
                    'user_currency_symbol': profile.currency_symbol,
                    'user_decimal_places': profile.currency_decimal_places,
                    'org_name': org.name if org else 'AKAF',
                    'org_logo': org.logo.url if org and org.logo else None,
                    'org_id': org.id if org else None,
                    'org_updated_at': org.updated_at.isoformat() if org and getattr(org, 'updated_at', None) else None,
                    # IMPORTANT: Do not store model instances in session cache
                    # Only keep primitive values to avoid JSON serialization errors
                    # Access logic: 
                    # 1. Superuser has access to everything
                    # 2. Regular user: (Organization allows OR no organization) AND (User has direct permission)
                    'can_use_expenses': request.user.is_superuser or ((org.can_use_expenses if org else True) and request.user.has_perm('users.can_access_expenses')),
                    'can_use_ticketing': request.user.is_superuser or ((org.can_use_ticketing if org else True) and request.user.has_perm('users.can_access_ticketing')),
                    'can_use_attendance': request.user.is_superuser or ((org.can_use_attendance if org else True) and request.user.has_perm('users.can_access_attendance')),
                    'can_use_personnel': request.user.is_superuser or ((getattr(org, 'can_use_personnel', True) if org else True) and (role_is_manager or request.user.has_perm('users.can_access_personnel'))),
                    'can_use_projects': request.user.is_superuser or ((org.can_use_projects if org else True) and request.user.has_perm('users.can_access_projects')),
                    'can_use_dms': request.user.is_superuser or ((org.can_use_dms if org else True) and request.user.has_perm('users.can_access_dms')),
                    'can_use_ai': request.user.is_superuser or ((org.can_use_ai if org else True) and request.user.has_perm('users.can_access_ai')),
                    'can_use_menu': request.user.is_superuser or ((org.can_use_menu if org else True) and request.user.has_perm('users.can_access_menu')),
                    'can_use_club': request.user.is_superuser or ((org.can_use_club if org else True) and request.user.has_perm('users.can_access_club')),
                }
            except Exception:
                # Fallback if DB column doesn't exist yet
                settings_data = {
                    'user_currency_code': 'OMR',
                    'user_currency_symbol': 'ر.ع.',
                    'user_decimal_places': 3,
                    'org_name': 'AKAF',
                    'org_logo': None,
                    'org_id': None,
                    'org_updated_at': None,
                    'can_use_expenses': False,
                    'can_use_ticketing': False,
                    'can_use_attendance': False,
                    'can_use_personnel': False,
                    'can_use_projects': False,
                    'can_use_dms': False,
                    'can_use_ai': False,
                    'can_use_menu': False,
                    'can_use_club': False,
                }
            
            # Cache in session
            request.session[settings_key] = settings_data
            return settings_data
            
    return {
        'user_currency_code': 'OMR',
        'user_currency_symbol': 'ر.ع.',
        'user_decimal_places': 3,
        'can_use_personnel': False,
    }
