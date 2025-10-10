# ventes/models.py (partie Checklist)
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class CategorieObjet(models.Model):
    """Catégories pour organiser les objets de checklist"""
    nom = models.CharField(max_length=100)
    icone = models.CharField(max_length=50, blank=True, help_text="Classe FontAwesome (ex: fa-utensils)")
    couleur = models.CharField(max_length=20, default='slate', help_text="Couleur Tailwind")
    ordre = models.IntegerField(default=0)
    actif = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = 'Catégorie d\'objet'
        verbose_name_plural = 'Catégories d\'objets'
    
    def __str__(self):
        return self.nom


class ObjetChecklist(models.Model):
    """Objets disponibles pour créer des checklists"""
    nom = models.CharField(max_length=200)
    categorie = models.ForeignKey(CategorieObjet, on_delete=models.CASCADE, related_name='objets')
    description = models.TextField(blank=True)
    unite = models.CharField(max_length=50, default='unité', help_text="Ex: unité, kg, L, paire")
    quantite = models.IntegerField(default=0, help_text='Quantité en stock')
    actif = models.BooleanField(default=True)
    ordre = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['categorie', 'ordre', 'nom']
        verbose_name = 'Objet de checklist'
        verbose_name_plural = 'Objets de checklist'
    
    def __str__(self):
        return f"{self.nom} ({self.categorie.nom})"


class Checklist(models.Model):
    """Checklist créée par une vendeuse"""
    
    STATUS_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('en_attente', 'En attente de vérification'),
        ('en_cours', 'En cours de vérification'),
        ('validee', 'Validée'),
        ('incomplete', 'Incomplète'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=200)
    numero_commande = models.CharField(max_length=20, unique=True, help_text="Pour lier à une livraison")
    livraison = models.ForeignKey('livraison.Livraison', on_delete=models.SET_NULL, null=True, blank=True, related_name='checklists')

    # Relations
    creee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='checklists_creees')
    verificateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='checklists_verifiees')
    
    # Dates
    date_evenement = models.DateField()
    date_creation = models.DateTimeField(default=timezone.now)
    date_modification = models.DateTimeField(auto_now=True)
    date_verification = models.DateTimeField(null=True, blank=True)
    
    # Statut - Logique:
    # - Création: en_cours
    # - Tous validés: validee (automatique)
    # - Au moins 1 refusé: incomplete (automatique)
    # - Modification par Ventes: en_cours
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_cours')
    
    # Notes
    notes = models.TextField(blank=True)
    notes_verificateur = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date_evenement', '-date_creation']
        verbose_name = 'Checklist'
        verbose_name_plural = 'Checklists'
    
    def __str__(self):
        return f"{self.nom} - {self.date_evenement}"
    
    def dupliquer(self):
        """Créer une copie de la checklist avec tous ses items"""
        nouvelle = Checklist.objects.create(
            nom=f"{self.nom} (Copie)",
            numero_commande=f"{self.numero_commande}-COPIE",
            creee_par=self.creee_par,
            date_evenement=self.date_evenement,
            status='en_cours',
            notes=self.notes
        )
        
        # Copier tous les items
        for item in self.items.all():
            ItemChecklist.objects.create(
                checklist=nouvelle,
                objet=item.objet,
                quantite=item.quantite,
                ordre=item.ordre
            )
        
        return nouvelle
    
    def progression(self):
        """Retourne le pourcentage de complétion basé sur les items VALIDES"""
        total = self.items.count()
        if total == 0:
            return 0
        valides = self.items.filter(statut_verification='valide').count()
        return round((valides / total) * 100)
    
    def lier_livraison_automatiquement(self):
        """Lie automatiquement une livraison si le numéro de commande correspond"""
        from livraison.models import Livraison
        
        try:
            livraison = Livraison.objects.get(
                numero_livraison=self.numero_commande,
                est_recuperation=False
            )
            if not self.livraison:
                self.livraison = livraison
                self.save(update_fields=['livraison'])
                
                # Mettre à jour aussi la livraison
                if not livraison.checklist:
                    livraison.checklist = self
                    livraison.save(update_fields=['checklist'])
                return True
        except Livraison.DoesNotExist:
            pass
        return False


