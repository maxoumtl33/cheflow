"""
Script d'importation des données de Submission (ancien modèle) vers Soumission (nouveau modèle)

Instructions:
1. Placer le fichier Soumissions.xlsx dans le même répertoire que ce script
2. Exécuter: python import_soumissions.py
"""

import os
import django
import pandas as pd
from datetime import datetime
from decimal import Decimal

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurant_manager.settings')
django.setup()

from ventes.models import Soumission
from django.contrib.auth import get_user_model

User = get_user_model()

def convert_boolean(value):
    """Convertit les valeurs booléennes de l'Excel"""
    if pd.isna(value) or value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'oui', 'yes']
    return bool(int(value))

def convert_date(date_str):
    """Convertit une date string en objet date"""
    if pd.isna(date_str) or date_str is None or date_str == '':
        return None
    try:
        if isinstance(date_str, str):
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        return date_str
    except Exception as e:
        print(f"Erreur conversion date: {date_str} - {e}")
        return None

def convert_datetime(datetime_str):
    """Convertit une datetime string en objet datetime"""
    if pd.isna(datetime_str) or datetime_str is None or datetime_str == '':
        return None
    try:
        if isinstance(datetime_str, str):
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        return datetime_str
    except Exception as e:
        print(f"Erreur conversion datetime: {datetime_str} - {e}")
        return None

def map_status(old_status):
    """Mappe l'ancien statut vers le nouveau"""
    status_mapping = {
        'en_cours': 'en_cours',
        'envoyé': 'envoye',
        'validé': 'accepte',
        'valide': 'accepte',
        'refusé': 'refuse',
        'refuse': 'refuse'
    }
    return status_mapping.get(old_status, 'en_cours')

def import_soumissions_from_excel(filepath):
    """Importe les soumissions depuis le fichier Excel"""
    
    # Lire le fichier Excel
    print(f"Lecture du fichier: {filepath}")
    df = pd.read_excel(filepath)
    
    print(f"Nombre total de lignes: {len(df)}")
    
    # Compteurs
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    # Obtenir l'utilisateur par défaut (premier admin ou créer un utilisateur générique)
    try:
        default_user = User.objects.filter(is_staff=True).first()
        if not default_user:
            default_user = User.objects.create_user(
                username='importation',
                email='importation@example.com',
                is_staff=False
            )
            print(f"Utilisateur par défaut créé: {default_user.username}")
    except Exception as e:
        print(f"Erreur création utilisateur: {e}")
        return
    
    # Parcourir chaque ligne
    for index, row in df.iterrows():
        try:
            # Vérifier si la ligne a des données minimales requises
            if pd.isna(row.get('company_name')) or row.get('company_name') is None:
                skipped_count += 1
                continue
            
            # Extraire et nettoyer les données
            company_name = str(row.get('company_name', '')).strip()
            event_location = str(row.get('event_location', '')).strip() if not pd.isna(row.get('event_location')) else ''
            ordered_by = str(row.get('ordered_by', '')).strip() if not pd.isna(row.get('ordered_by')) else ''
            phone = str(row.get('phone', '')).strip() if not pd.isna(row.get('phone')) else ''
            email = str(row.get('email', '')).strip() if not pd.isna(row.get('email')) else ''
            
            # Date de l'événement
            event_date = convert_date(row.get('date'))
            if not event_date:
                print(f"Ligne {index + 2}: Date manquante pour {company_name}, ligne ignorée")
                skipped_count += 1
                continue
            
            # Nombre de personnes
            guest_count = row.get('guest_count')
            if pd.isna(guest_count) or guest_count is None:
                guest_count = 0
            else:
                guest_count = int(guest_count)
            
            # Options booléennes
            avec_service = convert_boolean(row.get('avec_service', False))
            avec_alcool = convert_boolean(row.get('avec_alcool', False))
            location_materiel = convert_boolean(row.get('location_materiel', False))
            
            # Commentaire/Notes
            notes = str(row.get('commentaire', '')).strip() if not pd.isna(row.get('commentaire')) else ''
            
            # Statut
            old_status = str(row.get('status', 'en_cours')).strip()
            new_status = map_status(old_status)
            
            # Dates de création et modification
            created_at = convert_datetime(row.get('created_at'))
            date_soumission = convert_datetime(row.get('sent_at'))
            
            # Créer la nouvelle soumission
            soumission = Soumission(
                date_evenement=event_date,
                nom_compagnie=company_name,
                nombre_personnes=guest_count if guest_count > 0 else 1,
                adresse=event_location,
                avec_service=avec_service,
                location_materiel=location_materiel,
                avec_alcool=avec_alcool,
                commande_par=ordered_by if ordered_by else company_name,
                email=email if email else f"contact@{company_name.lower().replace(' ', '')}.com",
                telephone=phone if phone else '',
                statut=new_status,
                cree_par=default_user,
                notes=notes,
                date_soumission=date_soumission
            )
            
            # Définir manuellement la date de création si disponible
            if created_at:
                soumission.cree_a = created_at
            
            # Sauvegarder
            soumission.save()
            
            created_count += 1
            
            if created_count % 10 == 0:
                print(f"Progression: {created_count} soumissions créées...")
            
        except Exception as e:
            error_count += 1
            print(f"Erreur ligne {index + 2} ({company_name}): {str(e)}")
            continue
    
    # Rapport final
    print("\n" + "="*60)
    print("RAPPORT D'IMPORTATION")
    print("="*60)
    print(f"Total de lignes traitées: {len(df)}")
    print(f"Soumissions créées: {created_count}")
    print(f"Lignes ignorées (données insuffisantes): {skipped_count}")
    print(f"Erreurs: {error_count}")
    print("="*60)
    
    return created_count

if __name__ == '__main__':
    # Chemin du fichier Excel
    excel_file = 'Soumissions.xlsx'
    
    if not os.path.exists(excel_file):
        print(f"Erreur: Le fichier '{excel_file}' n'existe pas.")
        print("Veuillez placer le fichier Soumissions.xlsx dans le même répertoire que ce script.")
    else:
        # Confirmation avant import
        response = input(f"Êtes-vous sûr de vouloir importer les données de '{excel_file}'? (oui/non): ")
        
        if response.lower() in ['oui', 'yes', 'o', 'y']:
            print("\nDébut de l'importation...")
            count = import_soumissions_from_excel(excel_file)
            print(f"\nImportation terminée! {count} soumissions créées.")
        else:
            print("Importation annulée.")