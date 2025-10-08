from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from hotel.models import Contrat
from livraison.models import Livraison
from ventes.models import Checklist


class Command(BaseCommand):
    help = 'Répare toutes les liaisons entre Contrats, Livraisons et Checklists'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans modifier la base de données',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affiche plus de détails',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODE DRY-RUN: Aucune modification ne sera effectuée\n'))
        
        self.stdout.write('=' * 80)
        self.stdout.write('RÉPARATION DES LIAISONS')
        self.stdout.write('=' * 80 + '\n')
        
        stats = {
            'contrats_repares': 0,
            'livraisons_liees': 0,
            'checklists_liees': 0,
            'contrats_incomplets': 0,
            'erreurs': []
        }
        
        # ========== 1. RÉPARER LES CONTRATS ==========
        self.stdout.write(self.style.HTTP_INFO('1️⃣  Réparation des Contrats...'))
        
        contrats_incomplets = Contrat.objects.filter(
            Q(livraison__isnull=True) | Q(checklist__isnull=True)
        )
        
        for contrat in contrats_incomplets:
            if verbose:
                self.stdout.write(f"  Contrat {contrat.numero_contrat}:")
            
            try:
                with transaction.atomic():
                    liaisons_avant = {
                        'livraison': contrat.livraison is not None,
                        'checklist': contrat.checklist is not None
                    }
                    
                    if not dry_run:
                        liaisons_effectuees = contrat.forcer_liaison_complete()
                    else:
                        # Simuler pour le dry-run
                        liaisons_effectuees = []
                        if not contrat.livraison:
                            if Livraison.objects.filter(
                                numero_livraison=contrat.numero_contrat,
                                est_recuperation=False
                            ).exists():
                                liaisons_effectuees.append('livraison')
                        if not contrat.checklist:
                            if Checklist.objects.filter(
                                numero_commande=contrat.numero_contrat
                            ).exists():
                                liaisons_effectuees.append('checklist')
                    
                    if liaisons_effectuees:
                        stats['contrats_repares'] += 1
                        if 'livraison' in str(liaisons_effectuees):
                            stats['livraisons_liees'] += 1
                        if 'checklist' in str(liaisons_effectuees):
                            stats['checklists_liees'] += 1
                        
                        msg = f"    ✅ Lié: {', '.join(liaisons_effectuees)}"
                        self.stdout.write(self.style.SUCCESS(msg))
                    elif verbose:
                        self.stdout.write("    ⚠️  Aucune liaison trouvée")
                        stats['contrats_incomplets'] += 1
                    
            except Exception as e:
                stats['erreurs'].append({
                    'contrat': contrat.numero_contrat,
                    'erreur': str(e)
                })
                self.stdout.write(self.style.ERROR(f"    ❌ Erreur: {str(e)}"))
        
        # ========== 2. VÉRIFIER LES LIVRAISONS ORPHELINES ==========
        self.stdout.write('\n' + self.style.HTTP_INFO('2️⃣  Vérification des Livraisons sans Checklist...'))
        
        livraisons_orphelines = Livraison.objects.filter(
            checklist__isnull=True,
            est_recuperation=False
        )
        
        for livraison in livraisons_orphelines:
            try:
                if not dry_run:
                    succes = livraison.lier_checklist_automatiquement()
                else:
                    succes = Checklist.objects.filter(
                        numero_commande=livraison.numero_livraison
                    ).exists()
                
                if succes:
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✅ Livraison {livraison.numero_livraison} → Checklist liée")
                    )
                elif verbose:
                    self.stdout.write(f"  ⚠️  Livraison {livraison.numero_livraison}: Aucune checklist trouvée")
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Livraison {livraison.numero_livraison}: {str(e)}")
                )
        
        # ========== 3. VÉRIFIER LES CHECKLISTS ORPHELINES ==========
        self.stdout.write('\n' + self.style.HTTP_INFO('3️⃣  Vérification des Checklists sans Livraison...'))
        
        checklists_orphelines = Checklist.objects.filter(livraison__isnull=True)
        
        for checklist in checklists_orphelines:
            try:
                if not dry_run:
                    succes = checklist.lier_livraison_automatiquement()
                else:
                    succes = Livraison.objects.filter(
                        numero_livraison=checklist.numero_commande,
                        est_recuperation=False
                    ).exists()
                
                if succes:
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✅ Checklist {checklist.numero_commande} → Livraison liée")
                    )
                elif verbose:
                    self.stdout.write(f"  ⚠️  Checklist {checklist.numero_commande}: Aucune livraison trouvée")
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Checklist {checklist.numero_commande}: {str(e)}")
                )
        
        # ========== RÉSUMÉ ==========
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('RÉSUMÉ'))
        self.stdout.write('=' * 80)
        self.stdout.write(f"Contrats réparés: {stats['contrats_repares']}")
        self.stdout.write(f"Livraisons liées: {stats['livraisons_liees']}")
        self.stdout.write(f"Checklists liées: {stats['checklists_liees']}")
        self.stdout.write(f"Contrats toujours incomplets: {stats['contrats_incomplets']}")
        
        if stats['erreurs']:
            self.stdout.write(self.style.ERROR(f"\nErreurs ({len(stats['erreurs'])}):"))
            for err in stats['erreurs']:
                self.stdout.write(f"  - {err['contrat']}: {err['erreur']}")
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('Exécutez sans --dry-run pour appliquer les modifications'))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('✅ Réparation terminée'))