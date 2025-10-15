from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Livraison, ImportExcel
from .services import ExcelImportService
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings


@login_required
def dashboard_responsable(request):
    """Dashboard principal du responsable livraison"""
    
    # Date sélectionnée (par défaut aujourd'hui)
    date_selectionnee = request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
    date_obj = datetime.strptime(date_selectionnee, '%Y-%m-%d').date()
    
    # Statistiques du jour
    livraisons_jour = Livraison.objects.filter(date_livraison=date_obj)
    
    stats = {
        'total': livraisons_jour.count(),
        'non_assignees': livraisons_jour.filter(status='non_assignee').count(),
        'assignees': livraisons_jour.filter(status='assignee').count(),
        'en_cours': livraisons_jour.filter(status='en_cours').count(),
        'livrees': livraisons_jour.filter(status='livree').count(),
    }
    
    # Livraisons par période
    livraisons_matin = livraisons_jour.filter(periode='matin')
    livraisons_midi = livraisons_jour.filter(periode='midi')
    livraisons_apres_midi = livraisons_jour.filter(periode='apres_midi')
    
    context = {
        'date_selectionnee': date_selectionnee,
        'stats': stats,
        'livraisons_matin': livraisons_matin,
        'livraisons_midi': livraisons_midi,
        'livraisons_apres_midi': livraisons_apres_midi,
    }
    
    return render(request, 'livraison/responsable/dashboard.html', context)

from .forms import ExcelUploadForm

# Dans votre views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, date
import json


