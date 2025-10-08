# maitre_hotel/urls.py
from django.urls import path
from . import views

app_name = 'maitre_hotel'

urlpatterns = [
    # Dashboard
    path('dashboard_maitre_hotel/', views.dashboard, name='dashboard_maitre_hotel'),
    
    # Détail contrat
    path('contrat/<uuid:contrat_id>/', views.detail_contrat, name='detail_contrat'),
    
    # Actions sur contrat
    path('contrat/<uuid:contrat_id>/commencer/', views.commencer_contrat, name='commencer_contrat'),
    path('contrat/<uuid:contrat_id>/terminer/', views.terminer_contrat, name='terminer_contrat'),
    path('contrat/<uuid:contrat_id>/rapport-boissons/', views.rapport_boissons, name='rapport_boissons'),
    
    # Photos
    path('contrat/<uuid:contrat_id>/ajouter-photo/', views.ajouter_photo, name='ajouter_photo'),
    path('photo/<int:photo_id>/supprimer/', views.supprimer_photo, name='supprimer_photo'),
    
    # API
    path('api/contrats/', views.api_contrats, name='api_contrats'),
    path('api/contrat/<uuid:contrat_id>/', views.api_detail_contrat, name='api_detail_contrat'),
    path('api/contrats-mois/', views.api_contrats_mois, name='api_contrats_mois'),
    path('api/contrat/<uuid:contrat_id>/livreurs/', views.get_livreur_info, name='api_livreurs_contrat'),
    path('api/contrat/<uuid:contrat_id>/status/', views.get_livraison_status, name='api_livraison_status'),
]