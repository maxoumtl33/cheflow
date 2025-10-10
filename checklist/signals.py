# checklist/signals.py

from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from ventes.models import ItemChecklist, ItemChecklistHistorique

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
                    checklist=instance.checklist,  # ✅ IMPORTANT
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


@receiver(pre_delete, sender=ItemChecklist)
def create_deletion_history(sender, instance, **kwargs):
    """Crée un historique AVANT la suppression de l'item"""
    
    # ✅ Seulement si l'item avait été vérifié
    if instance.date_verification:
        try:
            # ✅ CRITIQUE: Créer l'historique AVANT la suppression
            # avec toutes les infos nécessaires
            ItemChecklistHistorique.objects.create(
                item=None,  # Sera NULL après suppression
                checklist=instance.checklist,  # ✅ OBLIGATOIRE
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