@login_required
def import_excel(request):
    """Vue pour importer les livraisons depuis Excel"""
    print("=== IMPORT EXCEL VIEW APPELÉE ===")
    print(f"Méthode: {request.method}")
    
    if request.method == 'POST':
        print("POST détecté")
        print(f"FILES: {request.FILES}")
        print(f"POST data: {request.POST}")
        print("POST détecté")
        print(f"FILES: {request.FILES}")
        print(f"POST data: {request.POST}")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        print(f"Est AJAX: {is_ajax}")
        
        # Récupérer le fichier
        fichier = request.FILES.get('fichier_excel') or request.FILES.get('fichier')
        print(f"Fichier récupéré: {fichier}")
        
        if not fichier:
            print("ERREUR: Aucun fichier")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Aucun fichier fourni'
                }, status=400)
            messages.error(request, 'Aucun fichier fourni')
            return redirect('livraison:import_excel')
        
        print(f"Nom du fichier: {fichier.name}")
        
        # Récupérer la date de livraison
        date_livraison_str = request.POST.get('date_livraison')
        print(f"Date reçue (string): {date_livraison_str}")
        
        if not date_livraison_str:
            print("ERREUR: Aucune date fournie")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Aucune date de livraison fournie'
                }, status=400)
            messages.error(request, 'Veuillez sélectionner une date de livraison')
            return redirect('livraison:import_excel')
        
        # Parser la date
        try:
            date_livraison = datetime.strptime(date_livraison_str, '%Y-%m-%d').date()
            print(f"Date parsée: {date_livraison}")
        except ValueError as e:
            print(f"ERREUR: Format de date invalide - {e}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Format de date invalide'
                }, status=400)
            messages.error(request, 'Format de date invalide')
            return redirect('livraison:import_excel')
        
        # Vérifier que la date n'est pas dans le passé (optionnel - vous pouvez retirer cette vérification)
        if date_livraison < date.today():
            print(f"AVERTISSEMENT: Date dans le passé ({date_livraison})")
            # Note: On peut autoriser les imports dans le passé si nécessaire
            # Si vous voulez bloquer, décommentez ci-dessous:
            # if is_ajax:
            #     return JsonResponse({
            #         'success': False,
            #         'error': 'La date de livraison ne peut pas être dans le passé'
            #     }, status=400)
            # messages.error(request, 'La date de livraison ne peut pas être dans le passé')
            # return redirect('livraison:import_excel')
        
        try:
            print("Création du service...")
            service = ExcelImportService()
            
            print(f"Début de l'import pour le {date_livraison}...")
            resultat = service.importer(fichier, date_livraison=date_livraison)
            print(f"Résultat: {resultat}")
            
            if resultat['success']:
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'livraisons_creees': resultat['imported'],
                        'livraisons_mises_a_jour': resultat['updated'],
                        'livraisons_inchangees': resultat['skipped'],
                        'total': resultat['imported'] + resultat['updated'] + resultat['skipped'],
                        'erreurs': len(resultat['errors']),
                        'geocoding_failed': resultat['geocoding_failed'],
                        'date_livraison': date_livraison.strftime('%Y-%m-%d')
                    })
                
                # Message de succès
                message = f"✅ Import réussi pour le {date_livraison.strftime('%d/%m/%Y')} : "
                message += f"{resultat['imported']} créées, "
                message += f"{resultat['updated']} mises à jour, "
                message += f"{resultat['skipped']} inchangées"
                
                if resultat['geocoding_failed']:
                    message += f" | ⚠️ {len(resultat['geocoding_failed'])} non géocodées"
                
                messages.success(request, message)
                return redirect('livraison:dashboard_responsable')
            else:
                # Erreur
                error_msg = resultat.get('error', 'Erreur inconnue')
                print(f"ERREUR lors de l'import: {error_msg}")
                
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_msg
                    }, status=500)
                
                messages.error(request, f"Erreur lors de l'import : {error_msg}")
                return redirect('livraison:import_excel')
        
        except Exception as e:
            print(f"EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
            
            messages.error(request, f"Erreur : {str(e)}")
            return redirect('livraison:import_excel')
    
    # GET - Afficher le formulaire
    print("GET request - affichage du formulaire")
    
    context = {
        'date_aujourd_hui': date.today().isoformat(),
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        'imports_recents': ImportExcel.objects.order_by('-date_import')[:10]
    }
    
    return render(request, 'livraison/responsable/import_excel.html', context)

@login_required
def livraisons_json(request):
    """API JSON pour récupérer les livraisons (pour la carte)"""
    
    date = request.GET.get('date')
    periode = request.GET.get('periode')
    
    livraisons = Livraison.objects.filter(status='non_assignee')
    
    if date:
        livraisons = livraisons.filter(date_livraison=date)
    
    if periode:
        livraisons = livraisons.filter(periode=periode)
    
    data = []
    for liv in livraisons:
        data.append({
            'id': str(liv.id),
            'numero': liv.numero_livraison,
            'nom_evenement': liv.nom_evenement,
            'client': liv.client_nom,
            'adresse': liv.adresse_complete,
            'latitude': float(liv.latitude) if liv.latitude else None,
            'longitude': float(liv.longitude) if liv.longitude else None,
            'heure': liv.heure_souhaitee.strftime('%H:%M') if liv.heure_souhaitee else '',
            'periode': liv.get_periode_display(),
            'mode_envoi': liv.mode_envoi.nom if liv.mode_envoi else '',
            'nb_convives': liv.nb_convives,
            'informations_supplementaires': liv.informations_supplementaires,  # NOUVEAU
            'cafe': liv.besoin_cafe,
            'the': liv.besoin_the,
            'glace': liv.besoin_sac_glace,
            'chaud': liv.besoin_part_chaud,
            'est_recuperation': liv.est_recuperation,
        })
    
    return JsonResponse({'livraisons': data})


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Route, Livraison, LivraisonRoute
from users.models import CustomUser

@login_required
@require_http_methods(["POST"])
def creer_route(request):
    """Version simplifiée avec auto-parsing"""
    try:
        data = json.loads(request.body)
        
        route = Route.objects.create(
            nom=data['nom'],
            date=data['date'],
            periode=data['periode'],
            heure_depart=data['heure_depart'],
            commentaire=data.get('commentaire', ''),
            cree_par=request.user
        )
        
        if data.get('livreurs'):
            livreurs = CustomUser.objects.filter(
                id__in=data['livreurs'],
                role__in=['livreur', 'resp_livraison']  # ← CORRECTION ICI
            )
            route.livreurs.set(livreurs)
        
        return JsonResponse({
            'success': True,
            'route': {
                'id': str(route.id),
                'nom': route.nom,
                'heure_depart': route.heure_depart.strftime('%H:%M'),
                'livreurs': [
                    {'id': l.id, 'nom': l.get_full_name() or l.username} 
                    for l in route.livreurs.all()
                ],
                'commentaire': route.commentaire,
                'livraisons': []
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
from django.db import models
@login_required
@require_http_methods(["POST"])
def ajouter_livraison_route(request):
    """Ajouter une livraison à une route avec position"""
    try:
        data = json.loads(request.body)
        
        route = Route.objects.get(id=data['route_id'])
        livraison = Livraison.objects.get(id=data['livraison_id'])
        position = data.get('position')  # 🔥 NOUVEAU
        
        # Vérifier si pas déjà assignée
        if livraison.status != 'non_assignee':
            return JsonResponse({
                'success': False, 
                'error': 'Livraison déjà assignée'
            }, status=400)
        
        # 🔥 Si position spécifiée, décaler les autres
        if position is not None:
            # Décaler toutes les livraisons après cette position
            LivraisonRoute.objects.filter(
                route=route,
                ordre__gte=position
            ).update(ordre=models.F('ordre') + 1)
            
            ordre = position
        else:
            # Ajouter à la fin
            ordre = LivraisonRoute.objects.filter(route=route).count()
        
        # Créer l'association
        LivraisonRoute.objects.create(
            livraison=livraison,
            route=route,
            ordre=ordre
        )
        
        # Mettre à jour le statut
        livraison.status = 'assignee'
        livraison.save()
        
        # 🔥 Retourner TOUTES les livraisons de la route dans l'ordre
        livraisons_route = LivraisonRoute.objects.filter(
            route=route
        ).select_related('livraison').order_by('ordre')
        
        livraisons_data = []
        for lr in livraisons_route:
            liv = lr.livraison
            livraisons_data.append({
                'id': str(liv.id),
                'numero': liv.numero_livraison,
                'nom_evenement': liv.nom_evenement,
                'client': liv.client_nom,
                'adresse': liv.adresse_complete,
                'heure': liv.heure_souhaitee.strftime('%H:%M') if liv.heure_souhaitee else '',
                'cafe': liv.besoin_cafe,
                'the': liv.besoin_the,
                'glace': liv.besoin_sac_glace,
                'chaud': liv.besoin_part_chaud,
                'est_recuperation': liv.est_recuperation,
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Livraison ajoutée à la route',
            'livraisons': livraisons_data  # 🔥 Toutes les livraisons
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def retirer_livraison_route(request):
    """Retirer une livraison d'une route"""
    try:
        data = json.loads(request.body)
        
        livraison = Livraison.objects.get(id=data['livraison_id'])
        
        # Supprimer l'association
        LivraisonRoute.objects.filter(livraison=livraison).delete()
        
        # Remettre en non assignée
        livraison.status = 'non_assignee'
        livraison.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Livraison retirée de la route'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def reordonner_livraisons_route(request, route_id):
    """Réordonner les livraisons dans une route"""
    try:
        data = json.loads(request.body)
        ordre_livraisons = data.get('ordre', [])  # Liste d'IDs dans l'ordre
        
        route = Route.objects.get(id=route_id)
        
        # Mettre à jour l'ordre
        for index, livraison_id in enumerate(ordre_livraisons):
            LivraisonRoute.objects.filter(
                route=route,
                livraison_id=livraison_id
            ).update(ordre=index)
        
        # 🔥 NOUVEAU : Retourner les livraisons dans le bon ordre
        livraisons_route = LivraisonRoute.objects.filter(
            route=route
        ).select_related('livraison').order_by('ordre')
        
        livraisons_data = []
        for lr in livraisons_route:
            liv = lr.livraison
            livraisons_data.append({
                'id': str(liv.id),
                'numero': liv.numero_livraison,
                'nom_evenement': liv.nom_evenement,
                'client': liv.client_nom,
                'adresse': liv.adresse_complete,
                'heure': liv.heure_souhaitee.strftime('%H:%M') if liv.heure_souhaitee else '',
                'cafe': liv.besoin_cafe,
                'the': liv.besoin_the,
                'glace': liv.besoin_sac_glace,
                'chaud': liv.besoin_part_chaud,
                'est_recuperation': liv.est_recuperation,
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Ordre mis à jour',
            'livraisons': livraisons_data  # 🔥 Retourner les livraisons
        })
        
    except Route.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Route introuvable'
        }, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def routes_json(request):
    """Récupérer toutes les routes pour une date/période"""
    
    date = request.GET.get('date')
    periode = request.GET.get('periode')
    
    routes = Route.objects.all()
    
    if date:
        routes = routes.filter(date=date)
    if periode:
        routes = routes.filter(periode=periode)
    
    data = []
    for route in routes:
        livraisons_route = LivraisonRoute.objects.filter(
            route=route
        ).select_related('livraison').order_by('ordre')
        
        livraisons_data = []
        for lr in livraisons_route:
            liv = lr.livraison
            livraisons_data.append({
                'id': str(liv.id),
                'numero': liv.numero_livraison,
                'nom_evenement': liv.nom_evenement,  # ← NOUVEAU
                'client': liv.client_nom,
                'adresse': liv.adresse_complete,
                'heure': liv.heure_souhaitee.strftime('%H:%M') if liv.heure_souhaitee else '',
                'mode_envoi': liv.mode_envoi.nom if liv.mode_envoi else '',
                'nb_convives': liv.nb_convives,  # ← NOUVEAU
                'informations_supplementaires': liv.informations_supplementaires,
                'cafe': liv.besoin_cafe,
                'the': liv.besoin_the,
                'glace': liv.besoin_sac_glace,
                'chaud': liv.besoin_part_chaud,
            })
        
        data.append({
            'id': str(route.id),
            'nom': route.nom,
            'heure_depart': route.heure_depart.strftime('%H:%M'),
            'livreurs': [l.get_full_name() for l in route.livreurs.all()],
            'livreurs_ids': [l.id for l in route.livreurs.all()],
            'commentaire': route.commentaire,
            'status': route.status,
            'livraisons': livraisons_data
        })
    
    return JsonResponse({'routes': data})

@login_required
def livreurs_json(request):
    """Liste des livreurs disponibles"""
    
    livreurs = CustomUser.objects.filter(
        role__in=['livreur', 'resp_livraison'],  # ← CORRECTION ICI
        is_active=True
    )
    
    data = [{
        'id': l.id,
        'nom': l.get_full_name(),
        'username': l.username
    } for l in livreurs]
    
    return JsonResponse({'livreurs': data})

import re
from django.db import transaction

@login_required
@require_http_methods(["POST"])
def fusionner_livraisons(request):
    """Fusionner plusieurs livraisons avec logique de priorité et regroupement intelligent des noms"""
    try:
        data = json.loads(request.body)
        livraison_ids = data.get('livraison_ids', [])
        
        if len(livraison_ids) < 2:
            return JsonResponse({
                'success': False,
                'error': 'Sélectionnez au moins 2 livraisons'
            }, status=400)
        
        # Récupérer les livraisons
        livraisons = list(Livraison.objects.filter(
            id__in=livraison_ids,
            status='non_assignee'
        ).select_related('mode_envoi', 'checklist').order_by('date_creation'))
        
        if len(livraisons) != len(livraison_ids):
            return JsonResponse({
                'success': False,
                'error': 'Certaines livraisons sont déjà assignées ou introuvables'
            }, status=400)
        
        # ========================================
        # ÉTAPE 1: Déterminer la livraison principale selon la hiérarchie
        # ========================================
        livraison_principale = determiner_livraison_principale(livraisons)
        autres_livraisons = [l for l in livraisons if l.id != livraison_principale.id]
        
        # ========================================
        # ÉTAPE 2: Générer le nom fusionné intelligent
        # ========================================
        nom_fusionne = generer_nom_fusionne([l.nom_evenement for l in livraisons])
        
        # ========================================
        # ÉTAPE 3: Fusionner les données
        # ========================================
        with transaction.atomic():
            # Collecter les modes d'envoi uniques
            modes_envoi = []
            total_convives = 0
            
            for liv in livraisons:
                if liv.mode_envoi:
                    mode_nom = liv.mode_envoi.nom
                    if mode_nom not in modes_envoi:
                        modes_envoi.append(mode_nom)
                total_convives += liv.nb_convives
            
            # Mettre à jour la livraison principale
            notes = livraison_principale.notes_internes or ''
            if notes:
                notes += '\n\n'
            notes += f"═══ FUSION DE {len(livraisons)} LIVRAISONS ═══\n"
            notes += f"Date fusion: {timezone.now().strftime('%Y-%m-%d %H:%M')}\n"
            notes += f"Modes d'envoi: {' + '.join(modes_envoi)}\n"
            notes += f"Total convives: {total_convives}\n"
            notes += "\nLivraisons fusionnées:\n"
            
            for liv in livraisons:
                notes += f"  • {liv.numero_livraison} - {liv.nom_evenement}\n"
            
            livraison_principale.nom_evenement = nom_fusionne
            livraison_principale.notes_internes = notes
            livraison_principale.nb_convives = total_convives
            livraison_principale.save()
            
            # Supprimer les autres livraisons
            for liv in autres_livraisons:
                liv.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{len(livraisons)} livraisons fusionnées',
            'livraison_id': str(livraison_principale.id),
            'nom_evenement': nom_fusionne
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def determiner_livraison_principale(livraisons):
    """
    Détermine quelle livraison doit devenir la principale selon la hiérarchie:
    1. Checklist + Mode récupérable
    2. Checklist seule
    3. Mode récupérable seul
    4. Première livraison
    """
    
    # Niveau 1: Checklist + Mode récupérable
    for liv in livraisons:
        if (liv.checklist and 
            liv.mode_envoi and 
            liv.mode_envoi.permet_recuperation):
            print(f"✅ Principale (Checklist + Récup): {liv.numero_livraison}")
            return liv
    
    # Niveau 2: Checklist seule
    for liv in livraisons:
        if liv.checklist:
            print(f"✅ Principale (Checklist): {liv.numero_livraison}")
            return liv
    
    # Niveau 3: Mode récupérable seul
    for liv in livraisons:
        if liv.mode_envoi and liv.mode_envoi.permet_recuperation:
            print(f"✅ Principale (Récup): {liv.numero_livraison}")
            return liv
    
    # Niveau 4: Première livraison
    print(f"✅ Principale (Première): {livraisons[0].numero_livraison}")
    return livraisons[0]


def generer_nom_fusionne(noms_evenements):
    """
    Génère un nom fusionné intelligent.
    
    Exemples:
    - ["Sandrine Lima 1", "Sandrine Lima 1.1", "Sandrine Lima 1.3"] 
      -> "Sandrine Lima 1+1.1+1.3 @ZONE 9"
    
    - ["Louigi 2.1 @ZONE 5", "Louigi 2.2 @ZONE 5"]
      -> "Louigi 2.1+2.2 @ZONE 5"
    
    - ["Marie 1", "Marie 2", "Marie 3"]
      -> "Marie 1+2+3"
    """
    
    if not noms_evenements:
        return ''
    
    # Pattern: "Nom Base + Numéro (+ sous-numéro optionnel) + Zone optionnelle"
    # Ex: "Sandrine Lima 1.1 @ZONE 9"
    pattern = r'^(.+?)\s+(\d+)(?:\.(\d+))?\s*(@.+)?$'
    
    parsed = []
    nom_base = ''
    zone = ''
    
    for nom in noms_evenements:
        if not nom:
            continue
            
        match = re.match(pattern, nom.strip())
        
        if match:
            base, numero_principal, sous_numero, zone_match = match.groups()
            
            if not nom_base:
                nom_base = base.strip()
            
            if zone_match and not zone:
                zone = zone_match.strip()
            
            # Stocker le numéro complet
            if sous_numero:
                parsed.append(f"{numero_principal}.{sous_numero}")
            else:
                parsed.append(numero_principal)
        else:
            # Si le pattern ne match pas, utiliser tel quel
            if not nom_base:
                nom_base = nom.strip()
    
    if not parsed:
        # Aucun pattern trouvé -> concaténer simplement
        return ' + '.join(noms_evenements)
    
    # Construire le nom final
    numeros_fusionnes = '+'.join(parsed)
    
    result = f"{nom_base} {numeros_fusionnes}"
    
    if zone:
        result += f" {zone}"
    
    return result.strip()

@login_required
@require_http_methods(["DELETE"])
def supprimer_route(request, route_id):
    """Supprimer une route et remettre les livraisons en non assignées"""
    try:
        route = Route.objects.get(id=route_id)
        
        # Récupérer toutes les livraisons de cette route
        livraisons_route = LivraisonRoute.objects.filter(route=route)
        
        # Remettre chaque livraison en non assignée
        for lr in livraisons_route:
            lr.livraison.status = 'non_assignee'
            lr.livraison.save()
        
        # Supprimer la route (cascade supprimera LivraisonRoute)
        route.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Route supprimée'
        })
        
    except Route.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Route introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def sauvegarder_besoins_livraison(request, livraison_id):
    """Sauvegarder les besoins spéciaux d'une livraison + nom d'événement"""
    try:
        livraison = Livraison.objects.get(id=livraison_id)
        data = json.loads(request.body)
        
        # ✨ NOUVEAU: Modifier le nom d'événement
        if 'nom_evenement' in data:
            livraison.nom_evenement = data['nom_evenement'].strip()
        
        # MODIFIER L'HEURE
        if data.get('heure'):
            try:
                from datetime import datetime
                heure_obj = datetime.strptime(data['heure'], '%H:%M').time()
                livraison.heure_souhaitee = heure_obj
                
                # Recalculer la période
                if heure_obj < datetime.strptime('09:30', '%H:%M').time():
                    livraison.periode = 'matin'
                elif heure_obj < datetime.strptime('13:00', '%H:%M').time():
                    livraison.periode = 'midi'
                else:
                    livraison.periode = 'apres_midi'
            except:
                pass
        
        # INFORMATIONS SUPPLÉMENTAIRES
        livraison.informations_supplementaires = data.get('informations_supplementaires', '')
        
        # Mettre à jour les besoins
        livraison.besoin_cafe = data.get('cafe', False)
        livraison.besoin_the = data.get('the', False)
        livraison.besoin_sac_glace = data.get('glace', False)
        livraison.besoin_part_chaud = data.get('chaud', False)
        
        # Stocker les détails dans autres_besoins (JSON)
        details = {}
        if data.get('cafe'):
            details['cafe'] = {
                'type': data.get('cafe_type'),
                'quantite': data.get('cafe_quantite')
            }
        if data.get('the'):
            details['the'] = {
                'type': data.get('the_type'),
                'quantite': data.get('the_quantite')
            }
        if data.get('glace'):
            details['glace'] = {
                'quantite': data.get('glace_quantite')
            }
        if data.get('checklist'):
            details['checklist'] = {
                'notes': data.get('checklist_notes')
            }
        
        livraison.autres_besoins = json.dumps(details)
        livraison.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Informations sauvegardées',
            'nom_evenement': livraison.nom_evenement  # ✨ Retourner le nouveau nom
        })
        
    except Livraison.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Livraison introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@require_http_methods(["POST"])
def reordonner_livraisons_route(request, route_id):
    """Réordonner les livraisons dans une route"""
    try:
        data = json.loads(request.body)
        ordre_livraisons = data.get('ordre', [])  # Liste d'IDs dans l'ordre
        
        route = Route.objects.get(id=route_id)
        
        # Mettre à jour l'ordre
        for index, livraison_id in enumerate(ordre_livraisons):
            LivraisonRoute.objects.filter(
                route=route,
                livraison_id=livraison_id
            ).update(ordre=index)
        
        return JsonResponse({
            'success': True,
            'message': 'Ordre mis à jour'
        })
        
    except Route.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Route introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
from django.db.models import Prefetch
@login_required
def get_routes(request):
    """Récupérer les routes avec livraisons TRIÉES par ordre"""
    date_str = request.GET.get('date')
    periode = request.GET.get('periode', 'matin')
    
    if date_str:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        date_obj = timezone.now().date()
    
    routes = Route.objects.filter(
        date=date_obj,
        periode=periode
    ).prefetch_related(
        Prefetch(
            'livraisonroute_set',
            queryset=LivraisonRoute.objects.select_related('livraison').order_by('ordre')
        )
    )
    
    routes_data = []
    for route in routes:
        livraisons_route = []
        for lr in route.livraisonroute_set.all():  # Déjà trié par ordre
            liv = lr.livraison
            livraisons_route.append({
                'id': str(liv.id),
                'numero': liv.numero_livraison,
                'nom_evenement': liv.nom_evenement,
                'client': liv.client_nom,
                'adresse': liv.adresse_complete,
                'heure': liv.heure_souhaitee.strftime('%H:%M') if liv.heure_souhaitee else '',
                'cafe': liv.besoin_cafe,
                'the': liv.besoin_the,
                'glace': liv.besoin_sac_glace,
                'chaud': liv.besoin_part_chaud,
            })
        
        routes_data.append({
            'id': str(route.id),
            'nom': route.nom,
            'heure_depart': route.heure_depart.strftime('%H:%M') if route.heure_depart else '',
            'livreurs': [l.get_full_name() for l in route.livreurs.all()],
            'commentaire': route.commentaire,
            'livraisons': livraisons_route  # Déjà dans le bon ordre
        })
    
    return JsonResponse({'routes': routes_data})

@login_required
@require_http_methods(["PUT"])
def modifier_route(request, route_id):
    """Modifier une route existante"""
    try:
        route = Route.objects.get(id=route_id)
        data = json.loads(request.body)
        
        # Mettre à jour les champs
        route.nom = data.get('nom', route.nom)
        route.commentaire = data.get('commentaire', route.commentaire)
        
        if data.get('heure_depart'):
            from datetime import datetime
            route.heure_depart = datetime.strptime(data['heure_depart'], '%H:%M').time()
        
        route.save()
        
        # Mettre à jour les livreurs
        if data.get('livreurs'):
            livreurs = CustomUser.objects.filter(
                id__in=data['livreurs'],
                role__in=['livreur', 'resp_livraison']  # ← CORRECTION ICI
            )
            route.livreurs.set(livreurs)
        
        return JsonResponse({
            'success': True,
            'message': 'Route modifiée'
        })
        
    except Route.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Route introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q, Prefetch
from datetime import datetime, timedelta
from django.utils import timezone
import json

from .models import (
    Livraison, Route, LivraisonRoute, DisponibiliteLivreur, 
    ModeEnvoi
)
from users.models import CustomUser

def getCookie(name):
    """Helper pour récupérer CSRF token côté serveur si nécessaire"""
    pass

# ==========================================
# GESTION DES LIVREURS - CRUD
# ==========================================

@login_required
@require_http_methods(["POST"])
def creer_livreur(request):
    """Créer un nouveau livreur"""
    try:
        data = json.loads(request.body)
        
        # Validation
        if CustomUser.objects.filter(username=data['username']).exists():
            return JsonResponse({
                'success': False,
                'error': 'Ce nom d\'utilisateur existe déjà'
            }, status=400)
        
        if len(data['password']) < 8:
            return JsonResponse({
                'success': False,
                'error': 'Le mot de passe doit contenir au moins 8 caractères'
            }, status=400)
        
        # Créer l'utilisateur
        livreur = CustomUser.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email', ''),
            role='livreur',
            is_active=True
        )
        
        # Créer le profil livreur si vous avez un modèle Livreur séparé
        from .models import Livreur
        Livreur.objects.create(
            user=livreur,
            telephone=data.get('telephone', '')
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Livreur créé avec succès',
            'livreur_id': livreur.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def creer_livreur(request):
    """Créer un nouveau livreur"""
    try:
        data = json.loads(request.body)
        
        # Validation
        if CustomUser.objects.filter(username=data['username']).exists():
            return JsonResponse({
                'success': False,
                'error': 'Ce nom d\'utilisateur existe déjà'
            }, status=400)
        
        if len(data['password']) < 8:
            return JsonResponse({
                'success': False,
                'error': 'Le mot de passe doit contenir au moins 8 caractères'
            }, status=400)
        
        # Déterminer le rôle (par défaut 'livreur')
        role = data.get('role', 'livreur')
        if role not in ['livreur', 'resp_livraison']:
            role = 'livreur'
        
        # Créer l'utilisateur
        livreur = CustomUser.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email', ''),
            role=role,  # ← CORRECTION ICI
            is_active=True
        )
        
        # Créer le profil livreur si vous avez un modèle Livreur séparé
        from .models import Livreur
        Livreur.objects.create(
            user=livreur,
            telephone=data.get('telephone', '')
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Livreur créé avec succès',
            'livreur_id': livreur.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_livreur_details(request, livreur_id):
    """Récupérer les détails d'un livreur"""
    try:
        livreur = CustomUser.objects.get(
            id=livreur_id, 
            role__in=['livreur', 'resp_livraison']  # ← CORRECTION ICI
        )
        
        # Récupérer le profil livreur
        try:
            from .models import Livreur
            profil = Livreur.objects.get(user=livreur)
            telephone = profil.telephone
        except:
            telephone = ''
        
        return JsonResponse({
            'id': livreur.id,
            'username': livreur.username,
            'first_name': livreur.first_name,
            'last_name': livreur.last_name,
            'email': livreur.email,
            'telephone': telephone,
            'is_active': livreur.is_active,
            'role': livreur.role,
            'role_display': livreur.get_role_display()
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Livreur introuvable'
        }, status=404)

@login_required
@require_http_methods(["PUT"])
def modifier_livreur(request, livreur_id):
    """Modifier un livreur existant"""
    try:
        data = json.loads(request.body)
        livreur = CustomUser.objects.get(
            id=livreur_id, 
            role__in=['livreur', 'resp_livraison']  # ← CORRECTION ICI
        )
        
        # Vérifier si le username est déjà utilisé par un autre utilisateur
        if data['username'] != livreur.username:
            if CustomUser.objects.filter(username=data['username']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Ce nom d\'utilisateur existe déjà'
                }, status=400)
        
        # Mettre à jour les champs
        livreur.username = data['username']
        livreur.first_name = data['first_name']
        livreur.last_name = data['last_name']
        livreur.email = data.get('email', '')
        livreur.is_active = data.get('is_active', True)
        
        # Changer le mot de passe si demandé
        if data.get('change_password') and data.get('new_password'):
            if len(data['new_password']) < 8:
                return JsonResponse({
                    'success': False,
                    'error': 'Le mot de passe doit contenir au moins 8 caractères'
                }, status=400)
            livreur.set_password(data['new_password'])
        
        livreur.save()
        
        # Mettre à jour le profil livreur
        try:
            from .models import Livreur
            profil, created = Livreur.objects.get_or_create(user=livreur)
            profil.telephone = data.get('telephone', '')
            profil.save()
        except:
            pass
        
        return JsonResponse({
            'success': True,
            'message': 'Livreur modifié avec succès'
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Livreur introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["DELETE"])
def supprimer_livreur(request, livreur_id):
    """Supprimer un livreur"""
    try:
        livreur = CustomUser.objects.get(
            id=livreur_id, 
            role__in=['livreur', 'resp_livraison']  # ← CORRECTION ICI
        )
        
        # Vérifier qu'il n'a pas de routes actives
        routes_actives = Route.objects.filter(
            livreurs=livreur,
            status__in=['planifiee', 'en_cours']
        ).count()
        
        if routes_actives > 0:
            return JsonResponse({
                'success': False,
                'error': f'Impossible de supprimer ce livreur car il a {routes_actives} route(s) active(s)'
            }, status=400)
        
        # Supprimer
        livreur.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Livreur supprimé avec succès'
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Livreur introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)



