"""
Commande Django management pour importer les items

Placer ce fichier dans: votre_app/management/commands/import_items.py

Usage:
    python manage.py import_items Items.xlsx
    python manage.py import_items Items.xlsx --clear  # Efface les données existantes
"""

import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction
from ventes.models import ObjetChecklist, CategorieObjet


class Command(BaseCommand):
    help = 'Importe les items depuis un fichier Excel vers les modèles ObjetChecklist et CategorieObjet'

    def add_arguments(self, parser):
        parser.add_argument(
            'fichier',
            type=str,
            help='Chemin vers le fichier Excel à importer'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Efface toutes les données existantes avant l\'importation'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simule l\'importation sans modifier la base de données'
        )

    def obtenir_couleur_icone(self, nom_categorie):
        """Assigne une couleur et une icône selon la catégorie"""
        mapping = {
            'ÉQUIPEMENT DE CUISSON': ('red', 'fa-fire-burner'),
            'SANS ALCOOL': ('blue', 'fa-bottle-water'),
            'ACCESSOIRES DE DÉCOR': ('pink', 'fa-paintbrush'),
            'ÉQUIPEMENT POUR SERVICE CAFÉ': ('amber', 'fa-mug-hot'),
            'ÉQUIPEMENT DE SERVICE': ('slate', 'fa-plate-utensils'),
            'VAISSELLE': ('indigo', 'fa-plate-wheat'),
            'USTENSILES': ('orange', 'fa-utensils'),
            'MOBILIER': ('emerald', 'fa-chair'),
            'LINGE': ('cyan', 'fa-shirt'),
            'ÉLECTROMÉNAGER': ('violet', 'fa-blender'),
            'ALCOOL': ('rose', 'fa-wine-glass'),
            'RÉFRIGÉRATION': ('sky', 'fa-temperature-snow'),
            'CHAUFFAGE': ('red', 'fa-temperature-hot'),
            'ÉCLAIRAGE': ('yellow', 'fa-lightbulb'),
            'SONORISATION': ('purple', 'fa-volume-high'),
            'TRANSPORT': ('gray', 'fa-truck'),
            'SÉCURITÉ': ('green', 'fa-shield'),
        }
        
        for cle, (couleur, icone) in mapping.items():
            if cle in nom_categorie.upper():
                return couleur, icone
        
        return 'slate', 'fa-box'

    def handle(self, *args, **options):
        fichier = options['fichier']
        clear = options['clear']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODE DRY-RUN - Aucune modification ne sera effectuée'))
        
        if clear and not dry_run:
            self.stdout.write(self.style.WARNING('⚠️  Suppression des données existantes...'))
            ObjetChecklist.objects.all().delete()
            CategorieObjet.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✅ Données effacées'))
        
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
            'categories_creees': 0,
            'objets_crees': 0,
            'objets_mis_a_jour': 0,
            'erreurs': 0
        }
        
        categories_cache = {}
        
        def traiter_importation():
            for index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    nom_item = row[0]
                    quantite = row[1] or 0
                    nom_categorie_raw = row[2]
                    
                    if not nom_item or not nom_categorie_raw:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  Ligne {index}: données manquantes, ignorée')
                        )
                        continue
                    
                    nom_categorie = nom_categorie_raw.strip().title()
                    
                    # Créer ou récupérer la catégorie
                    if nom_categorie not in categories_cache:
                        couleur, icone = self.obtenir_couleur_icone(nom_categorie)
                        
                        if not dry_run:
                            categorie, created = CategorieObjet.objects.get_or_create(
                                nom=nom_categorie,
                                defaults={
                                    'icone': icone,
                                    'couleur': couleur,
                                    'ordre': len(categories_cache),
                                    'actif': True
                                }
                            )
                        else:
                            created = True
                            categorie = None
                        
                        categories_cache[nom_categorie] = categorie
                        
                        if created:
                            stats['categories_creees'] += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ Catégorie: {nom_categorie} ({couleur}, {icone})')
                            )
                    else:
                        categorie = categories_cache[nom_categorie]
                    
                    # Créer ou mettre à jour l'objet
                    if not dry_run:
                        objet, created = ObjetChecklist.objects.update_or_create(
                            nom=nom_item.strip(),
                            categorie=categorie,
                            defaults={
                                'quantite': int(quantite),
                                'unite': 'unité',
                                'actif': True,
                                'ordre': index
                            }
                        )
                    else:
                        # En dry-run, vérifier si l'objet existe
                        created = not ObjetChecklist.objects.filter(
                            nom=nom_item.strip()
                        ).exists()
                    
                    if created:
                        stats['objets_crees'] += 1
                    else:
                        stats['objets_mis_a_jour'] += 1
                    
                    if index % 50 == 0:
                        self.stdout.write(f'📊 Progression: {index} lignes traitées...')
                        
                except Exception as e:
                    stats['erreurs'] += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Erreur ligne {index}: {str(e)}')
                    )
                    continue
        
        if not dry_run:
            with transaction.atomic():
                traiter_importation()
        else:
            traiter_importation()
        
        # Afficher les statistiques
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RAPPORT D\'IMPORTATION'))
        self.stdout.write('='*50)
        self.stdout.write(f'✅ Catégories créées: {stats["categories_creees"]}')
        self.stdout.write(f'✅ Objets créés: {stats["objets_crees"]}')
        self.stdout.write(f'🔄 Objets mis à jour: {stats["objets_mis_a_jour"]}')
        self.stdout.write(self.style.ERROR(f'❌ Erreurs: {stats["erreurs"]}'))
        self.stdout.write(f'📊 Total traité: {stats["objets_crees"] + stats["objets_mis_a_jour"]}')
        self.stdout.write('='*50)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 Dry-run terminé - Aucune modification effectuée'))