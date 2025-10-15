from django.urls import path
from . import views

app_name = 'livraison'

urlpatterns = [
    # ==========================================
    # API - MODES D'ENVOI & RÉCUPÉRATIONS
    # ==========================================
    path('api/modes-envoi/', views.modes_envoi_json, name='modes_envoi_json'),
    path('api/modes-envoi/creer/', views.creer_mode_envoi, name='creer_mode_envoi'),
    path('api/modes-envoi/<int:mode_id>/modifier/', views.modifier_mode_envoi, name='modifier_mode_envoi'),
    path('api/modes-envoi/<int:mode_id>/supprimer/', views.supprimer_mode_envoi, name='supprimer_mode_envoi'),
    
    path('api/livraisons-recuperables/', views.livraisons_recuperables_json, name='livraisons_recuperables_json'),
    path('api/transformer-recuperations/', views.transformer_en_recuperations, name='transformer_en_recuperations'),
    path('api/recuperations-en-cours/', views.recuperations_en_cours_json, name='recuperations_en_cours_json'),
    
    # ==========================================
    # RESPONSABLE - DASHBOARD & GESTION
    # ==========================================
    path('responsable/dashboard/', views.dashboard_responsable, name='dashboard_responsable'),
    path('responsable/import/', views.import_excel, name='import_excel'),
    
    # Gestion des livreurs
    path('responsable/livreurs/', views.gestion_livreurs, name='gestion_livreurs'),
    
    # Résumé journalier
    path('responsable/resume/', views.resume_journalier, name='resume_journalier'),
    
    # Gestion des récupérations
    path('responsable/recuperations/', views.gestion_recuperations, name='gestion_recuperations'),
    
    # Édition de livraison
    path('editer/<uuid:livraison_id>/', views.editer_livraison, name='editer_livraison'),

    path('liste/', views.liste_livraisons, name='liste_livraisons'),
    
    # ==========================================
    # API - LIVRAISONS
    # ==========================================
    path('api/livraisons/', views.livraisons_json, name='livraisons_json'),
    path('api/livraisons/<uuid:livraison_id>/besoins/', views.sauvegarder_besoins_livraison, name='sauvegarder_besoins'),
    path('api/livraisons/<uuid:livraison_id>/status/', views.changer_status_livraison, name='changer_status_livraison'),
    path('api/fusionner-livraisons/', views.fusionner_livraisons, name='fusionner_livraisons'),
    path('api/update-geocode/', views.update_geocode, name='update_geocode'),
    
    # ==========================================
    # API - ROUTES
    # ==========================================
    path('api/routes/', views.routes_json, name='routes_json'),
    path('api/routes/creer/', views.creer_route, name='creer_route'),
    path('api/routes/ajouter-livraison/', views.ajouter_livraison_route, name='ajouter_livraison_route'),
    path('api/routes/retirer-livraison/', views.retirer_livraison_route, name='retirer_livraison_route'),
    path('api/routes/<uuid:route_id>/reordonner/', views.reordonner_livraisons_route, name='reordonner_route'),
    path('api/routes/<uuid:route_id>/modifier/', views.modifier_route, name='modifier_route'),
    path('api/routes/supprimer/<uuid:route_id>/', views.supprimer_route, name='supprimer_route'),
    
    # ==========================================
    # API - LIVREURS & DISPONIBILITÉS
    # ==========================================
    path('api/livreurs/', views.livreurs_json, name='livreurs_json'),
    path('api/livreurs/creer/', views.creer_livreur, name='creer_livreur'),
    path('api/livreurs/<int:livreur_id>/', views.get_livreur_details, name='get_livreur_details'),
    path('api/livreurs/<int:livreur_id>/modifier/', views.modifier_livreur, name='modifier_livreur'),
    path('api/livreurs/<int:livreur_id>/supprimer/', views.supprimer_livreur, name='supprimer_livreur'),
    path('livreur/shift-info/', views.get_shift_info, name='get_shift_info'),
    path('api/disponibilites/', views.disponibilites_json, name='disponibilites_json'),
    path('api/disponibilites/ajouter/', views.ajouter_disponibilite, name='ajouter_disponibilite'),
    path('api/disponibilites/creer/', views.creer_disponibilite, name='creer_disponibilite'),
    path('api/disponibilites/<uuid:dispo_id>/modifier/', views.modifier_disponibilite, name='modifier_disponibilite'),
    path('api/disponibilites/<uuid:dispo_id>/supprimer/', views.supprimer_disponibilite, name='supprimer_disponibilite'),
    path('api/livreurs/<uuid:livreur_id>/disponibilites/', views.disponibilites_livreur, name='disponibilites_livreur'),
    path('api/disponibilites/date/', views.disponibilites_par_date, name='disponibilites_par_date'),
    path('api/routes/date/', views.routes_par_date, name='routes_par_date'),
    path('api/routes/month/', views.routes_du_mois, name='routes_du_mois'),
    # ==========================================
# LIVREUR - INTERFACE
# ==========================================
path('livreur/dashboard/', views.dashboard_livreur, name='dashboard_livreur'),
path('livreur/route/<uuid:route_id>/demarrer/', views.demarrer_route, name='demarrer_route'),
path('livreur/route/<uuid:route_id>/vehicule/', views.selection_vehicule, name='selection_vehicule'),
path('livreur/route/<uuid:route_id>/assigner-vehicule/', views.assigner_vehicule, name='assigner_vehicule'),
path('livreur/route/<uuid:route_id>/livraisons/', views.livraisons_route, name='livraisons_route'),
path('livreur/livraison/<uuid:livraison_id>/', views.detail_livraison, name='detail_livraison'),
path('livreur/livraison/<uuid:livraison_id>/photo/', views.prendre_photo, name='prendre_photo'),
path('livreur/livraison/<uuid:livraison_id>/signature/', views.sauvegarder_signature, name='sauvegarder_signature'),
path('livreur/livraison/<uuid:livraison_id>/livree/', views.marquer_livree, name='marquer_livree'),
path('livreur/route/<uuid:route_id>/terminer/', views.terminer_route, name='terminer_route'),
path('livreur/photo/<int:photo_id>/supprimer/', views.supprimer_photo, name='supprimer_photo'),

path('responsable/livraison/<uuid:livraison_id>/', views.detail_livraison_responsable, name='detail_livraison_responsable'),
    
    # API pour modification rapide
    path('api/livraisons/<uuid:livraison_id>/modifier/', views.modifier_livraison_responsable, name='modifier_livraison_responsable'),
    
    # API pour suppression
    path('api/livraisons/<uuid:livraison_id>/supprimer/', views.supprimer_livraison, name='supprimer_livraison'),
]