# GESTION DES LIVREURS
# ==========================================

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch
from datetime import datetime, timedelta
from django.utils import timezone
from users.models import CustomUser
from .models import DisponibiliteLivreur, Route, LivraisonRoute

@login_required
def gestion_livreurs(request):
    """Page de gestion des livreurs et leurs disponibilités avec routes organisées"""
    
    # Récupérer tous les livreurs
    livreurs = CustomUser.objects.filter(
        role__in=['livreur', 'resp_livraison']
    ).prefetch_related(
        Prefetch(
            'disponibilites',
            queryset=DisponibiliteLivreur.objects.filter(
                date_fin__gte=timezone.now().date()
            ).order_by('date_debut')
        )
    ).annotate(
        routes_actives=Count(
            'routes',
            filter=Q(routes__status__in=['planifiee', 'en_cours'])
        )
    ).order_by('first_name', 'last_name')
    
    # Semaine courante pour le planning
    aujourd_hui = timezone.now().date()
    debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    
    # Générer les 14 prochains jours
    jours_planning = []
    for i in range(14):
        jour = debut_semaine + timedelta(days=i)
        jours_planning.append(jour)
    
    # Récupérer les routes des 14 prochains jours organisées par date et période
    routes_par_date = {}
    for jour in jours_planning:
        routes_jour = Route.objects.filter(
            date=jour
        ).select_related(
            'vehicule'
        ).prefetch_related(
            'livreurs',
            Prefetch(
                'livraisonroute_set',
                queryset=LivraisonRoute.objects.select_related('livraison').order_by('ordre')
            )
        ).order_by('periode', 'heure_depart')
        
        # Organiser par période
        routes_par_periode = {
            'matin': [],
            'midi': [],
            'apres_midi': []
        }
        
        for route in routes_jour:
            # Compter les récupérations
            nb_recuperations = route.livraisonroute_set.filter(
                livraison__est_recuperation=True
            ).count()
            
            route_data = {
                'id': str(route.id),
                'nom': route.nom,
                'heure_depart': route.heure_depart.strftime('%H:%M') if route.heure_depart else '',
                'status': route.status,
                'status_display': route.get_status_display(),
                'livreurs': [
                    {
                        'id': l.id,
                        'nom': l.get_full_name() or l.username,
                        'initiales': f"{l.first_name[0] if l.first_name else ''}{l.last_name[0] if l.last_name else ''}".upper()
                    }
                    for l in route.livreurs.all()
                ],
                'nb_livraisons': route.livraisonroute_set.count(),
                'nb_recuperations': nb_recuperations,
                'vehicule': f"{route.vehicule.marque} {route.vehicule.modele}" if route.vehicule else None
            }
            
            routes_par_periode[route.periode].append(route_data)
        
        routes_par_date[jour.strftime('%Y-%m-%d')] = routes_par_periode
    
    context = {
        'livreurs': livreurs,
        'jours_planning': jours_planning,
        'aujourd_hui': aujourd_hui,
        'routes_par_date': routes_par_date,
    }
    
    return render(request, 'livraison/responsable/gestion_livreurs.html', context)

