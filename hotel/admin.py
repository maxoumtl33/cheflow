# maitre_hotel/admin.py
from django.contrib import admin
from .models import Contrat, PhotoContrat, HistoriqueContrat


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = [
        'numero_contrat', 
        'nom_evenement', 
        'client_nom', 
        'date_evenement', 
        'maitre_hotel',
        'status',
        'nb_convives'
    ]
    list_filter = ['status', 'date_evenement', 'maitre_hotel']
    search_fields = [
        'numero_contrat', 
        'nom_evenement', 
        'client_nom', 
        'client_email',
        'adresse_complete'
    ]
    readonly_fields = ['date_creation', 'date_modification', 'heure_debut_reelle', 'heure_fin_reelle']
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'numero_contrat',
                'nom_evenement',
                'maitre_hotel',
                'status'
            )
        }),
        ('Client', {
            'fields': (
                'client_nom',
                'client_telephone',
                'client_email',
                'contact_sur_site'
            )
        }),
        ('Localisation', {
            'fields': (
                'adresse_complete',
                'ville',
                'code_postal'
            )
        }),
        ('Date et horaires', {
            'fields': (
                'date_evenement',
                'heure_debut_prevue',
                'heure_fin_prevue',
                'heure_debut_reelle',
                'heure_fin_reelle'
            )
        }),
        ('Détails événement', {
            'fields': (
                'nb_convives',
                'deroule_evenement',
                'informations_supplementaires'
            )
        }),
        ('Relations', {
            'fields': (
                'livraison',
                'checklist'
            )
        }),
        ('Rapports', {
            'fields': (
                'rapport_boissons',
                'notes_finales'
            )
        }),
        ('Métadonnées', {
            'fields': (
                'date_creation',
                'date_modification',
                'cree_par'
            ),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si c'est une création
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(PhotoContrat)
class PhotoContratAdmin(admin.ModelAdmin):
    list_display = ['contrat', 'legende', 'ordre', 'date_ajout', 'ajoute_par']
    list_filter = ['date_ajout', 'contrat']
    search_fields = ['contrat__numero_contrat', 'contrat__nom_evenement', 'legende']
    readonly_fields = ['date_ajout']


@admin.register(HistoriqueContrat)
class HistoriqueContratAdmin(admin.ModelAdmin):
    list_display = ['contrat', 'type_action', 'date_action', 'effectue_par']
    list_filter = ['type_action', 'date_action']
    search_fields = ['contrat__numero_contrat', 'contrat__nom_evenement', 'description']
    readonly_fields = ['date_action']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False