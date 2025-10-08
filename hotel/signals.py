"""
Signals pour gérer l'association automatique entre Contrat, Livraison et Checklist
Fichier: hotel/signals.py
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction

from hotel.models import Contrat
from livraison.models import Livraison
from ventes.models import Checklist


# ============================================================================
# SIGNAL: Création/Modification de CONTRAT
# ============================================================================
@receiver(post_save, sender=Contrat)
def lier_contrat_livraison_checklist(sender, instance, created, **kwargs):
    """
    Quand un Contrat est créé ou modifié:
    1. Cherche une Livraison avec le même numero_contrat
    2. Cherche une Checklist avec le même numero_contrat
    3. Les associe au Contrat
    """
    if created:
        with transaction.atomic():
            # Chercher la Livraison correspondante
            try:
                livraison = Livraison.objects.select_for_update().get(
                    numero_livraison=instance.numero_contrat,
                    est_recuperation=False
                )
                # Associer la livraison au contrat
                if not instance.livraison:
                    instance.livraison = livraison
                    Contrat.objects.filter(id=instance.id).update(livraison=livraison)
                    print(f"✅ Contrat {instance.numero_contrat} → Livraison liée")
            except Livraison.DoesNotExist:
                print(f"⚠️  Contrat {instance.numero_contrat}: Aucune livraison trouvée")
            except Livraison.MultipleObjectsReturned:
                # Prendre la plus récente
                livraison = Livraison.objects.filter(
                    numero_livraison=instance.numero_contrat,
                    est_recuperation=False
                ).order_by('-date_creation').first()
                if not instance.livraison and livraison:
                    Contrat.objects.filter(id=instance.id).update(livraison=livraison)
                    print(f"✅ Contrat {instance.numero_contrat} → Livraison liée (multiple, pris le plus récent)")
            
            # Chercher la Checklist correspondante
            try:
                checklist = Checklist.objects.select_for_update().get(
                    numero_commande=instance.numero_contrat
                )
                # Associer la checklist au contrat
                if not instance.checklist:
                    instance.checklist = checklist
                    Contrat.objects.filter(id=instance.id).update(checklist=checklist)
                    print(f"✅ Contrat {instance.numero_contrat} → Checklist liée")
            except Checklist.DoesNotExist:
                print(f"⚠️  Contrat {instance.numero_contrat}: Aucune checklist trouvée")
            except Checklist.MultipleObjectsReturned:
                # Prendre la plus récente
                checklist = Checklist.objects.filter(
                    numero_commande=instance.numero_contrat
                ).order_by('-date_creation').first()
                if not instance.checklist and checklist:
                    Contrat.objects.filter(id=instance.id).update(checklist=checklist)
                    print(f"✅ Contrat {instance.numero_contrat} → Checklist liée (multiple, pris le plus récent)")


# ============================================================================
# SIGNAL: Création/Modification de CHECKLIST
# ============================================================================
@receiver(post_save, sender=Checklist)
def lier_checklist_contrat(sender, instance, created, **kwargs):
    """
    Quand une Checklist est créée ou modifiée:
    1. Cherche un Contrat avec le même numero_commande
    2. L'associe au Contrat
    3. Vérifie aussi la liaison avec la Livraison
    """
    if created or not instance.livraison:
        with transaction.atomic():
            # Lier au Contrat si existe
            try:
                contrat = Contrat.objects.select_for_update().get(
                    numero_contrat=instance.numero_commande
                )
                if not contrat.checklist:
                    contrat.checklist = instance
                    contrat.save(update_fields=['checklist'])
                    print(f"✅ Checklist {instance.numero_commande} → Contrat lié")
            except Contrat.DoesNotExist:
                pass  # Pas de contrat, c'est normal pour certaines checklists
            except Contrat.MultipleObjectsReturned:
                # Prendre le plus récent
                contrat = Contrat.objects.filter(
                    numero_contrat=instance.numero_commande
                ).order_by('-date_creation').first()
                if contrat and not contrat.checklist:
                    contrat.checklist = instance
                    contrat.save(update_fields=['checklist'])
                    print(f"✅ Checklist {instance.numero_commande} → Contrat lié (multiple)")
            
            # Appeler la méthode existante pour lier à la Livraison
            if not instance.livraison:
                instance.lier_livraison_automatiquement()


# ============================================================================
# SIGNAL: Création/Modification de LIVRAISON
# ============================================================================
@receiver(post_save, sender=Livraison)
def lier_livraison_contrat(sender, instance, created, **kwargs):
    """
    Quand une Livraison est créée ou modifiée:
    1. Cherche un Contrat avec le même numero_livraison
    2. L'associe au Contrat
    3. Vérifie aussi la liaison avec la Checklist (via méthode existante)
    """
    if created or not instance.checklist:
        with transaction.atomic():
            # Lier au Contrat si existe
            try:
                contrat = Contrat.objects.select_for_update().get(
                    numero_contrat=instance.numero_livraison
                )
                if not contrat.livraison:
                    contrat.livraison = instance
                    contrat.save(update_fields=['livraison'])
                    print(f"✅ Livraison {instance.numero_livraison} → Contrat lié")
            except Contrat.DoesNotExist:
                pass  # Pas de contrat, c'est normal pour certaines livraisons
            except Contrat.MultipleObjectsReturned:
                # Prendre le plus récent
                contrat = Contrat.objects.filter(
                    numero_contrat=instance.numero_livraison
                ).order_by('-date_creation').first()
                if contrat and not contrat.livraison:
                    contrat.livraison = instance
                    contrat.save(update_fields=['livraison'])
                    print(f"✅ Livraison {instance.numero_livraison} → Contrat lié (multiple)")
            
            # Appeler la méthode existante pour lier à la Checklist
            if not instance.checklist:
                instance.lier_checklist_automatiquement()


# ============================================================================
# VALIDATION: Empêcher la création de Contrat sans numéro
# ============================================================================
@receiver(pre_save, sender=Contrat)
def valider_contrat(sender, instance, **kwargs):
    """Valide qu'un contrat a toujours un numéro"""
    if not instance.numero_contrat:
        raise ValueError("Un contrat doit avoir un numéro de contrat")