@login_required
@require_http_methods(["POST"])
def ajouter_disponibilite(request):
    """Ajouter une disponibilité pour un livreur avec heure de shift optionnelle"""
    try:
        data = json.loads(request.body)
        livreur = CustomUser.objects.get(
            id=data['livreur_id'], 
            role__in=['livreur', 'resp_livraison']  # ← CORRECTION ICI
        )
        
        # ✨ Gérer l'heure de début de shift
        heure_debut_shift = None
        if data.get('heure_debut_shift'):
            try:
                from datetime import datetime
                heure_debut_shift = datetime.strptime(data['heure_debut_shift'], '%H:%M').time()
            except:
                pass
        
        dispo = DisponibiliteLivreur.objects.create(
            livreur=livreur,
            date_debut=data['date_debut'],
            date_fin=data['date_fin'],
            type_dispo=data['type_dispo'],
            heure_debut_shift=heure_debut_shift,
            notes=data.get('notes', '')
        )
        
        return JsonResponse({
            'success': True,
            'disponibilite': {
                'id': str(dispo.id),
                'date_debut': str(dispo.date_debut),
                'date_fin': str(dispo.date_fin),
                'type_dispo': dispo.type_dispo,
                'type_display': dispo.get_type_dispo_display(),
                'heure_debut_shift': dispo.heure_debut_shift.strftime('%H:%M') if dispo.heure_debut_shift else None,
                'notes': dispo.notes
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["DELETE"])
def supprimer_disponibilite(request, dispo_id):
    """Supprimer une disponibilité"""
    try:
        dispo = DisponibiliteLivreur.objects.get(id=dispo_id)
        dispo.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Disponibilité supprimée'
        })
        
    except DisponibiliteLivreur.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Disponibilité introuvable'
        }, status=404)


@login_required
def disponibilites_json(request):
    """API pour récupérer les disponibilités avec heures de shift"""
    livreur_id = request.GET.get('livreur_id')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    dispos = DisponibiliteLivreur.objects.select_related('livreur')
    
    if livreur_id:
        dispos = dispos.filter(livreur_id=livreur_id)
    if date_debut:
        dispos = dispos.filter(date_fin__gte=date_debut)
    if date_fin:
        dispos = dispos.filter(date_debut__lte=date_fin)
    
    data = []
    for dispo in dispos:
        data.append({
            'id': str(dispo.id),
            'livreur_id': dispo.livreur.id,
            'livreur_nom': dispo.livreur.get_full_name(),
            'date_debut': dispo.date_debut.strftime('%Y-%m-%d'),
            'date_fin': dispo.date_fin.strftime('%Y-%m-%d'),
            'type_dispo': dispo.type_dispo,
            'type_display': dispo.get_type_dispo_display(),
            'heure_debut_shift': dispo.heure_debut_shift.strftime('%H:%M') if dispo.heure_debut_shift else None,
            'notes': dispo.notes
        })
    
    return JsonResponse({'disponibilites': data})

# ==========================================
# RÉSUMÉ JOURNALIER
# ==========================================

@login_required
def resume_journalier(request):
    """Dashboard de résumé des livraisons par jour"""
    
    # Date sélectionnée
    date_str = request.GET.get('date', timezone.now().strftime('%Y-%m-%d'))
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Récupérer toutes les livraisons du jour
    livraisons = Livraison.objects.filter(
        date_livraison=date_obj
    ).select_related(
        'mode_envoi'
    ).prefetch_related(
        'livraisonroute_set__route__livreurs'
    ).order_by('heure_souhaitee')
    
    # Stats globales
    stats = {
        'total': livraisons.count(),
        'non_assignee': livraisons.filter(status='non_assignee').count(),
        'assignee': livraisons.filter(status='assignee').count(),
        'en_cours': livraisons.filter(status='en_cours').count(),
        'livree': livraisons.filter(status='livree').count(),
        'annulee': livraisons.filter(status='annulee').count(),
    }
    
    # Pourcentage de progression
    if stats['total'] > 0:
        stats['progression'] = int((stats['livree'] / stats['total']) * 100)
    else:
        stats['progression'] = 0
    
    # Grouper par route
    routes = Route.objects.filter(
        date=date_obj
    ).prefetch_related(
        Prefetch(
            'livraisonroute_set',
            queryset=LivraisonRoute.objects.select_related('livraison').order_by('ordre')
        ),
        'livreurs'
    ).order_by('periode', 'heure_depart')
    
    context = {
        'date_selectionnee': date_str,
        'date_obj': date_obj,
        'livraisons': livraisons,
        'stats': stats,
        'routes': routes,
    }
    
    return render(request, 'livraison/responsable/resume_journalier.html', context)


# ==========================================
# ÉDITION DE LIVRAISON
# ==========================================

@login_required
def editer_livraison(request, livraison_id):
    """Page d'édition complète d'une livraison"""
    
    livraison = get_object_or_404(Livraison, id=livraison_id)
    
    if request.method == 'POST':
        try:
            # Client
            livraison.client_nom = request.POST.get('client_nom')
            livraison.client_telephone = request.POST.get('client_telephone', '')
            livraison.client_email = request.POST.get('client_email', '')
            livraison.contact_sur_site = request.POST.get('contact_sur_site', '')
            
            # Adresse
            livraison.adresse_complete = request.POST.get('adresse_complete')
            livraison.ville = request.POST.get('ville', '')
            livraison.code_postal = request.POST.get('code_postal', '')
            livraison.app = request.POST.get('app', '')
            livraison.ligne_adresse_2 = request.POST.get('ligne_adresse_2', '')
            
            # Date et heure
            livraison.date_livraison = request.POST.get('date_livraison')
            
            heure_str = request.POST.get('heure_souhaitee')
            if heure_str:
                livraison.heure_souhaitee = datetime.strptime(heure_str, '%H:%M').time()
                
                # Recalculer période
                heure = livraison.heure_souhaitee
                if heure < datetime.strptime('09:30', '%H:%M').time():
                    livraison.periode = 'matin'
                elif heure < datetime.strptime('13:00', '%H:%M').time():
                    livraison.periode = 'midi'
                else:
                    livraison.periode = 'apres_midi'
            
            # Mode envoi
            mode_envoi_id = request.POST.get('mode_envoi')
            if mode_envoi_id:
                livraison.mode_envoi = ModeEnvoi.objects.get(id=mode_envoi_id)
            
            # Détails
            livraison.nom_evenement = request.POST.get('nom_evenement', '')
            livraison.nb_convives = int(request.POST.get('nb_convives', 0))
            livraison.montant = float(request.POST.get('montant', 0))
            
            # Besoins
            livraison.besoin_cafe = request.POST.get('besoin_cafe') == 'on'
            livraison.besoin_the = request.POST.get('besoin_the') == 'on'
            livraison.besoin_sac_glace = request.POST.get('besoin_sac_glace') == 'on'
            livraison.besoin_part_chaud = request.POST.get('besoin_part_chaud') == 'on'
            
            # Notes
            livraison.informations_supplementaires = request.POST.get('informations_supplementaires', '')
            livraison.instructions_speciales = request.POST.get('instructions_speciales', '')
            livraison.notes_internes = request.POST.get('notes_internes', '')
            
            livraison.save()
            
            messages.success(request, '✅ Livraison mise à jour avec succès')
            return redirect('livraison:resume_journalier') + f'?date={livraison.date_livraison}'
            
        except Exception as e:
            messages.error(request, f'❌ Erreur : {str(e)}')
    
    # GET - Afficher le formulaire
    modes_envoi = ModeEnvoi.objects.filter(actif=True)
    
    context = {
        'livraison': livraison,
        'modes_envoi': modes_envoi,
    }
    
    return render(request, 'livraison/responsable/editer_livraison.html', context)


@login_required
@require_http_methods(["POST"])
def changer_status_livraison(request, livraison_id):
    """Changer le statut d'une livraison"""
    try:
        data = json.loads(request.body)
        livraison = Livraison.objects.get(id=livraison_id)
        
        nouveau_status = data.get('status')
        
        if nouveau_status not in dict(Livraison.STATUS_CHOICES):
            return JsonResponse({
                'success': False,
                'error': 'Statut invalide'
            }, status=400)
        
        livraison.status = nouveau_status
        
        # Si marquée comme livrée, enregistrer l'heure
        if nouveau_status == 'livree' and not livraison.heure_livraison_reelle:
            livraison.heure_livraison_reelle = timezone.now()
        
        livraison.save()
        
        return JsonResponse({
            'success': True,
            'status': livraison.status,
            'status_display': livraison.get_status_display()
        })
        
    except Livraison.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Livraison introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime
