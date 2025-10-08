from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps
from django.contrib import messages

def role_required(*roles):
    """
    Décorateur pour restreindre l'accès à certains rôles
    Usage: @role_required('livreur', 'resp_livraison')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if not request.user.has_role(*roles):
                messages.error(request, 'Vous n\'avez pas accès à cette page.')
                return redirect(request.user.get_dashboard_url())
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator