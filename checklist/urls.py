# checklist/urls.py
from django.urls import path
from . import views

app_name = 'checklist'

urlpatterns = [
    # Dashboard principal
    path('dasboard_checklist', views.dashboard_verificateur, name='dashboard_verificateur'),
    
    # Vérification de checklist
    path('verification/<uuid:checklist_id>/', views.verification_checklist, name='verification'),
    
    # Actions sur les items (AJAX)
    path('item/<int:item_id>/valider/', views.valider_item, name='valider_item'),
    path('item/<int:item_id>/modifier/', views.modifier_item, name='modifier_item'),
    
    # Finaliser la checklist
    path('checklist/<uuid:checklist_id>/finaliser/', views.finaliser_checklist, name='finaliser'),
    
    # Impressions
    path('imprimer/livraisons/', views.imprimer_livraisons, name='imprimer_livraisons'),
    path('imprimer/checklists/', views.imprimer_checklists, name='imprimer_checklists'),

    path('api/total-objets/', views.api_total_objets, name='api_total_objets'),
    path('api/update-quantite/', views.api_update_quantite, name='api_update_quantite'),
]