from django.utils import timezone
import json
from django.db import transaction
import shutil
import os

@login_required
def recuperations_en_cours_json(request):
    """API pour récupérer toutes les récupérations en cours"""
    
    # Récupérations non encore livrées
    recuperations = Livraison.objects.filter(
        est_recuperation=True,
        status__in=['non_assignee', 'assignee', 'en_cours']
    ).select_related(
        'mode_envoi',
        'livraison_origine'
    ).prefetch_related(
        'livraisonroute_set__route__livreurs'
    ).order_by('date_livraison', 'heure_souhaitee')
    
    print(f"DEBUG: {recuperations.count()} récupérations en cours trouvées")
    
    data = []
    for recup in recuperations:
        # Récupérer la route si assignée
        route_info = None
        lr = recup.livraisonroute_set.first()
        if lr:
            route_info = {
                'nom': lr.route.nom,
                'livreurs': [l.get_full_name() for l in lr.route.livreurs.all()],
                'heure_depart': lr.route.heure_depart.strftime('%H:%M') if lr.route.heure_depart else ''
            }
        
        data.append({
            'id': str(recup.id),
            'numero': recup.numero_livraison,
            'nom_evenement': recup.nom_evenement,
            'client': recup.client_nom,
            'adresse': recup.adresse_complete,
            'date_livraison': str(recup.date_livraison),
            'heure': recup.heure_souhaitee.strftime('%H:%M') if recup.heure_souhaitee else '',
            'periode': recup.get_periode_display(),
            'status': recup.status,
            'status_display': recup.get_status_display(),
            'mode_envoi': recup.mode_envoi.nom if recup.mode_envoi else '',
            'nb_convives': recup.nb_convives,
            'route': route_info,
            'livraison_origine': {
                'numero': recup.livraison_origine.numero_livraison if recup.livraison_origine else '',
                'date': str(recup.livraison_origine.date_livraison) if recup.livraison_origine else ''
            } if recup.livraison_origine else None
        })
    
    return JsonResponse({'recuperations': data})


from .models import (
    Livraison, ModeEnvoi, PhotoLivraison
)

# ==========================================
# GESTION DES RÉCUPÉRATIONS
# ==========================================

@login_required
def gestion_recuperations(request):
    """Page de gestion des récupérations"""
    
    # Date sélectionnée
    date_str = request.GET.get('date', timezone.now().strftime('%Y-%m-%d'))
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Tous les modes d'envoi actifs
    modes_envoi = ModeEnvoi.objects.filter(actif=True).order_by('nom')
    
    # Modes permettant récupération
    modes_recuperables = ModeEnvoi.objects.filter(
        actif=True,
        permet_recuperation=True
    ).order_by('nom')
    
    print(f"DEBUG: Modes récupérables trouvés: {modes_recuperables.count()}")
    for mode in modes_recuperables:
        print(f"  - {mode.nom} (permet_recuperation={mode.permet_recuperation})")
    
    context = {
        'date_selectionnee': date_str,
        'date_obj': date_obj,
        'modes_envoi': modes_envoi,
        'modes_recuperables': modes_recuperables,
    }
    
    return render(request, 'livraison/responsable/gestion_recuperations.html', context)


# ==========================================
# API - MODES D'ENVOI
# ==========================================

@login_required
def modes_envoi_json(request):
    """API pour récupérer tous les modes d'envoi"""
    
    modes = ModeEnvoi.objects.all().order_by('nom')
    
    data = [{
        'id': mode.id,
        'nom': mode.nom,
        'description': mode.description,
        'couleur': mode.couleur,
        'permet_recuperation': mode.permet_recuperation,
        'actif': mode.actif
    } for mode in modes]
    
    return JsonResponse({'modes': data})


@login_required
@require_http_methods(["POST"])
def creer_mode_envoi(request):
    """Créer un nouveau mode d'envoi"""
    try:
        data = json.loads(request.body)
        
        # Vérifier unicité
        if ModeEnvoi.objects.filter(nom=data['nom']).exists():
            return JsonResponse({
                'success': False,
                'error': 'Ce mode d\'envoi existe déjà'
            }, status=400)
        
        mode = ModeEnvoi.objects.create(
            nom=data['nom'],
            description=data.get('description', ''),
            couleur=data.get('couleur', '#3B82F6'),
            permet_recuperation=data.get('permet_recuperation', False),
            actif=True
        )
        
        return JsonResponse({
            'success': True,
            'mode': {
                'id': mode.id,
                'nom': mode.nom,
                'description': mode.description,
                'couleur': mode.couleur,
                'permet_recuperation': mode.permet_recuperation,
                'actif': mode.actif
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["PUT"])
def modifier_mode_envoi(request, mode_id):
    """Modifier un mode d'envoi"""
    try:
        data = json.loads(request.body)
        mode = ModeEnvoi.objects.get(id=mode_id)
        
        # Vérifier unicité du nom si changé
        if data['nom'] != mode.nom:
            if ModeEnvoi.objects.filter(nom=data['nom']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Ce nom est déjà utilisé'
                }, status=400)
        
        mode.nom = data['nom']
        mode.description = data.get('description', '')
        mode.couleur = data.get('couleur', '#3B82F6')
        mode.permet_recuperation = data.get('permet_recuperation', False)
        mode.actif = data.get('actif', True)
        mode.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Mode d\'envoi modifié'
        })
        
    except ModeEnvoi.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Mode d\'envoi introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["DELETE"])
def supprimer_mode_envoi(request, mode_id):
    """Supprimer un mode d'envoi"""
    try:
        mode = ModeEnvoi.objects.get(id=mode_id)
        
        # Vérifier qu'il n'est pas utilisé
        nb_livraisons = Livraison.objects.filter(mode_envoi=mode).count()
        
        if nb_livraisons > 0:
            return JsonResponse({
                'success': False,
                'error': f'Impossible de supprimer: {nb_livraisons} livraison(s) utilisent ce mode'
            }, status=400)
        
        mode.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Mode d\'envoi supprimé'
        })
        
    except ModeEnvoi.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Mode d\'envoi introuvable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# ==========================================
# API - RÉCUPÉRATIONS
# ==========================================

@login_required
def livraisons_recuperables_json(request):
    """API pour récupérer les livraisons récupérables d'une date"""
    
    date_str = request.GET.get('date')
    mode_id = request.GET.get('mode_id')
    
    print(f"DEBUG livraisons_recuperables_json: date={date_str}, mode_id={mode_id}")
    
    if not date_str or not mode_id:
        print("DEBUG: Date ou mode_id manquant")
        return JsonResponse({'livraisons': []})
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        mode = ModeEnvoi.objects.get(id=mode_id, permet_recuperation=True)
        print(f"DEBUG: Mode trouvé: {mode.nom}, permet_recuperation={mode.permet_recuperation}")
    except ModeEnvoi.DoesNotExist:
        print(f"DEBUG: Mode {mode_id} introuvable ou ne permet pas récupération")
        return JsonResponse({'livraisons': []})
    except Exception as e:
        print(f"DEBUG: Erreur parsing: {e}")
        return JsonResponse({'livraisons': []})
    
    # Livraisons de cette date avec ce mode d'envoi et déjà livrées
    livraisons = Livraison.objects.filter(
        date_livraison=date_obj,
        mode_envoi=mode,
        status='livree',
        est_recuperation=False
    ).order_by('heure_souhaitee')
    
    print(f"DEBUG: {livraisons.count()} livraisons trouvées")
    
    data = []
    for liv in livraisons:
        # Vérifier si récupération déjà créée
        recuperation_existe = Livraison.objects.filter(
            livraison_origine=liv,
            est_recuperation=True
        ).exists()
        
        data.append({
            'id': str(liv.id),
            'numero': liv.numero_livraison,
            'nom_evenement': liv.nom_evenement,
            'client': liv.client_nom,
            'adresse': liv.adresse_complete,
            'heure': liv.heure_souhaitee.strftime('%H:%M') if liv.heure_souhaitee else '',
            'nb_convives': liv.nb_convives,
            'recuperation_existe': recuperation_existe
        })
    
    print(f"DEBUG: Retour de {len(data)} livraisons dans JSON")
    return JsonResponse({'livraisons': data})


