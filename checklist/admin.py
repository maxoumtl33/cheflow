# checklist/admin.py
from django.contrib import admin
from django.core.exceptions import ValidationError
from ventes.models import CategorieObjet, ObjetChecklist, Checklist, ItemChecklist


@admin.register(CategorieObjet)
class CategorieObjetAdmin(admin.ModelAdmin):
    list_display = ['nom', 'icone', 'couleur', 'ordre', 'actif']
    list_editable = ['ordre', 'actif']
    list_filter = ['actif']
    search_fields = ['nom']
    ordering = ['ordre', 'nom']


class ObjetChecklistInline(admin.TabularInline):
    model = ObjetChecklist
    extra = 1
    fields = ['nom', 'description', 'unite', 'ordre', 'actif']


@admin.register(ObjetChecklist)
class ObjetChecklistAdmin(admin.ModelAdmin):
    list_display = ['nom', 'categorie', 'unite', 'ordre', 'actif']
    list_filter = ['categorie', 'actif']
    list_editable = ['ordre', 'actif']
    search_fields = ['nom', 'description']
    ordering = ['categorie', 'ordre', 'nom']


class ItemChecklistInline(admin.TabularInline):
    model = ItemChecklist
    extra = 0
    fields = ['objet', 'quantite', 'ordre', 'statut_verification', 'notes']
    readonly_fields = ['statut_verification', 'date_verification', 'verifie_par', 'modifie_depuis_verification']
    autocomplete_fields = ['objet']
    
    
    


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ['nom', 'numero_commande', 'date_evenement', 'status', 'creee_par', 'verificateur', 'progression_display']
    list_filter = ['status', 'date_evenement', 'date_creation']
    search_fields = ['nom', 'numero_commande', 'notes']
    readonly_fields = ['date_creation', 'date_modification', 'date_verification', 'status']
    inlines = [ItemChecklistInline]
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('nom', 'numero_commande', 'date_evenement', 'status')
        }),
        ('Relations', {
            'fields': ('creee_par', 'verificateur')
        }),
        ('Notes', {
            'fields': ('notes', 'notes_verificateur', 'livraison'),
            'classes': ('collapse',)

        }),
        ('Dates', {
            'fields': ('date_creation', 'date_modification', 'date_verification'),
            'classes': ('collapse',)
        }),
    )
    
    def progression_display(self, obj):
        return f"{obj.progression()}%"
    progression_display.short_description = 'Progression'
    
    actions = ['dupliquer_checklists']
    
    def dupliquer_checklists(self, request, queryset):
        count = 0
        for checklist in queryset:
            checklist.dupliquer()
            count += 1
        self.message_user(request, f"{count} checklist(s) dupliquée(s) avec succès.")
    dupliquer_checklists.short_description = "Dupliquer les checklists sélectionnées"


@admin.register(ItemChecklist)
class ItemChecklistAdmin(admin.ModelAdmin):
    list_display = ['objet', 'checklist', 'quantite', 'statut_verification', 'date_verification']
    list_filter = ['statut_verification', 'checklist__status', 'objet__categorie']
    search_fields = ['objet__nom', 'checklist__nom', 'notes']
    readonly_fields = ['date_verification', 'verifie', 'verifie_par', 'modifie_depuis_verification']
    
    def get_readonly_fields(self, request, obj=None):
        """Protéger quantité et objet si item validé ou refusé"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.statut_verification in ['valide', 'refuse']:
            readonly.extend(['objet', 'quantite'])
        return readonly
    
    def has_delete_permission(self, request, obj=None):
        """Empêcher la suppression d'items validés ou refusés"""
        if obj and obj.statut_verification in ['valide', 'refuse']:
            return False
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """Validation avant sauvegarde"""
        if change:  # Si modification
            try:
                old_obj = ItemChecklist.objects.get(pk=obj.pk)
                # Bloquer la modification si validé ou refusé
                if old_obj.statut_verification in ['valide', 'refuse']:
                    if old_obj.quantite != obj.quantite or old_obj.objet_id != obj.objet_id:
                        raise ValidationError(
                            "Impossible de modifier un item déjà validé ou refusé. "
                            "Contactez le vérificateur pour qu'il le remette en 'non vérifié'."
                        )
            except ItemChecklist.DoesNotExist:
                pass
        super().save_model(request, obj, form, change)