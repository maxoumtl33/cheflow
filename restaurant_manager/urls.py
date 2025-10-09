from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from users.views import redirect_to_dashboard

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('admin/', admin.site.urls),
    path('livraison/', include('livraison.urls')),
    path('ventes/', include('ventes.urls')),
    path('checklist/', include('checklist.urls')),
    path('maitre_hotel/', include('hotel.urls')),
    path('accounts/profile/', redirect_to_dashboard, name='profile'),
]

# Ajouter les static et media files
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)