@login_required
@require_http_methods(["POST"])
def transformer_en_recuperations(request):
    """Transformer des livraisons en récupérations"""
    try:
        data = json.loads(request.body)
        
        livraison_ids = data.get('livraison_ids', [])
        date_recuperation = data.get('date_recuperation')
        
        if not livraison_ids or not date_recuperation:
            return JsonResponse({
                'success': False,
                'error': 'Données manquantes'
            }, status=400)
        
        date_obj = datetime.strptime(date_recuperation, '%Y-%m-%d').date()
        
        livraisons_creees = []
        
        with transaction.atomic():
            for liv_id in livraison_ids:
                livraison_origine = Livraison.objects.get(id=liv_id)
                
                # Vérifier que le mode permet récupération
                if not livraison_origine.mode_envoi or not livraison_origine.mode_envoi.permet_recuperation:
                    continue
                
                # Créer la récupération (duplication complète)
                nouvelle_livraison = Livraison.objects.create(
                    # Nouveau numéro de livraison
                    numero_livraison=f"{livraison_origine.numero_livraison}-RECUP",
                    nom_evenement=f"{livraison_origine.nom_evenement} (Récupération)" if livraison_origine.nom_evenement else "Récupération",
                    
                    # Client (identique)
                    client_nom=livraison_origine.client_nom,
                    client_telephone=livraison_origine.client_telephone,
                    client_email=livraison_origine.client_email,
                    contact_sur_site=livraison_origine.contact_sur_site,
                    
                    # Adresse (identique)
                    adresse_complete=livraison_origine.adresse_complete,
                    latitude=livraison_origine.latitude,
                    longitude=livraison_origine.longitude,
                    place_id=livraison_origine.place_id,
                    code_postal=livraison_origine.code_postal,
                    ville=livraison_origine.ville,
                    app=livraison_origine.app,
                    ligne_adresse_2=livraison_origine.ligne_adresse_2,
                    
                    # Timing (nouvelle date)
                    date_livraison=date_obj,
                    periode='apres_midi',  # Par défaut après-midi pour récupération
                    heure_souhaitee=None,
                    
                    # Détails
                    mode_envoi=livraison_origine.mode_envoi,
                    montant=0,  # Pas de montant pour récupération
                    nb_convives=livraison_origine.nb_convives,
                    
                    # Besoins (réinitialisés)
                    besoin_cafe=False,
                    besoin_the=False,
                    besoin_sac_glace=False,
                    besoin_part_chaud=False,
                    
                    # Statut
                    status='non_assignee',
                    
                    # Notes
                    instructions_speciales=f"RÉCUPÉRATION de la livraison {livraison_origine.numero_livraison}\nDate originale: {livraison_origine.date_livraison}",
                    notes_internes=livraison_origine.notes_internes,
                    
                    # Récupération
                    est_recuperation=True,
                    livraison_origine=livraison_origine,
                    
                    # Metadata
                    cree_par=request.user
                )
                
                # Copier les photos
                photos_origine = PhotoLivraison.objects.filter(livraison=livraison_origine)
                for photo in photos_origine:
                    # Dupliquer le fichier physique
                    if photo.image:
                        old_path = photo.image.path
                        if os.path.exists(old_path):
                            # Créer nouveau nom de fichier
                            ext = os.path.splitext(old_path)[1]
                            new_filename = f"recuperation_{nouvelle_livraison.id}_{photo.id}{ext}"
                            new_path = os.path.join(
                                os.path.dirname(old_path),
                                new_filename
                            )
                            
                            # Copier le fichier
                            shutil.copy2(old_path, new_path)
                            
                            # Créer l'entrée PhotoLivraison
                            PhotoLivraison.objects.create(
                                livraison=nouvelle_livraison,
                                image=new_path,
                                legende=photo.legende,
                                prise_par=photo.prise_par
                            )
                
                livraisons_creees.append({
                    'id': str(nouvelle_livraison.id),
                    'numero': nouvelle_livraison.numero_livraison
                })
        
        return JsonResponse({
            'success': True,
            'message': f'{len(livraisons_creees)} récupération(s) créée(s)',
            'livraisons': livraisons_creees
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, date
import json
import base64
from django.core.files.base import ContentFile

from .models import (
    Route, Livraison, LivraisonRoute, PhotoLivraison, Vehicule
)

# ==========================================
# DASHBOARD LIVREUR
# ==========================================

@login_required
def dashboard_livreur(request):
    # Récupérer la date sélectionnée ou utiliser aujourd'hui
    date_param = request.GET.get('date')
    
    if date_param:
        try:
            date_selectionnee = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            date_selectionnee = date.today()
    else:
        date_selectionnee = date.today()
    
    # Récupérer les routes du livreur pour la date sélectionnée
    routes = Route.objects.filter(
        livreurs=request.user,
        date=date_selectionnee
    ).select_related('vehicule').prefetch_related(
        'livraisonroute_set__livraison'  # Simplifié sans commande
    ).order_by('heure_depart')
    
    context = {
        'routes': routes,
        'date_selectionnee': date_selectionnee,
        'aujourd_hui': date.today(),
    }
    
    return render(request, 'livraison/livreur/dashboard.html', context)




# ==========================================
# DÉMARRAGE DE ROUTE
# ==========================================

@login_required
def demarrer_route(request, route_id):
    """Démarrer une route - une seule route en cours à la fois"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        route = Route.objects.get(id=route_id, livreurs=request.user)
    except Route.DoesNotExist:
        return JsonResponse({
            'error': 'Route introuvable ou vous n\'êtes pas assigné à cette route'
        }, status=404)
    
    # Vérifier le statut actuel de la route
    if route.status == 'en_cours':
        # La route est déjà démarrée, c'est OK
        return JsonResponse({'success': True})
    
    if route.status == 'terminee':
        return JsonResponse({
            'error': 'Cette route est déjà terminée'
        }, status=400)
    
    # Vérifier qu'aucune autre route n'est en cours pour ce livreur
    routes_en_cours = Route.objects.filter(
        livreurs=request.user,
        status='en_cours',
        date=route.date  # Même date uniquement
    ).exclude(id=route_id)
    
    if routes_en_cours.exists():
        route_en_cours = routes_en_cours.first()
        return JsonResponse({
            'error': f'Vous avez déjà une route en cours : "{route_en_cours.nom}". Terminez-la avant d\'en démarrer une nouvelle.'
        }, status=400)
    
    # Démarrer la route
    if route.status == 'planifiee':
        route.status = 'en_cours'
        route.heure_depart_reelle = timezone.now()
        route.save()
        
        # Mettre à jour le statut des livraisons
        for livraison_route in route.livraisonroute_set.all():
            if livraison_route.livraison.status == 'assignee':
                livraison_route.livraison.status = 'en_cours'
                livraison_route.livraison.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Route démarrée avec succès'
        })
    
    return JsonResponse({
        'error': f'La route ne peut pas être démarrée (statut actuel: {route.get_status_display()})'
    }, status=400)
@login_required
def selection_vehicule(request, route_id):
    """Étape 2: Sélection du véhicule"""
    
    route = get_object_or_404(Route, id=route_id, livreurs=request.user)
    
    if route.status != 'en_cours':
        return redirect('livraison:dashboard_livreur')
    
    # Liste des véhicules disponibles
    vehicules = Vehicule.objects.filter(statut="disponible").order_by('modele')
    
    context = {
        'route': route,
        'vehicules': vehicules,
    }
    
    return render(request, 'livraison/livreur/selection_vehicule.html', context)


@login_required
@require_http_methods(["POST"])
def assigner_vehicule(request, route_id):
    """Assigner un véhicule à la route"""
    try:
        data = json.loads(request.body)
        route = Route.objects.get(id=route_id, livreurs=request.user)
        vehicule = Vehicule.objects.get(id=data['vehicule_id'])
        
        # Assigner le véhicule
        route.vehicule = vehicule
        route.save()
        
        # Marquer le véhicule comme non disponible
        vehicule.disponible = False
        vehicule.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Véhicule assigné',
            'etape_suivante': 'livraisons'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# ==========================================
# VUE DES LIVRAISONS
# ==========================================

@login_required
def livraisons_route(request, route_id):
    """Afficher les livraisons d'une route avec gestion d'erreur"""
    print(f"📦 LIVRAISONS_ROUTE - User: {request.user.username}, Route ID: {route_id}")
    
    try:
        # Essayer de récupérer la route
        route = Route.objects.get(id=route_id, livreurs=request.user)
        print(f"✅ Route trouvée: {route.nom}, Status: {route.status}")
    except Route.DoesNotExist:
        print(f"❌ Route introuvable ou user non assigné")
        messages.error(request, 'Route introuvable ou vous n\'êtes pas assigné à cette route')
        return redirect('livraison:dashboard_livreur')
    
    # Vérifier que la route est bien en cours
    if route.status != 'en_cours':
        print(f"⚠️ Route pas en cours (status: {route.status})")
        messages.warning(request, f'Cette route n\'est pas en cours (statut: {route.get_status_display()})')
        return redirect('livraison:dashboard_livreur')
    
    # Récupérer les livraisons
    livraisons = route.livraisonroute_set.select_related(
        'livraison__mode_envoi'
    ).prefetch_related(
        'livraison__photos'
    ).order_by('ordre')
    
    print(f"📦 {livraisons.count()} livraisons trouvées")
    
    context = {
        'route': route,
        'livraisons': livraisons,
    }
    
    return render(request, 'livraison/livreur/livraisons_route.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Livraison, Route

@login_required
def detail_livraison(request, livraison_id):
    livraison = get_object_or_404(Livraison, id=livraison_id)
    
    # Trouver la route associée via LivraisonRoute
    livraison_route = livraison.livraisonroute_set.first()
    route = livraison_route.route if livraison_route else None
    
    
    
    context = {
        'livraison': livraison,
        'route': route,
    }
    
    return render(request, 'livraison/livreur/detail_livraison.html', context)

# ==========================================
# ACTIONS LIVREUR
# ==========================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Livraison, PhotoLivraison

@login_required
def prendre_photo(request, livraison_id):
    """Upload de plusieurs photos compressées (max 5)"""
    livraison = get_object_or_404(Livraison, id=livraison_id)
    
    if request.method == 'POST':
        photos = request.FILES.getlist('photos')
        current_count = livraison.photos.count()
        max_photos = 5
        
        # Vérifier la limite
        if current_count >= max_photos:
            return JsonResponse({'error': 'Maximum 5 photos'}, status=400)
        
        # Calculer combien on peut encore ajouter
        available_slots = max_photos - current_count
        photos_to_add = photos[:available_slots]
        
        # Créer les photos
        for photo_file in photos_to_add:
            PhotoLivraison.objects.create(
                livraison=livraison,
                image=photo_file,
                prise_par=request.user
            )
    
    return redirect('livraison:detail_livraison', livraison_id=livraison.id)

@login_required
def supprimer_photo(request, photo_id):
    """Supprimer une photo de livraison"""
    if request.method == 'POST':
        photo = get_object_or_404(PhotoLivraison, id=photo_id)
        
        # Vérifier que l'utilisateur a le droit
        if photo.livraison.livraisonroute_set.filter(route__livreurs=request.user).exists():
            photo.delete()
            return JsonResponse({'success': True})
        
        return JsonResponse({'error': 'Non autorisé'}, status=403)
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


import json
import base64
import uuid
import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.files.base import ContentFile
from .models import Livraison

logger = logging.getLogger(__name__)

@login_required
def sauvegarder_signature(request, livraison_id):
    """Sauvegarde de la signature en base64 + nom du signataire"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    livraison = get_object_or_404(Livraison, id=livraison_id)
    
    try:
        # Parser le JSON
        data = json.loads(request.body)
        signature_data = data.get('signature', '')
        nom_signataire = data.get('nom_signataire', '')
        
        # Validation
        if not signature_data:
            return JsonResponse({'error': 'Signature manquante'}, status=400)
        
        if not nom_signataire or nom_signataire.strip() == '':
            return JsonResponse({'error': 'Nom du signataire requis'}, status=400)
        
        # Retirer le préfixe data:image/png;base64,
        if ',' in signature_data:
            signature_data = signature_data.split(',')[1]
        
        # Décoder la signature
        try:
            signature_binary = base64.b64decode(signature_data)
        except Exception as decode_error:
            logger.error(f"Erreur décodage base64: {decode_error}")
            return JsonResponse({'error': 'Format de signature invalide'}, status=400)
        
        # Créer le fichier
        filename = f'signature_{livraison_id}_{uuid.uuid4().hex[:8]}.png'
        
        # Supprimer l'ancienne signature si elle existe
        if livraison.signature_client:
            livraison.signature_client.delete(save=False)
        
        # Sauvegarder la nouvelle signature
        livraison.signature_client.save(filename, ContentFile(signature_binary), save=False)
        livraison.nom_signataire = nom_signataire.strip()
        livraison.save()
        
        return JsonResponse({'success': True})
    
    except json.JSONDecodeError as e:
        logger.error(f"Erreur JSON: {e}")
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    
    except Exception as e:
        logger.error(f"Erreur inattendue dans sauvegarder_signature: {e}", exc_info=True)
        return JsonResponse({'error': f'Erreur serveur: {str(e)}'}, status=500)


@login_required
def marquer_livree(request, livraison_id):
    """Marquer une livraison comme livrée"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    livraison = get_object_or_404(Livraison, id=livraison_id)
    
    livraison.status = 'livree'
    livraison.heure_livraison_reelle = timezone.now()
    livraison.save()
    
    # Vérifier si la route doit être terminée automatiquement
    livraison_route = livraison.livraisonroute_set.first()
    if livraison_route and livraison_route.route:
        livraison_route.route.verifier_completion_auto()
    
    return JsonResponse({'success': True})

@login_required
@require_http_methods(["POST"])
def terminer_route(request, route_id):
    """Terminer une route"""
    try:
        route = Route.objects.get(id=route_id, livreurs=request.user)
        
        # Vérifier que toutes les livraisons sont livrées
        livraisons_non_livrees = LivraisonRoute.objects.filter(
            route=route,
            livraison__status__in=['en_cours', 'assignee']
        ).count()
        
        if livraisons_non_livrees > 0:
            return JsonResponse({
                'success': False,
                'error': f'{livraisons_non_livrees} livraison(s) non terminée(s)'
            }, status=400)
        
        route.status = 'terminee'
        route.heure_retour_reelle = timezone.now().time()
        route.save()
        
        # Libérer le véhicule
        if hasattr(route, 'vehicule') and route.vehicule:
            route.vehicule.disponible = True
            route.vehicule.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Route terminée avec succès!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    

from collections import defaultdict

@login_required
def liste_livraisons(request):
    """Liste des livraisons avec filtre par date et recherche"""
    
    # Récupérer le terme de recherche
    search_query = request.GET.get('search', '').strip()
    
    # Récupérer toutes les livraisons avec leurs relations
    livraisons = Livraison.objects.select_related(
        'cree_par',
        'mode_envoi',
        'checklist'
    ).prefetch_related(
        Prefetch(
            'livraisonroute_set',
            queryset=LivraisonRoute.objects.select_related(
                'route'
            ).prefetch_related(
                'route__livreurs'
            )
        )
    )
    
    # Appliquer la recherche si un terme est fourni
    if search_query:
        livraisons = livraisons.filter(
            Q(numero_livraison__icontains=search_query) |
            Q(nom_evenement__icontains=search_query) |
            Q(client_nom__icontains=search_query) |
            Q(adresse_complete__icontains=search_query)
        )
    
    # Trier par date (desc) puis par période (ordre spécifique pour avoir matin, midi, soir, soirée)
    livraisons = livraisons.order_by('-date_livraison', 'periode')
    
    # Organiser les livraisons par date pour le calendrier
    livraisons_by_date = defaultdict(list)
    
    # Définir l'ordre des périodes avec leurs heures de début estimées
    periode_order = {
        'matin': ('08:00', 1),
        'midi': ('12:00', 2),
        'apres_midi': ('14:00', 3),
        'soir': ('18:00', 4),
        'soiree': ('20:00', 5),
    }
    
    for livraison in livraisons:
        date_str = livraison.date_livraison.strftime('%Y-%m-%d')
        
        # Récupérer la route et les livreurs associés
        route_info = livraison.livraisonroute_set.first()
        livreurs = []
        route_nom = None
        
        if route_info and route_info.route:
            route_nom = route_info.route.nom
            livreurs = [l.get_full_name() or l.username for l in route_info.route.livreurs.all()]
        
        # Obtenir l'heure et l'ordre de tri pour la période
        heure_estimee, ordre_periode = periode_order.get(livraison.periode, ('00:00', 0))
        
        livraisons_by_date[date_str].append({
            'id': str(livraison.id),
            'numero': livraison.numero_livraison,
            'nom_evenement': livraison.nom_evenement or livraison.numero_livraison,
            'client': livraison.client_nom,
            'adresse': livraison.adresse_complete,
            'periode': livraison.get_periode_display(),
            'periode_code': livraison.periode,
            'heure_estimee': heure_estimee,
            'ordre_periode': ordre_periode,
            'status': livraison.status,
            'status_display': livraison.get_status_display(),
            'route_nom': route_nom,
            'livreurs': livreurs,
            'montant': float(livraison.montant),
        })
    
    # Trier les livraisons de chaque date par ordre de période
    for date_str in livraisons_by_date:
        livraisons_by_date[date_str].sort(key=lambda x: x['ordre_periode'])
    
    # Statistiques
    stats = {
        'total_livraisons': Livraison.objects.count(),
        'livraisons_aujourdhui': Livraison.objects.filter(date_livraison=date.today()).count(),
        'en_cours': Livraison.objects.filter(status='en_cours').count(),
        'non_assignees': Livraison.objects.filter(status='non_assignee').count(),
    }
    
    context = {
        'livraisons': livraisons[:50],  # Dernières 50 pour le tableau principal
        'livraisons_by_date': dict(livraisons_by_date),
        'today': date.today().strftime('%Y-%m-%d'),
        'stats': stats,
        'search_query': search_query,
    }
    
    return render(request, 'livraison/liste_livraisons.html', context)

@login_required
@require_http_methods(["POST"])
def update_geocode(request):
    """Vue pour mettre à jour manuellement le géocodage d'une livraison"""
    try:
        # Parser le JSON du body
        data = json.loads(request.body)
        
        numero = data.get('numero')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        adresse = data.get('adresse')
        ville = data.get('ville')
        code_postal = data.get('code_postal')
        
        print(f"🔍 DEBUG update_geocode:")
        print(f"  - Numéro reçu: {numero}")
        print(f"  - Latitude: {latitude}")
        print(f"  - Longitude: {longitude}")
        print(f"  - Adresse: {adresse}")
        print(f"  - Ville: {ville}")
        print(f"  - Code postal: {code_postal}")
        
        # Validation
        if not all([numero, latitude, longitude]):
            return JsonResponse({
                'success': False,
                'error': 'Données manquantes (numéro, latitude ou longitude)'
            }, status=400)
        
        # Trouver la livraison par numero_livraison
        try:
            livraison = Livraison.objects.get(numero_livraison=numero)
            print(f"✅ Livraison trouvée: {livraison.id}")
        except Livraison.DoesNotExist:
            print(f"❌ Livraison #{numero} introuvable")
            print(f"   Livraisons existantes:")
            for liv in Livraison.objects.all()[:5]:
                print(f"   - {liv.numero_livraison}")
            return JsonResponse({
                'success': False,
                'error': f'Livraison #{numero} introuvable'
            }, status=404)
        
        # Mettre à jour les coordonnées et l'adresse
        livraison.latitude = float(latitude)
        livraison.longitude = float(longitude)
        
        if adresse:
            livraison.adresse_complete = adresse
        if ville:
            livraison.ville = ville
        if code_postal:
            livraison.code_postal = code_postal
        
        # Marquer comme géocodée
        livraison.geocode_status = 'success'
        livraison.geocode_attempts = 0
        
        livraison.save()
        
        print(f"✅ Livraison {numero} géocodée avec succès")
        
        return JsonResponse({
            'success': True,
            'message': f'Livraison #{numero} géocodée avec succès',
            'livraison': {
                'numero': livraison.numero_livraison,
                'nom': livraison.client_nom,
                'adresse': livraison.adresse_complete,
                'ville': livraison.ville,
                'code_postal': livraison.code_postal,
                'latitude': float(livraison.latitude) if livraison.latitude else None,
                'longitude': float(livraison.longitude) if livraison.longitude else None
            }
        })
        
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Format JSON invalide'
        }, status=400)
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    

