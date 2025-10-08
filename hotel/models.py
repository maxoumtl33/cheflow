# maitre_hotel/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import uuid
from livraison.models import Livraison
from ventes.models import Checklist


class Contrat(models.Model):
    """Contrat géré par un maître d'hôtel"""
    
    STATUS_CHOICES = [
        ('planifie', 'Planifié'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_contrat = models.CharField(max_length=50, unique=True)
    nom_evenement = models.CharField(max_length=300)
    
    # Relations
    maitre_hotel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='contrats_maitre_hotel',
        limit_choices_to={'role': 'maitre_hotel'}
    )
    livraison = models.OneToOneField(
        'livraison.Livraison',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contrat'
    )
    checklist = models.OneToOneField(
        'ventes.Checklist',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contrat'
    )
    
    # Informations client
    client_nom = models.CharField(max_length=200)
    client_telephone = models.CharField(max_length=20)
    client_email = models.EmailField(blank=True)
    contact_sur_site = models.CharField(max_length=200, blank=True)
    
    # Adresse
    adresse_complete = models.TextField()
    ville = models.CharField(max_length=100, default='Montréal')
    code_postal = models.CharField(max_length=10, blank=True)
    
    # Date et heure
    date_evenement = models.DateField()
    heure_debut_prevue = models.TimeField()
    heure_fin_prevue = models.TimeField()
    
    # Déroulé de l'événement
    deroule_evenement = models.TextField(
        blank=True,
        help_text="Description détaillée du déroulement de l'événement"
    )
    
    # Informations supplémentaires
    nb_convives = models.PositiveIntegerField(default=0)
    informations_supplementaires = models.TextField(blank=True)
    instructions_speciales = models.TextField(blank=True)
    
    # Statut et suivi
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planifie')
    
    # Timestamps de début/fin réels
    heure_debut_reelle = models.DateTimeField(null=True, blank=True)
    heure_fin_reelle = models.DateTimeField(null=True, blank=True)
    
    # Rapports
    rapport_boissons = models.TextField(
        blank=True,
        help_text="Rapport sur la consommation de boissons"
    )
    notes_finales = models.TextField(
        blank=True,
        help_text="Notes et remarques à la fin du contrat"
    )
    
    # Metadata
    date_creation = models.DateTimeField(default=timezone.now)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='contrats_crees'
    )
    
    class Meta:
        ordering = ['date_evenement', 'heure_debut_prevue']
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        indexes = [
            models.Index(fields=['date_evenement', 'status']),
            models.Index(fields=['maitre_hotel', 'status']),
        ]
    
    def __str__(self):
        return f"{self.numero_contrat} - {self.nom_evenement}"
    
    def duree_reelle(self):
        """Calcule la durée réelle en heures"""
        if self.heure_debut_reelle and self.heure_fin_reelle:
            delta = self.heure_fin_reelle - self.heure_debut_reelle
            return round(delta.total_seconds() / 3600, 2)
        return None
    
    def peut_commencer(self):
        """Vérifie si le contrat peut être démarré"""
        return self.status == 'planifie'
    
    def peut_terminer(self):
        """Vérifie si le contrat peut être terminé"""
        return self.status == 'en_cours'
    
    def commencer(self):
        """Démarre le contrat"""
        if self.peut_commencer():
            self.status = 'en_cours'
            self.heure_debut_reelle = timezone.now()
            self.save()
            return True
        return False
    
    def terminer(self, notes_finales=''):
        """Termine le contrat"""
        if self.peut_terminer():
            self.status = 'termine'
            self.heure_fin_reelle = timezone.now()
            if notes_finales:
                self.notes_finales = notes_finales
            self.save()
            return True
        return False
    
    def est_complet(self):
        return self.livraison is not None and self.checklist is not None

    def forcer_liaison_complete(self):
        """
        Force la liaison avec Livraison et Checklist si elles existent
        Utile pour réparer des associations manquantes
        """
        from django.db import transaction
        
        liaisons_effectuees = []
        
        with transaction.atomic():
            # Chercher et lier la Livraison
            if not self.livraison:
                try:
                    livraison = Livraison.objects.get(
                        numero_livraison=self.numero_contrat,
                        est_recuperation=False
                    )
                    self.livraison = livraison
                    liaisons_effectuees.append('livraison')
                except Livraison.DoesNotExist:
                    pass
                except Livraison.MultipleObjectsReturned:
                    livraison = Livraison.objects.filter(
                        numero_livraison=self.numero_contrat,
                        est_recuperation=False
                    ).order_by('-date_creation').first()
                    if livraison:
                        self.livraison = livraison
                        liaisons_effectuees.append('livraison (multiple)')
            
            # Chercher et lier la Checklist
            if not self.checklist:
                try:
                    checklist = Checklist.objects.get(
                        numero_commande=self.numero_contrat
                    )
                    self.checklist = checklist
                    liaisons_effectuees.append('checklist')
                except Checklist.DoesNotExist:
                    pass
                except Checklist.MultipleObjectsReturned:
                    checklist = Checklist.objects.filter(
                        numero_commande=self.numero_contrat
                    ).order_by('-date_creation').first()
                    if checklist:
                        self.checklist = checklist
                        liaisons_effectuees.append('checklist (multiple)')
            
            # Sauvegarder si des liaisons ont été effectuées
            if liaisons_effectuees:
                self.save(update_fields=['livraison', 'checklist'])
        
        return liaisons_effectuees

    def verifier_coherence(self):
        """
        Vérifie la cohérence des données entre Contrat, Livraison et Checklist
        Retourne un dict avec les incohérences trouvées
        """
        incoherences = []
        
        if self.livraison:
            # Vérifier que le numéro correspond
            if self.livraison.numero_livraison != self.numero_contrat:
                incoherences.append({
                    'type': 'numero_mismatch',
                    'champ': 'livraison',
                    'contrat': self.numero_contrat,
                    'autre': self.livraison.numero_livraison
                })
            
            # Vérifier la date
            if self.livraison.date_livraison != self.date_evenement:
                incoherences.append({
                    'type': 'date_mismatch',
                    'champ': 'livraison',
                    'contrat': self.date_evenement,
                    'autre': self.livraison.date_livraison
                })
            
            # Vérifier que la livraison pointe bien vers ce contrat
            if hasattr(self.livraison, 'contrat') and self.livraison.contrat != self:
                incoherences.append({
                    'type': 'reverse_link_broken',
                    'champ': 'livraison'
                })
        
        if self.checklist:
            # Vérifier que le numéro correspond
            if self.checklist.numero_commande != self.numero_contrat:
                incoherences.append({
                    'type': 'numero_mismatch',
                    'champ': 'checklist',
                    'contrat': self.numero_contrat,
                    'autre': self.checklist.numero_commande
                })
            
            # Vérifier la date
            if self.checklist.date_evenement != self.date_evenement:
                incoherences.append({
                    'type': 'date_mismatch',
                    'champ': 'checklist',
                    'contrat': self.date_evenement,
                    'autre': self.checklist.date_evenement
                })
            
            # Vérifier que la checklist pointe bien vers ce contrat
            if hasattr(self.checklist, 'contrat') and self.checklist.contrat != self:
                incoherences.append({
                    'type': 'reverse_link_broken',
                    'champ': 'checklist'
                })
        
        return incoherences

    def get_statut_complet(self):
        """Retourne un statut textuel complet pour l'affichage"""
        if not self.livraison and not self.checklist:
            return "⚠️ Incomplet (aucune livraison ni checklist)"
        elif not self.livraison:
            return "⚠️ Incomplet (livraison manquante)"
        elif not self.checklist:
            return "⚠️ Incomplet (checklist manquante)"
        else:
            return "✅ Complet"

    @classmethod
    def reparer_toutes_liaisons(cls):
        """
        Méthode de classe pour réparer toutes les liaisons manquantes
        Utile après une migration ou import massif
        """
        contrats_repares = []
        
        for contrat in cls.objects.filter(
            models.Q(livraison__isnull=True) | models.Q(checklist__isnull=True)
        ):
            liaisons = contrat.forcer_liaison_complete()
            if liaisons:
                contrats_repares.append({
                    'numero': contrat.numero_contrat,
                    'liaisons': liaisons
                })
        
        return {
            'total': len(contrats_repares),
            'details': contrats_repares
        }


