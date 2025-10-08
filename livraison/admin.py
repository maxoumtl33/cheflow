from django.contrib import admin
from .models import (
    ModeEnvoi, Livraison, Route, LivraisonRoute,
    PhotoLivraison, DisponibiliteLivreur, ImportExcel, Vehicule
)

@admin.register(ModeEnvoi)
class ModeEnvoiAdmin(admin.ModelAdmin):
    list_display = ['nom', 'permet_recuperation', 'actif']
    list_filter = ['permet_recuperation', 'actif']

@admin.register(Livraison)
class LivraisonAdmin(admin.ModelAdmin):
    list_display = ['numero_livraison', 'client_nom', 'date_livraison', 'periode', 'status']
    list_filter = ['status', 'periode', 'date_livraison', 'est_recuperation']
    search_fields = ['numero_livraison', 'client_nom', 'adresse_complete']
    date_hierarchy = 'date_livraison'

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['nom', 'date', 'periode', 'heure_depart', 'status']
    list_filter = ['status', 'periode', 'date']
    filter_horizontal = ['livreurs']

@admin.register(DisponibiliteLivreur)
class DisponibiliteLivreurAdmin(admin.ModelAdmin):
    list_display = ['livreur', 'date_debut', 'date_fin', 'type_dispo']
    list_filter = ['type_dispo', 'date_debut']

@admin.register(ImportExcel)
class ImportExcelAdmin(admin.ModelAdmin):
    list_display = ['date_import', 'importe_par', 'nb_lignes_importees', 'nb_erreurs']
    readonly_fields = ['date_import', 'nb_lignes_total', 'nb_lignes_importees', 'nb_erreurs']

@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ('immatriculation', 'marque', 'modele', 'annee', 'statut')
    list_filter = ('statut', 'type_vehicule', 'carburant')
    search_fields = ('immatriculation', 'marque', 'modele')