@login_required
def get_shift_info(request):
    """API pour récupérer l'info de shift d'un livreur pour une date donnée"""
    try:
        date_str = request.GET.get('date')
        if not date_str:
            date_obj = timezone.now().date()
        else:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        dispo = DisponibiliteLivreur.objects.filter(
            livreur=request.user,
            date_debut__lte=date_obj,
            date_fin__gte=date_obj,
            type_dispo='disponible',
            heure_debut_shift__isnull=False
        ).first()
        
        if dispo and dispo.heure_debut_shift:
            return JsonResponse({
                'success': True,
                'heure_debut_shift': dispo.heure_debut_shift.strftime('%H:%M'),
                'has_shift': True
            })
        
        return JsonResponse({'success': True, 'has_shift': False})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import DisponibiliteLivreur, Livreur
import json
from datetime import datetime

@login_required
@require_http_methods(["POST"])
def creer_disponibilite(request):
    """Crée une nouvelle disponibilité pour un livreur"""
    try:
        data = json.loads(request.body)
        
        livreur = Livreur.objects.get(id=data['livreur_id'])
        
        disponibilite = DisponibiliteLivreur.objects.create(
            livreur=livreur,
            date_debut=datetime.fromisoformat(data['date_debut'].replace('Z', '+00:00')),
            date_fin=datetime.fromisoformat(data['date_fin'].replace('Z', '+00:00')),
            type_dispo=data.get('type_dispo', 'disponible'),
            notes=data.get('notes', '')
        )
        
        return JsonResponse({
            'success': True,
            'disponibilite': {
                'id': str(disponibilite.id),
                'date_debut': disponibilite.date_debut.isoformat(),
                'date_fin': disponibilite.date_fin.isoformat(),
                'type_dispo': disponibilite.type_dispo,
                'notes': disponibilite.notes
            }
        })
        
    except Livreur.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Livreur introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(["PUT"])
def modifier_disponibilite(request, dispo_id):
    """Modifie une disponibilité existante"""
    try:
        data = json.loads(request.body)
        
        disponibilite = DisponibiliteLivreur.objects.get(id=dispo_id)
        
        if 'date_debut' in data:
            disponibilite.date_debut = datetime.fromisoformat(data['date_debut'].replace('Z', '+00:00'))
        if 'date_fin' in data:
            disponibilite.date_fin = datetime.fromisoformat(data['date_fin'].replace('Z', '+00:00'))
        if 'type_dispo' in data:
            disponibilite.type_dispo = data['type_dispo']
        if 'notes' in data:
            disponibilite.notes = data['notes']
        
        disponibilite.save()
        
        return JsonResponse({
            'success': True,
            'disponibilite': {
                'id': str(disponibilite.id),
                'date_debut': disponibilite.date_debut.isoformat(),
                'date_fin': disponibilite.date_fin.isoformat(),
                'type_dispo': disponibilite.type_dispo,
                'notes': disponibilite.notes
            }
        })
        
    except DisponibiliteLivreur.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Disponibilité introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(["DELETE"])
