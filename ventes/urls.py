# ==================== ventes/urls.py ====================
from django.urls import path
from . import views

app_name = 'ventes'

urlpatterns = [
    # Dashboard
    path('dashboard_vente/', views.dashboard_vendeuse, name='dashboard_vendeuse'),
    path('dashboard-responsable/', views.dashboard_responsable, name='dashboard_responsable'),
    
    # Checklists par date
    path('checklists/date/<str:date>/', views.checklists_by_date, name='checklists_by_date'),
    
    # CRUD Checklist - CHANGEMENT: uuid au lieu de int
    path('checklist/create/', views.checklist_create, name='checklist_create'),
    path('checklist/<uuid:pk>/', views.checklist_detail, name='checklist_detail'),
    path('checklist/<uuid:pk>/edit/', views.checklist_edit, name='checklist_edit'),
    path('checklist/<uuid:pk>/delete/', views.checklist_delete, name='checklist_delete'),
    path('checklist/<uuid:pk>/duplicate/', views.checklist_duplicate, name='checklist_duplicate'),
    path('item/<int:item_id>/supprimer/', views.supprimer_item_checklist, name='supprimer_item'),  # ✅ NOUVEAU

    # CRUD Objets
    path('objets/create/', views.objet_create, name='objet_create'),
    path('objets/<int:pk>/edit/', views.objet_edit, name='objet_edit'),
    path('objets/<int:pk>/delete/', views.objet_delete, name='objet_delete'),
    
    # CRUD Catégories
    path('categories/create/', views.categorie_create, name='categorie_create'),
    path('categories/<int:pk>/edit/', views.categorie_edit, name='categorie_edit'),
    path('categories/<int:pk>/delete/', views.categorie_delete, name='categorie_delete'),
    
    # CRUD Vendeuses
    path('vendeuses/create/', views.vendeuse_create, name='vendeuse_create'),
    path('vendeuses/<int:pk>/edit/', views.vendeuse_edit, name='vendeuse_edit'),
    path('vendeuses/<int:pk>/delete/', views.vendeuse_delete, name='vendeuse_delete'),
    
    # AJAX
    path('item/<int:pk>/toggle/', views.toggle_item_validation, name='toggle_item_validation'),
    path('item/<int:pk>/quantity/', views.update_item_quantity, name='update_item_quantity'),

    path('contrats/', views.contrat_list, name='contrat_list'),
    path('contrat/create/step1/', views.contrat_create_step1, name='contrat_create_step1'),
    path('contrat/create/step2/', views.contrat_create_step2, name='contrat_create_step2'),
    path('contrat/create/step3/', views.contrat_create_step3, name='contrat_create_step3'),
    path('contrat/<uuid:pk>/', views.contrat_detail, name='contrat_detail'),
    path('contrat/<uuid:pk>/edit/', views.contrat_edit, name='contrat_edit'),
    path('contrat/<uuid:pk>/delete/', views.contrat_delete, name='contrat_delete'),
    path('checklist/<uuid:checklist_id>/create-contrat/', 
         views.contrat_from_checklist, 
         name='contrat_from_checklist'),

    path('soumissions/', views.soumission_list, name='soumission_list'),
    path('soumission/create/', views.soumission_create, name='soumission_create'),
    path('soumission/<uuid:pk>/', views.soumission_detail, name='soumission_detail'),
    path('soumission/<uuid:pk>/edit/', views.soumission_edit, name='soumission_edit'),
    path('soumission/<uuid:pk>/delete/', views.soumission_delete, name='soumission_delete'),
    path('soumission/<uuid:pk>/duplicate/', views.soumission_duplicate, name='soumission_duplicate'),
    path('soumission/<uuid:pk>/envoyer/', views.soumission_envoyer, name='soumission_envoyer'),
    path('soumission/<uuid:pk>/accepter/', views.soumission_accepter, name='soumission_accepter'),
    path('soumission/<uuid:pk>/refuser/', views.soumission_refuser, name='soumission_refuser'),

    path('item/<int:item_id>/commentaire/', views.item_add_comment, name='item_add_comment'),
]