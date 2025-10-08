from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import uuid

class ModeEnvoi(models.Model):
    """Modes d'envoi (pour identifier les récupérations possibles)"""
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    couleur = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    permet_recuperation = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Mode d\'envoi'
        verbose_name_plural = 'Modes d\'envoi'
        ordering = ['nom']
    
    def __str__(self):
        return self.nom


class Livraison(models.Model):
    """Livraison principale"""
    
    PERIODE_CHOICES = [
        ('matin', 'Matin (5h-9h)'),
        ('midi', 'Midi (9h30-12h30)'),
        ('apres_midi', 'Après-midi (13h-20h)'),
    ]
    
    STATUS_CHOICES = [
        ('non_assignee', 'Non assignée'),
        ('assignee', 'Assignée'),
        ('en_cours', 'En cours'),
        ('livree', 'Livrée'),
        ('annulee', 'Annulée'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_livraison = models.CharField(max_length=50, unique=True)
    nom_evenement = models.CharField(max_length=300, blank=True)  # ← NOUVEAU
    
    # Client
    client_nom = models.CharField(max_length=200)
    client_telephone = models.CharField(max_length=20, blank=True)
    client_email = models.EmailField(blank=True)
    contact_sur_site = models.CharField(max_length=200, blank=True, verbose_name="Personne à contacter")
    
    # Adresse
    adresse_complete = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    place_id = models.CharField(max_length=200, blank=True, null=True,)  # ← NOUVEAU (Google Place ID)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, default='Montréal')
    app = models.CharField(max_length=20, blank=True, verbose_name="Appartement")
    ligne_adresse_2 = models.CharField(max_length=255, blank=True, verbose_name="Ligne adresse 2")
    
    # Timing
    date_livraison = models.DateField()
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES)
    heure_souhaitee = models.TimeField(null=True, blank=True)
    heure_livraison_reelle = models.DateTimeField(null=True, blank=True)
    
    # Détails livraison
    mode_envoi = models.ForeignKey(ModeEnvoi, on_delete=models.PROTECT, null=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nb_convives = models.PositiveIntegerField(default=0)  # ← NOUVEAU
    
    # Items spéciaux (checkboxes visuelles)
    besoin_cafe = models.BooleanField(default=False)
    besoin_the = models.BooleanField(default=False)
    besoin_sac_glace = models.BooleanField(default=False)
    besoin_part_chaud = models.BooleanField(default=False)
    autres_besoins = models.CharField(max_length=200, blank=True)
    informations_supplementaires = models.TextField(blank=True)
    

    nom_conseiller = models.CharField(max_length=100, blank=True)

    # Checklist liée
    checklist = models.ForeignKey(
        'ventes.Checklist',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='livraisons'
    )
    
    # Statut
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='non_assignee')
    
    # Notes
    instructions_speciales = models.TextField(blank=True)
    notes_internes = models.TextField(blank=True)
    
    # Récupération
    est_recuperation = models.BooleanField(default=False)
    livraison_origine = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recuperations'
    )
    
    # Validation livreur
    signature_client = models.ImageField(upload_to='signatures/', null=True, blank=True)
    nom_signataire = models.CharField(max_length=200, blank=True)
    
    # Metadata
    date_creation = models.DateTimeField(default=timezone.now)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='livraisons_creees'
    )
    date_modification = models.DateTimeField(auto_now=True)
    
    # Sync mobile
    synced_mobile = models.BooleanField(default=False)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['date_livraison', 'periode', 'heure_souhaitee']
        verbose_name = 'Livraison'
        verbose_name_plural = 'Livraisons'
        indexes = [
            models.Index(fields=['date_livraison', 'periode']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.nom_evenement or self.numero_livraison} - {self.client_nom}"
    
    def get_periode_display_time(self):
        periodes = {
            'matin': '5h-9h',
            'midi': '9h30-12h30',
            'apres_midi': '13h-20h'
        }
        return periodes.get(self.periode, '')
    
    def lier_checklist_automatiquement(self):
        """Lie automatiquement une checklist si le numéro de commande correspond"""
        from ventes.models import Checklist
        
        try:
            checklist = Checklist.objects.get(numero_commande=self.numero_livraison)
            if not self.checklist:  # Seulement si pas déjà liée
                self.checklist = checklist
                self.save(update_fields=['checklist'])
                return True
        except Checklist.DoesNotExist:
            pass
        except Checklist.MultipleObjectsReturned:
            # Prendre la plus récente si plusieurs
            checklist = Checklist.objects.filter(
                numero_commande=self.numero_livraison
            ).order_by('-date_creation').first()
            if not self.checklist:
                self.checklist = checklist
                self.save(update_fields=['checklist'])
                return True
        return False

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date


class Vehicule(models.Model):
    """
    Modèle représentant un véhicule dans le système.
    """
    
    # Choix pour le type de véhicule
    TYPE_CHOICES = [
        ('voiture', 'Voiture'),
        ('moto', 'Moto'),
        ('camion', 'Camion'),
        ('van', 'Van'),
        ('suv', 'SUV'),
    ]
    
    # Choix pour le type de carburant
    CARBURANT_CHOICES = [
        ('essence', 'Essence'),
        ('diesel', 'Diesel'),
        ('electrique', 'Électrique'),
        ('hybride', 'Hybride'),
        ('gpl', 'GPL'),
    ]
    
    # Choix pour le statut
    STATUT_CHOICES = [
        ('disponible', 'Disponible'),
        ('loue', 'Loué'),
        ('maintenance', 'En maintenance'),
        ('indisponible', 'Indisponible'),
    ]
    
    # Informations de base
    marque = models.CharField(max_length=50, verbose_name="Marque")
    modele = models.CharField(max_length=50, verbose_name="Modèle")
    annee = models.IntegerField(
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(date.today().year + 1)
        ],
        verbose_name="Année"
    )
    
    # Identification
    immatriculation = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Immatriculation"
    )
    numero_chassis = models.CharField(
        max_length=17,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Numéro de chassis (VIN)"
    )
    
    # Caractéristiques
    type_vehicule = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='voiture',
        verbose_name="Type de véhicule"
    )
    carburant = models.CharField(
        max_length=20,
        choices=CARBURANT_CHOICES,
        default='essence',
        verbose_name="Type de carburant"
    )
    couleur = models.CharField(max_length=30, verbose_name="Couleur")
    nombre_places = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        verbose_name="Nombre de places"
    )
    
    # Kilométrage
    kilometrage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Kilométrage (km)"
    )
    
    # Statut et disponibilité
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='disponible',
        verbose_name="Statut"
    )
    
    # Prix (si location)
    prix_journalier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name="Prix journalier (€)"
    )
    
    # Dates
    date_acquisition = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date d'acquisition"
    )
    date_derniere_revision = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date de dernière révision"
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    
    class Meta:
        verbose_name = "Véhicule"
        verbose_name_plural = "Véhicules"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['immatriculation']),
            models.Index(fields=['statut']),
        ]
    
    def __str__(self):
        return f"{self.marque} {self.modele} ({self.immatriculation})"
    
    def age_vehicule(self):
        """Retourne l'âge du véhicule en années."""
        return date.today().year - self.annee
    
    def est_disponible(self):
        """Vérifie si le véhicule est disponible."""
        return self.statut == 'disponible'
    
    def necessite_revision(self, intervalle_km=15000):
        """
        Vérifie si le véhicule nécessite une révision basée sur le kilométrage.
        Par défaut, tous les 15 000 km.
        """
        if not self.date_derniere_revision:
            return True
        # Cette logique peut être améliorée selon vos besoins
        return self.kilometrage % intervalle_km < 1000