def supprimer_disponibilite(request, dispo_id):
    """Supprime une disponibilité"""
    try:
        disponibilite = DisponibiliteLivreur.objects.get(id=dispo_id)
        disponibilite.delete()
        
        return JsonResponse({'success': True})
        
    except DisponibiliteLivreur.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Disponibilité introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def disponibilites_livreur(request, livreur_id):
    """Récupère toutes les disponibilités d'un livreur"""
    try:
        disponibilites = DisponibiliteLivreur.objects.filter(livreur_id=livreur_id).order_by('date_debut')
        
        return JsonResponse({
            'success': True,
            'disponibilites': [
                {
                    'id': str(d.id),
                    'date_debut': d.date_debut.isoformat(),
                    'date_fin': d.date_fin.isoformat(),
                    'type_dispo': d.type_dispo,
                    'notes': d.notes
                }
                for d in disponibilites
            ]
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from datetime import datetime
from .models import DisponibiliteLivreur, Livreur, Route
import traceback

# Dans views.py, modifier la fonction disponibilites_par_date

@login_required
@require_http_methods(["GET"])
def disponibilites_par_date(request):
    """Récupère les disponibilités de TOUS les livreurs pour une date donnée"""
    try:
        date_str = request.GET.get('date')
        if not date_str:
            date_recherche = datetime.now().date()
        else:
            date_recherche = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Récupérer tous les livreurs actifs
        livreurs = Livreur.objects.filter(is_active=True).select_related('user')
        
        result = []
        for livreur in livreurs:
            # Chercher les disponibilités qui couvrent cette date
            dispos = DisponibiliteLivreur.objects.filter(
                livreur=livreur.user,
                date_debut__lte=date_recherche,
                date_fin__gte=date_recherche
            ).order_by('date_debut')
            
            # Nom complet du livreur
            nom_complet = livreur.user.get_full_name() or livreur.user.username
            
            # Construire la liste des disponibilités
            dispos_data = []
            for d in dispos:
                dispos_data.append({
                    'id': str(d.id),
                    'type_dispo': d.type_dispo,
                    'heure_debut_shift': d.heure_debut_shift.strftime('%H:%M') if d.heure_debut_shift else None,
                    'notes': d.notes or ''
                })
            
            # Si le livreur n'a AUCUNE dispo pour cette date, il est considéré en congé
            if not dispos_data:
                dispos_data = []  # Liste vide = badge congé
            
            result.append({
                'id': str(livreur.id),
                'nom': nom_complet,
                'telephone': livreur.telephone or '',
                'dispos': dispos_data
            })
        
        return JsonResponse({
            'success': True,
            'disponibilites': result
        })
        
    except Exception as e:
        print(f"❌ Erreur disponibilites_par_date: {e}")
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def routes_par_date(request):
    """API pour récupérer les routes d'une date spécifique pour le livreur connecté"""
    date_str = request.GET.get('date')
    
    if not date_str:
        return JsonResponse({'success': False, 'error': 'Date requise'})
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Format de date invalide'})
    
    # Filtrer les routes du livreur connecté
    routes = Route.objects.filter(
        date=date_obj,
        livreurs=request.user
    ).select_related('vehicule').prefetch_related(
        'livreurs',  # 🔥 AJOUT pour charger tous les livreurs
        'livraisonroute_set__livraison__checklist'
    ).order_by('heure_depart')
    
    routes_data = []
    for route in routes:
        livraisons_route = route.livraisonroute_set.all().order_by('ordre')
        livraisons_data = []
        
        for lr in livraisons_route:
            livraison = lr.livraison
            
            # Construire la liste des besoins POUR CETTE LIVRAISON
            besoins_specifiques = []
            if livraison.besoin_cafe:
                besoins_specifiques.append('Café')
            if livraison.besoin_the:
                besoins_specifiques.append('Thé')
            if livraison.besoin_sac_glace:
                besoins_specifiques.append('Sac glace')
            if livraison.besoin_part_chaud:
                besoins_specifiques.append('Part chaud')
            if livraison.checklist:
                besoins_specifiques.append('Checklist')
            
            livraisons_data.append({
                'id': str(livraison.id),
                'nom': livraison.nom_evenement or livraison.numero_livraison,
                'adresse': livraison.adresse_complete,
                'heure': livraison.heure_souhaitee.strftime('%H:%M') if livraison.heure_souhaitee else '',
                'status': livraison.status,
                'informations_supplementaires': livraison.informations_supplementaires or '',
                'besoins_specifiques': besoins_specifiques
            })
        
        # 🔥 RÉCUPÉRER TOUS LES LIVREURS
        livreurs_noms = [
            livreur.get_full_name() or livreur.username
            for livreur in route.livreurs.all()
        ]
        
        # Jointure avec virgule pour l'affichage
        livreur_nom = ', '.join(livreurs_noms) if livreurs_noms else 'Non assigné'
        
        # Construire les besoins de la route (agrégés de toutes les livraisons)
        besoins_route = set()
        for lr in livraisons_route:
            livraison = lr.livraison
            if livraison.besoin_cafe:
                besoins_route.add('Café')
            if livraison.besoin_the:
                besoins_route.add('Thé')
            if livraison.besoin_sac_glace:
                besoins_route.add('Sac glace')
            if livraison.besoin_part_chaud:
                besoins_route.add('Part chaud')
            if livraison.checklist:
                besoins_route.add('Checklist')
        
        # Compter les livraisons par statut
        total_livraisons = livraisons_route.count()
        livraisons_livrees = sum(1 for lr in livraisons_route if lr.livraison.status == 'livree')
        livraisons_restantes = total_livraisons - livraisons_livrees
        
        routes_data.append({
            'id': str(route.id),
            'nom': route.nom,
            'date': route.date.strftime('%Y-%m-%d'),
            'heure_depart': route.heure_depart.strftime('%H:%M') if route.heure_depart else '',
            'status': route.status,
            'statusDisplay': route.get_status_display(),
            'livreur_nom': livreur_nom,  # 🔥 Tous les livreurs séparés par virgule
            'livreurs': livreurs_noms,   # 🔥 Liste des noms pour usage avancé
            'vehicule': f"{route.vehicule.marque} {route.vehicule.modele}" if route.vehicule else None,
            'commentaire': route.commentaire,
            'besoins': list(besoins_route),
            'total_livraisons': total_livraisons,
            'livraisons_livrees': livraisons_livrees,
            'livraisons_restantes': livraisons_restantes,
            'progression': round((livraisons_livrees / total_livraisons * 100) if total_livraisons > 0 else 0),
            'livraisons': livraisons_data
        })
    
    return JsonResponse({
        'success': True,
        'routes': routes_data
    })
@login_required
def routes_du_mois(request):
    """API pour récupérer les dates qui ont des routes pour le livreur connecté"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if not start_date or not end_date:
        return JsonResponse({'success': False, 'error': 'Dates requises'})
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Format de date invalide'})
    
    # 🔥 CORRECTION : date au lieu de date_route
    routes = Route.objects.filter(
        date__gte=start,  # 🔥 CHANGÉ
        date__lte=end,    # 🔥 CHANGÉ
        livreurs=request.user
    ).values_list('date', flat=True).distinct()  # 🔥 CHANGÉ
    
    dates = [date.strftime('%Y-%m-%d') for date in routes]
    
    return JsonResponse({
        'success': True,
        'dates': dates
    })

@login_required
def detail_livraison_responsable(request, livraison_id):
    """Vue détaillée d'une livraison pour le responsable"""
    livraison = get_object_or_404(
        Livraison.objects.select_related(
            'mode_envoi',
            'checklist',
            'cree_par',
            'livraison_origine'
        ).prefetch_related(
            'photos',
            'recuperations',
            'livraisonroute_set__route__livreurs',
            'livraisonroute_set__route__vehicule'
        ),
        id=livraison_id
    )
    
    # Récupérer la route et les livreurs
    livraison_route = livraison.livraisonroute_set.first()
    route = livraison_route.route if livraison_route else None
    
    # Récupérer les véhicules disponibles
    vehicules = Vehicule.objects.filter(statut='disponible').order_by('marque', 'modele')
    
    # Récupérer tous les modes d'envoi
    modes_envoi = ModeEnvoi.objects.filter(actif=True).order_by('nom')
    
    # Historique des statuts (si vous avez un système de logs)
    # historique_statuts = ... (à implémenter si nécessaire)
    
    context = {
        'livraison': livraison,
        'route': route,
        'vehicules': vehicules,
        'modes_envoi': modes_envoi,
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
    }
    
    return render(request, 'livraison/responsable/livraison_detail.html', context)


@login_required
@require_http_methods(["POST"])
def modifier_livraison_responsable(request, livraison_id):
    """Modification rapide d'une livraison (AJAX)"""
    try:
        data = json.loads(request.body)
        livraison = Livraison.objects.get(id=livraison_id)
        
        # Mettre à jour les champs autorisés
        if 'nom_evenement' in data:
            livraison.nom_evenement = data['nom_evenement']
        
        if 'client_nom' in data:
            livraison.client_nom = data['client_nom']
        
        if 'client_telephone' in data:
            livraison.client_telephone = data['client_telephone']
        
        if 'adresse_complete' in data:
            livraison.adresse_complete = data['adresse_complete']
        
        if 'heure_souhaitee' in data:
            from datetime import datetime
            livraison.heure_souhaitee = datetime.strptime(data['heure_souhaitee'], '%H:%M').time()
            
            # Recalculer la période
            heure = livraison.heure_souhaitee
            if heure < datetime.strptime('09:30', '%H:%M').time():
                livraison.periode = 'matin'
            elif heure < datetime.strptime('13:00', '%H:%M').time():
                livraison.periode = 'midi'
            else:
                livraison.periode = 'apres_midi'
        
        if 'mode_envoi_id' in data:
            livraison.mode_envoi = ModeEnvoi.objects.get(id=data['mode_envoi_id'])
        
        if 'nb_convives' in data:
            livraison.nb_convives = int(data['nb_convives'])
        
        if 'informations_supplementaires' in data:
            livraison.informations_supplementaires = data['informations_supplementaires']
        
        if 'notes_internes' in data:
            livraison.notes_internes = data['notes_internes']
        
        # Besoins spéciaux
        if 'besoin_cafe' in data:
            livraison.besoin_cafe = data['besoin_cafe']
        if 'besoin_the' in data:
            livraison.besoin_the = data['besoin_the']
        if 'besoin_sac_glace' in data:
            livraison.besoin_sac_glace = data['besoin_sac_glace']
        if 'besoin_part_chaud' in data:
            livraison.besoin_part_chaud = data['besoin_part_chaud']
        
        livraison.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Livraison mise à jour',
            'livraison': {
                'nom_evenement': livraison.nom_evenement,
                'client_nom': livraison.client_nom,
                'heure_souhaitee': livraison.heure_souhaitee.strftime('%H:%M') if livraison.heure_souhaitee else '',
                'periode_display': livraison.get_periode_display(),
            }
        })
        
    except Livraison.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Livraison introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["DELETE"])
def supprimer_livraison(request, livraison_id):
    """Supprimer une livraison"""
    try:
        livraison = Livraison.objects.get(id=livraison_id)
        
        # Vérifier qu'elle n'est pas dans une route en cours
        if livraison.status in ['en_cours', 'livree']:
            return JsonResponse({
                'success': False,
                'error': 'Impossible de supprimer une livraison en cours ou livrée'
            }, status=400)
        
        # Supprimer les associations de route
        LivraisonRoute.objects.filter(livraison=livraison).delete()
        
        # Supprimer la livraison
        livraison.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Livraison supprimée'
        })
        
    except Livraison.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Livraison introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)