# ventes/models.py
class ItemChecklist(models.Model):
    """Item dans une checklist"""
    
    STATUT_VERIFICATION_CHOICES = [
        ('en_cours', 'En cours'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
    ]
    
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='items')
    objet = models.ForeignKey(ObjetChecklist, on_delete=models.PROTECT)
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    ordre = models.IntegerField(default=0)
    
    # Statut de vérification
    statut_verification = models.CharField(
        max_length=20,
        choices=STATUT_VERIFICATION_CHOICES,
        default='en_cours',
        help_text="Statut de vérification de l'item"
    )
    
    # Champs de vérification
    verifie = models.BooleanField(default=False, help_text="Synchro auto avec statut")
    date_verification = models.DateTimeField(null=True, blank=True)
    verifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Notification de modification
    modifie_depuis_verification = models.BooleanField(
        default=False, 
        help_text="Indique si l'item a été modifié par les Ventes après vérification"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Item de checklist'
        verbose_name_plural = 'Items de checklist'
    
    def __str__(self):
        return f"{self.objet.nom} x{self.quantite}"
    
    def save(self, *args, **kwargs):
        # Synchroniser verifie avec statut_verification pour compatibilité
        self.verifie = (self.statut_verification == 'valide')
        super().save(*args, **kwargs)


# ventes/models.py - Ajouter ce modèle

from django.db import models
from django.conf import settings
from django.utils import timezone


# ventes/models.py

# ventes/models.py

# ventes/models.py

class ItemChecklistHistorique(models.Model):
    """Historique des modifications d'items de checklist"""
    
    TYPE_MODIFICATION_CHOICES = [
        ('quantite', 'Quantité modifiée'),
        ('ajout', 'Item ajouté'),
        ('suppression', 'Item supprimé'),
    ]
    
    # ✅ CRITIQUE: item doit pouvoir être NULL
    item = models.ForeignKey(
        'ItemChecklist', 
        on_delete=models.SET_NULL,  # ✅ SET_NULL au lieu de CASCADE
        null=True,  # ✅ Permet NULL
        blank=True,
        related_name='historique',
        help_text="Item concerné par la modification (NULL si supprimé)"
    )
    
    # ✅ OBLIGATOIRE : Référence directe à la checklist
    checklist = models.ForeignKey(
        'Checklist',
        on_delete=models.CASCADE,
        related_name='historique_items',
        help_text="Checklist à laquelle appartient cet item"
    )
    
    # Quantités
    quantite_avant = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Quantité avant modification"
    )
    quantite_apres = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Quantité après modification"
    )
    
    # Type de modification
    type_modification = models.CharField(
        max_length=20,
        choices=TYPE_MODIFICATION_CHOICES,
        default='quantite'
    )
    
    # Métadonnées
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Utilisateur qui a fait la modification"
    )
    date_modification = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et heure de la modification"
    )
    
    # ✅ OBLIGATOIRE : Garder les infos même après suppression de l'item
    objet_nom = models.CharField(
        max_length=200,
        help_text="Nom de l'objet (sauvegardé en cas de suppression)"
    )
    objet_unite = models.CharField(
        max_length=50,
        default='unité',
        help_text="Unité de l'objet"
    )
    categorie_nom = models.CharField(
        max_length=100,
        help_text="Nom de la catégorie"
    )
    
    # Notes optionnelles
    notes = models.TextField(
        blank=True,
        help_text="Notes sur la modification"
    )
    
    class Meta:
        ordering = ['-date_modification']
        verbose_name = 'Historique de modification'
        verbose_name_plural = 'Historiques de modifications'
        indexes = [
            models.Index(fields=['checklist', '-date_modification']),
            models.Index(fields=['type_modification', '-date_modification']),
        ]
    
    def __str__(self):
        if self.type_modification == 'quantite':
            return f"{self.objet_nom}: {self.quantite_avant} → {self.quantite_apres}"
        elif self.type_modification == 'ajout':
            return f"{self.objet_nom}: Ajouté ({self.quantite_apres})"
        else:
            return f"{self.objet_nom}: Supprimé"
    
    def difference(self):
        """Retourne la différence de quantité"""
        if self.quantite_avant and self.quantite_apres:
            return float(self.quantite_apres - self.quantite_avant)
        return None