from datetime import time
class Route(models.Model):
    """Route de livraison"""
    
    STATUS_CHOICES = [
        ('planifiee', 'Planifiée'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('annulee', 'Annulée'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100)
    
    date = models.DateField()
    periode = models.CharField(max_length=20, choices=Livraison.PERIODE_CHOICES)
    
    heure_depart = models.TimeField()
    @staticmethod
    def parse_heure(heure_value):
        """Convertit une string ou objet time en objet time"""
        if isinstance(heure_value, time):
            return heure_value
        
        if isinstance(heure_value, str):
            try:
                parts = heure_value.split(':')
                return time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                raise ValueError(f"Format d'heure invalide: {heure_value}")
        
        raise TypeError(f"Type non supporté pour heure: {type(heure_value)}")
    
    def save(self, *args, **kwargs):
        # Auto-parser l'heure si c'est une string
        if isinstance(self.heure_depart, str):
            self.heure_depart = self.parse_heure(self.heure_depart)
        super().save(*args, **kwargs)
    heure_retour_prevue = models.TimeField(null=True, blank=True)
    heure_retour_reelle = models.TimeField(null=True, blank=True)
    vehicule = models.ForeignKey(Vehicule, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes')
    
    livreurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        limit_choices_to={'role': 'livreur'},
        related_name='routes'
    )
    
    commentaire = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planifiee')
    
    # Ordre des livraisons (JSONField pour flexibilité)
    ordre_livraisons = models.JSONField(default=list, blank=True)
    
    # Metadata
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='routes_creees'
    )
    date_creation = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['date', 'heure_depart']
        verbose_name = 'Route'
        verbose_name_plural = 'Routes'
    
    def livraisons_livrees(self):
        """Retourne le nombre de livraisons livrées sur cette route."""
        return self.livraisonroute_set.filter(livraison__status='livree').count()
    
    def livraisons_en_cours(self):
        """Retourne le nombre de livraisons en cours sur cette route."""
        return self.livraisonroute_set.filter(livraison__status='en_cours').count()
    
    def livraisons_en_attente(self):
        """Retourne le nombre de livraisons en attente sur cette route."""
        return self.livraisonroute_set.filter(livraison__status='en_attente').count()
    
    def taux_completion(self):
        """Retourne le pourcentage de livraisons complétées."""
        total = self.livraisonroute_set.count()
        if total == 0:
            return 0
        livrees = self.livraisons_livrees()
        return round((livrees / total) * 100, 1)
    
    def verifier_completion_auto(self):
        """Vérifie si toutes les livraisons sont livrées et termine la route automatiquement"""
        if self.status != 'en_cours':
            return False
        
        # Vérifier que toutes les livraisons sont livrées
        total_livraisons = self.livraisonroute_set.count()
        livraisons_livrees = self.livraisonroute_set.filter(livraison__status='livree').count()
        
        if total_livraisons > 0 and total_livraisons == livraisons_livrees:
            self.status = 'terminee'
            self.heure_retour_reelle = timezone.now()
            self.save()
            return True
    
    def __str__(self):
        return f"{self.nom} - {self.date}"


class LivraisonRoute(models.Model):
    """Table intermédiaire pour gérer l'ordre des livraisons"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    livraison = models.ForeignKey(Livraison, on_delete=models.CASCADE)
    ordre = models.PositiveIntegerField(default=0)  # IMPORTANT pour le tri
    date_ajout = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['ordre']  # Tri par ordre
        unique_together = ['route', 'livraison']


class PhotoLivraison(models.Model):
    """Photos prises lors de la livraison"""
    
    livraison = models.ForeignKey(Livraison, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='livraisons/%Y/%m/%d/')
    legende = models.CharField(max_length=200, blank=True)
    prise_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    date_ajout = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['date_ajout']
        verbose_name = 'Photo de livraison'
        verbose_name_plural = 'Photos de livraison'


class DisponibiliteLivreur(models.Model):
    """Disponibilités des livreurs"""
    
    TYPE_CHOICES = [
        ('disponible', 'Disponible'),
        ('indisponible', 'Indisponible'),
        ('conge', 'Congé'),
        ('maladie', 'Maladie'),
    ]
    
    livreur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'livreur'},
        related_name='disponibilites'
    )
    
    date_debut = models.DateField()
    date_fin = models.DateField()
    type_dispo = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['date_debut']
        verbose_name = 'Disponibilité livreur'
        verbose_name_plural = 'Disponibilités livreurs'
    
    def __str__(self):
        return f"{self.livreur.get_full_name()} - {self.date_debut} au {self.date_fin}"


class ImportExcel(models.Model):
    """Historique des imports Excel"""
    
    fichier = models.FileField(
        upload_to='imports/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])]
    )
    
    date_import = models.DateTimeField(default=timezone.now)
    importe_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    nb_lignes_total = models.IntegerField(default=0)
    nb_lignes_importees = models.IntegerField(default=0)
    nb_erreurs = models.IntegerField(default=0)
    
    rapport_erreurs = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-date_import']
        verbose_name = 'Import Excel'
        verbose_name_plural = 'Imports Excel'


class Livreur(models.Model):
    """Modèle pour les livreurs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='livreur_profile'
    )
    telephone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.user.get_full_name() or self.user.username
    
    class Meta:
        verbose_name = "Livreur"
        verbose_name_plural = "Livreurs"