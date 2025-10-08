from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """Utilisateur personnalisé avec rôles"""
    
    ROLE_CHOICES = [
        # Livraison
        ('livreur', 'Livreur'),
        ('resp_livraison', 'Responsable Livraison'),
        
        # Ventes
        ('vendeur', 'Vendeur/Vendeuse'),
        ('resp_ventes', 'Responsable Ventes'),
        
        # Cuisine
        ('cuisinier', 'Cuisinier'),
        ('resp_dept_cuisine', 'Responsable Département Cuisine'),
        ('chef_cuisine', 'Chef Cuisine'),
        ('chef_commande', 'Chef Commande'),

        
        # Hôtel
        ('maitre_hotel', 'Maître d\'Hôtel'),
        
        # Comptabilité
        ('comptable', 'Comptable'),

        # Checklist
        ('verificateur_checklist', 'Vérificateur Checklist'),
        
        # Admin
        ('admin', 'Administrateur'),
    ]
    
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    telephone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='users/', blank=True, null=True)
    departement_cuisine = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    def get_dashboard_url(self):
        """Retourne l'URL du dashboard selon le rôle"""
        role_redirects = {
            # Livraison
            'livreur': 'livraison:dashboard_livreur',
            'resp_livraison': 'livraison:dashboard_responsable',
            
            # Ventes
            'vendeur': 'ventes:dashboard_vendeuse',
            'resp_ventes': 'ventes:dashboard_responsable',
            
            # Cuisine
            'cuisinier': 'cuisine:tableau_production',
            'resp_dept_cuisine': 'cuisine:dashboard_departement',
            'chef_cuisine': 'cuisine:dashboard_chef',
            
            # Hôtel
            'maitre_hotel': 'maitre_hotel:dashboard_maitre_hotel',
            
            # Comptabilité
            'comptable': 'comptabilite:dashboard',
            
            # Checklist
            'verificateur_checklist': 'checklist:dashboard_verificateur',
            
            # Admin
            'admin': 'admin:index',
        }
        return role_redirects.get(self.role, 'livraison:dashboard_responsable')
    
    def has_role(self, *roles):
        """Vérifie si l'utilisateur a un des rôles spécifiés"""
        return self.role in roles
    
    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'