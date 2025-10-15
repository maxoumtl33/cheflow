"""
Commande Django management pour importer les soumissions

Placer ce fichier dans: votre_app/management/commands/import_soumissions.py

Usage:
    python manage.py import_soumissions soumissions_nom.xlsx
    python manage.py import_soumissions soumissions_nom.xlsx --update  # Met à jour les existantes
"""

import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from ventes.models import Soumission
from datetime import datetime

User = get_user_model()


class Command(BaseCommand):
    help = 'Importe les soumissions depuis un fichier Excel et les lie aux vendeurs'

    def add_arguments(self, parser):
        parser.add_argument(
            'fichier',
            type=str,
            help='Chemin vers le fichier Excel à importer'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Met à jour les soumissions existantes si elles existent déjà'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simule l\'importation sans modifier la base de données'
        )

    def parse_date(self, date_value):
        """Parse une date depuis différents formats"""
        if not date_value:
            return None
        
        if isinstance(date_value, datetime):
            return date_value.date()
        
        try:
            return datetime.strptime(str(date_value), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    def parse_datetime(self, datetime_value):
        """Parse un datetime depuis différents formats"""
        if not datetime_value:
            return None
        
        if isinstance(datetime_value, datetime):
            return datetime_value
        
        try:
            return datetime.strptime(str(datetime_value), '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return None

    def bool_from_string(self, value):
        """Convertit une valeur en booléen"""
        if value in [True, 1, '1', 'True', 'true', 'TRUE']:
            return True
        return False

    def get_user_by_identifier(self, user_identifier):
        """Trouve un utilisateur par nom d'utilisateur ou ID"""
        if not user_identifier:
            return None
        
        try:
            if isinstance(user_identifier, (int, float)):
                return User.objects.get(id=int(user_identifier))
            
            user_str = str(user_identifier).strip()
            return User.objects.filter(username__iexact=user_str).first()
        except User.DoesNotExist:
            return None

    def get_or_create_numero_soumission(self, index):
        """Génère un numéro de soumission unique"""
        return f"SOU-{index:05d}"

    def handle(self, *args, **options):
        fichier = options['fichier']
        update = options['update']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODE DRY-RUN - Aucune modification ne sera effectuée'))
        
        try:
            workbook = openpyxl.load_workbook(fichier)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'❌ Fichier non trouvé: {fichier}'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur lors de la lecture du fichier: {str(e)}'))
            return
        
        sheet = workbook.active
        
        stats = {
            'soumissions_creees': 0,
            'soumissions_mises_a_jour': 0,
            'erreurs': 0,
            'utilisateurs_non_trouves': set(),
        }
        
        def traiter_importation():
            for index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=1):
                try:
                    user_identifier = row[0]  # user (colonne A)
                    nom_compagnie = row[1] if len(row) > 1 else None  # company_name (colonne B)
                    adresse = row[2] if len(row) > 2 else None  # event_location (colonne C)
                    commande_par = row[3] if len(row) > 3 else None  # ordered_by (colonne D)
                    telephone = row[4] if len(row) > 4 else None  # phone (colonne E)
                    email = row[5] if len(row) > 5 else None  # email (colonne F)
                    avec_service = self.bool_from_string(row[6] if len(row) > 6 else False)  # avec_service (G)
                    avec_alcool = self.bool_from_string(row[8] if len(row) > 8 else False)  # avec_alcool (I)
                    location_materiel = self.bool_from_string(row[9] if len(row) > 9 else False)  # location_materiel (J)
                    date_evenement = self.parse_date(row[10] if len(row) > 10 else None)  # date (K)
                    nombre_personnes = row[11] if len(row) > 11 else 0  # guest_count (L)
                    created_at = self.parse_datetime(row[12] if len(row) > 12 else None)  # created_at (M)
                    updated_at = self.parse_datetime(row[13] if len(row) > 13 else None)  # updated_at (N)
                    sent_at = self.parse_datetime(row[14] if len(row) > 14 else None)  # sent_at (O)
                    status = row[17] if len(row) > 17 else 'en_cours'  # status (R)
                    
                    if not user_identifier:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  Ligne {index + 1}: utilisateur manquant, ignorée')
                        )
                        continue
                    
                    utilisateur = self.get_user_by_identifier(user_identifier)
                    if not utilisateur:
                        stats['utilisateurs_non_trouves'].add(str(user_identifier))
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  Ligne {index + 1}: Utilisateur "{user_identifier}" non trouvé'
                            )
                        )
                    
                    if not date_evenement:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  Ligne {index + 1}: date manquante, ignorée')
                        )
                        continue
                    
                    numero_soumission = self.get_or_create_numero_soumission(index)
                    
                    soumission_data = {
                        'nom_compagnie': nom_compagnie or '',
                        'adresse': adresse or '',
                        'commande_par': commande_par or '',
                        'telephone': telephone or '',
                        'email': email or '',
                        'avec_service': avec_service,
                        'avec_alcool': avec_alcool,
                        'location_materiel': location_materiel,
                        'date_evenement': date_evenement,
                        'nombre_personnes': int(nombre_personnes) if nombre_personnes else 0,
                        'statut': status if status in ['en_cours', 'envoye', 'accepte', 'refuse'] else 'en_cours',
                        'cree_par': utilisateur,
                    }
                    
                    if created_at:
                        soumission_data['cree_a'] = created_at
                    if updated_at:
                        soumission_data['date_modification'] = updated_at
                    if sent_at and status == 'envoye':
                        soumission_data['date_soumission'] = sent_at
                    
                    if not dry_run:
                        if update:
                            soumission, created = Soumission.objects.update_or_create(
                                numero_soumission=numero_soumission,
                                defaults=soumission_data
                            )
                        else:
                            try:
                                soumission = Soumission.objects.create(
                                    numero_soumission=numero_soumission,
                                    **soumission_data
                                )
                                created = True
                            except Exception:
                                created = False
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠️  Ligne {index + 1}: Soumission {numero_soumission} existe déjà'
                                    )
                                )
                                continue
                    else:
                        created = not Soumission.objects.filter(
                            numero_soumission=numero_soumission
                        ).exists()
                    
                    if created:
                        stats['soumissions_creees'] += 1
                    else:
                        stats['soumissions_mises_a_jour'] += 1
                    
                    if (index) % 50 == 0:
                        self.stdout.write(f'📊 Progression: {index} lignes traitées...')
                        
                except Exception as e:
                    stats['erreurs'] += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Erreur ligne {index + 1}: {str(e)}')
                    )
                    continue
        
        if not dry_run:
            with transaction.atomic():
                traiter_importation()
        else:
            traiter_importation()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('RAPPORT D\'IMPORTATION DES SOUMISSIONS'))
        self.stdout.write('='*60)
        self.stdout.write(f'✅ Soumissions créées: {stats["soumissions_creees"]}')
        self.stdout.write(f'🔄 Soumissions mises à jour: {stats["soumissions_mises_a_jour"]}')
        self.stdout.write(self.style.ERROR(f'❌ Erreurs: {stats["erreurs"]}'))
        self.stdout.write(f'📊 Total traité: {stats["soumissions_creees"] + stats["soumissions_mises_a_jour"]}')
        
        if stats['utilisateurs_non_trouves']:
            self.stdout.write('\n⚠️  Utilisateurs non trouvés:')
            for user_id in stats['utilisateurs_non_trouves']:
                self.stdout.write(f'   - {user_id}')
        
        self.stdout.write('='*60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 Dry-run terminé - Aucune modification effectuée'))