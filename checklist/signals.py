# checklist/signals.py - VERSION COMPLÈTE

from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from ventes.models import ItemChecklist, Checklist, ItemChecklistHistorique


@receiver(pre_save, sender=ItemChecklist)
def track_item_changes(sender, instance, **kwargs):
    """Détecter les changements sur UN item spécifique et créer l'historique"""
    
    if instance.pk:  # Modification d'un item existant
        try:
            old_item = ItemChecklist.objects.get(pk=instance.pk)
            
            # Détecter les changements de quantité ou d'objet
            quantite_changed = old_item.quantite != instance.quantite
            objet_changed = old_item.objet_id != instance.objet_id
            
            # Si modification de quantité ou objet SUR CET ITEM UNIQUEMENT
            if quantite_changed or objet_changed:
                # Repasser CET item en "en_cours"
                instance.statut_verification = 'en_cours'
                instance.verifie = False
                instance.modifie_depuis_verification = True
                instance.date_verification = None
                instance.verifie_par = None
                
        except ItemChecklist.DoesNotExist:
            pass
    else:
        # Nouvel item créé
        instance.statut_verification = 'en_cours'
        instance.verifie = False
        instance.modifie_depuis_verification = True


@receiver(post_save, sender=ItemChecklist)
def create_item_history(sender, instance, created, **kwargs):
    """Créer un enregistrement d'historique après sauvegarde"""
    
    if created:
        # Nouvel item ajouté
        ItemChecklistHistorique.objects.create(
            item=instance,
            quantite_apres=instance.quantite,
            type_modification='ajout',
            notes=f"Item ajouté à la checklist"
        )
    else:
        # Item modifié - vérifier si la quantité a changé
        # On récupère la quantité avant depuis la base de données
        try:
            old_item = ItemChecklist.objects.get(pk=instance.pk)
            # Cette vérification se fait APRÈS le save, donc on compare avec l'historique
            dernier_historique = instance.historique.first()
            
            if dernier_historique:
                # Si la dernière quantité enregistrée est différente
                if float(dernier_historique.quantite_apres) != float(instance.quantite):
                    ItemChecklistHistorique.objects.create(
                        item=instance,
                        quantite_avant=dernier_historique.quantite_apres,
                        quantite_apres=instance.quantite,
                        type_modification='quantite',
                        notes=f"Quantité modifiée"
                    )
        except ItemChecklist.DoesNotExist:
            pass
    
    # Recalculer le statut de la checklist
    recalculer_statut_checklist(instance.checklist)


@receiver(pre_delete, sender=ItemChecklist)
def create_deletion_history(sender, instance, **kwargs):
    """Enregistrer la suppression dans l'historique avant de supprimer"""
    
    # Créer un historique de suppression
    ItemChecklistHistorique.objects.create(
        item=instance,
        quantite_avant=instance.quantite,
        quantite_apres=0,
        type_modification='suppression',
        notes=f"Item supprimé de la checklist"
    )


@receiver(post_delete, sender=ItemChecklist)
def update_checklist_status_on_item_delete(sender, instance, **kwargs):
    """Mettre à jour le statut de la checklist après suppression d'un item"""
    
    checklist = instance.checklist
    recalculer_statut_checklist(checklist)


def recalculer_statut_checklist(checklist):
    """
    Logique de calcul du statut de la checklist:
    - Si 1 ou plusieurs objets "refuse" -> checklist "incomplete"
    - Si 1 ou plusieurs objets "en_cours" -> checklist "en_cours"
    - Si tous objets "valide" -> checklist "validee"
    - Si aucun objet -> checklist "en_cours"
    """
    
    items = checklist.items.all()
    total_items = items.count()
    
    if total_items == 0:
        nouveau_statut = 'en_cours'
    else:
        # Compter les statuts
        items_refuses = items.filter(statut_verification='refuse').count()
        items_en_cours = items.filter(statut_verification='en_cours').count()
        items_valides = items.filter(statut_verification='valide').count()
        
        # Appliquer la logique
        if items_refuses > 0:
            nouveau_statut = 'incomplete'
        elif items_en_cours > 0:
            nouveau_statut = 'en_cours'
        elif items_valides == total_items:
            nouveau_statut = 'validee'
        else:
            nouveau_statut = 'en_cours'
    
    if checklist.status != nouveau_statut:
        checklist.status = nouveau_statut
        checklist.save(update_fields=['status'])