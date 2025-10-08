from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

@login_required
def redirect_to_dashboard(request):
    """Redirige l'utilisateur vers son dashboard selon son rôle"""
    dashboard_url = request.user.get_dashboard_url()
    return redirect(dashboard_url)