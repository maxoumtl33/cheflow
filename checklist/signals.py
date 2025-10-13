# checklist/signals.py

from django.db.models.signals import pre_save, pre_delete, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from ventes.models import ItemChecklist, ItemChecklistHistorique, Checklist

@receiver(pre_save, sender=ItemChecklist)
def detecter_modification_item(sender, instance, **kwargs):
    """Détecte les modifications de quantité et crée un historique"""
    
    # Si c'est un nouvel item (pas encore en base)
    if instance.pk is None:
        instance.modifie_depuis_verification = False
        return
    
    try:
        old_item = ItemChecklist.objects.get(pk=instance.pk)
        
        # Si la quantité a changé ET que l'item avait déjà été vérifié
        if old_item.quantite != instance.quantite:
            if old_item.date_verification:
                instance.modifie_depuis_verification = True
                instance.statut_verification = 'en_cours'
                
                # Créer un historique
                ItemChecklistHistorique.objects.create(
                    item=instance,
                    checklist=instance.checklist,
                    quantite_avant=old_item.quantite,
                    quantite_apres=instance.quantite,
                    type_modification='quantite',
                    objet_nom=instance.objet.nom,
                    objet_unite=instance.objet.unite,
                    categorie_nom=instance.objet.categorie.nom,
                    modifie_par=None
                )
            else:
                instance.modifie_depuis_verification = False
                
    except ItemChecklist.DoesNotExist:
        pass


@receiver(post_save, sender=ItemChecklist)
def update_checklist_status_on_save(sender, instance, created, **kwargs):
    """Met à jour le statut de la checklist selon les items"""
    
    checklist = instance.checklist
    
    # Recalculer automatiquement le statut
    checklist.recalculer_statut()
    checklist.save(update_fields=['status'])
    
    if created:
        print(f"✅ Checklist {checklist.numero_commande} - statut: {checklist.status} (ajout item)")
    else:
        print(f"✅ Checklist {checklist.numero_commande} - statut: {checklist.status} (modification item)")


@receiver(pre_delete, sender=ItemChecklist)
def create_deletion_history(sender, instance, **kwargs):
    """Crée un historique AVANT la suppression de l'item"""
    
    # ✅ Seulement si l'item avait été vérifié
    if instance.date_verification:
        try:
            ItemChecklistHistorique.objects.create(
                item=None,
                checklist=instance.checklist,
                quantite_avant=instance.quantite,
                quantite_apres=0,
                type_modification='suppression',
                objet_nom=instance.objet.nom,
                objet_unite=instance.objet.unite,
                categorie_nom=instance.objet.categorie.nom,
                modifie_par=None
            )
            print(f"✅ Historique de suppression créé pour {instance.objet.nom}")
        except Exception as e:
            print(f"❌ Erreur création historique suppression: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⏭️ Item '{instance.objet.nom}' jamais vérifié, pas d'historique")


@receiver(post_delete, sender=ItemChecklist)
def update_checklist_status_on_delete(sender, instance, **kwargs):
    """Met à jour le statut de la checklist quand un item est supprimé"""
    
    try:
        checklist = instance.checklist
        
        # Recalculer le statut après suppression
        checklist.recalculer_statut()
        checklist.save(update_fields=['status'])
        
        print(f"✅ Checklist {checklist.numero_commande} - statut: {checklist.status} (suppression)")
    except Checklist.DoesNotExist:
        pass


@receiver(post_save, sender=Checklist)
def initialiser_statut_checklist(sender, instance, created, **kwargs):
    """Initialise le statut à 'en_cours' lors de la création"""
    if created and instance.status != 'en_cours':
        instance.status = 'en_cours'
        instance.save(update_fields=['status'])
        print(f"✅ Nouvelle checklist {instance.numero_commande} créée avec statut 'en_cours'")