class PhotoContrat(models.Model):
        """Photos prises pendant l'événement (max 10)"""
        
        contrat = models.ForeignKey(
            Contrat,
            on_delete=models.CASCADE,
            related_name='photos'
        )
        image = models.ImageField(
            upload_to='contrats/%Y/%m/%d/',
            validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
        )
        legende = models.CharField(max_length=200, blank=True)
        ordre = models.PositiveIntegerField(default=0)
        
        date_ajout = models.DateTimeField(default=timezone.now)
        ajoute_par = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.SET_NULL,
            null=True
        )
        
        class Meta:
            ordering = ['ordre', 'date_ajout']
            verbose_name = 'Photo de contrat'
            verbose_name_plural = 'Photos de contrat'
        
        def __str__(self):
            return f"Photo {self.ordre} - {self.contrat.numero_contrat}"


class HistoriqueContrat(models.Model):
        """Historique des actions sur un contrat"""
        
        TYPE_ACTION_CHOICES = [
            ('creation', 'Création'),
            ('modification', 'Modification'),
            ('debut', 'Début du contrat'),
            ('fin', 'Fin du contrat'),
            ('rapport_boissons', 'Rapport boissons ajouté'),
            ('photo', 'Photo ajoutée'),
            ('annulation', 'Annulation'),
        ]
        
        contrat = models.ForeignKey(
            Contrat,
            on_delete=models.CASCADE,
            related_name='historique'
        )
        
        type_action = models.CharField(max_length=30, choices=TYPE_ACTION_CHOICES)
        description = models.TextField(blank=True)
        
        date_action = models.DateTimeField(default=timezone.now)
        effectue_par = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.SET_NULL,
            null=True
        )
        
        class Meta:
            ordering = ['-date_action']
            verbose_name = 'Historique de contrat'
            verbose_name_plural = 'Historiques de contrats'
        
        def __str__(self):
            return f"{self.get_type_action_display()} - {self.contrat.numero_contrat}"