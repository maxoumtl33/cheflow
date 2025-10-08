# maitre_hotel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import Contrat, PhotoContrat, HistoriqueContrat




@login_required
def dashboard(request):
    """Dashboard principal du maître d'hôtel"""
    
    maintenant = timezone.now()
    
    # Statistiques du mois ACTUEL
    mois_debut = maintenant.date().replace(day=1)
    if mois_debut.month == 12:
        mois_fin = mois_debut.replace(year=mois_debut.year + 1, month=1)
    else:
        mois_fin = mois_debut.replace(month=mois_debut.month + 1)
    
    contrats_mois = Contrat.objects.filter(
        maitre_hotel=request.user,
        date_evenement__gte=mois_debut,
        date_evenement__lt=mois_fin
    )
    
    stats = {
        'total': contrats_mois.count(),
        'planifies': contrats_mois.filter(status='planifie').count(),
        'en_cours': contrats_mois.filter(status='en_cours').count(),
        'termines': contrats_mois.filter(status='termine').count(),
    }
    
    # Prochain contrat
    prochain = Contrat.objects.filter(
        maitre_hotel=request.user,
        status='planifie',
        date_evenement__gte=maintenant.date()
    ).order_by('date_evenement', 'heure_debut_prevue').first()
    
    # Contrat en cours
    en_cours = Contrat.objects.filter(
        maitre_hotel=request.user,
        status='en_cours'
    ).first()
    
    # Charger les contrats du mois pour le calendrier
    contrats_mois_list = Contrat.objects.filter(
        maitre_hotel=request.user,
        date_evenement__gte=mois_debut,
        date_evenement__lt=mois_fin
    ).select_related('livraison', 'checklist')
    
    # Grouper par date
    contrats_par_date = {}
    for contrat in contrats_mois_list:
        date_key = contrat.date_evenement.isoformat()
        if date_key not in contrats_par_date:
            contrats_par_date[date_key] = []
        
        contrats_par_date[date_key].append({
            'id': str(contrat.id),
            'numero': contrat.numero_contrat,
            'nom': contrat.nom_evenement,
            'client': contrat.client_nom,
            'heure': f"{contrat.heure_debut_prevue.strftime('%H:%M')} - {contrat.heure_fin_prevue.strftime('%H:%M')}",
            'status': contrat.status,
            'nb_convives': contrat.nb_convives,
            'a_checklist': contrat.checklist_id is not None,
            'a_livraison': contrat.livraison_id is not None,
        })
    
    context = {
        'today': maintenant.date().isoformat(),  # Format: "2025-10-07"
        'mois_actuel': mois_debut.isoformat(),   # Format: "2025-10-01"
        'stats': stats,
        'prochain': prochain,
        'en_cours': en_cours,
        'contrats_json': json.dumps(contrats_par_date),
    }
    
    return render(request, 'maitre_hotel/dashboard.html', context)
@login_required
def calendrier(request):
    """Vue calendrier des contrats"""
    
    # Mois sélectionné
    mois_str = request.GET.get('mois')
    if mois_str:
        try:
            date_ref = datetime.strptime(mois_str, '%Y-%m')
        except ValueError:
            date_ref = timezone.now()
    else:
        date_ref = timezone.now()
    
    # Début et fin du mois
    debut_mois = date_ref.replace(day=1).date()
    if debut_mois.month == 12:
        fin_mois = debut_mois.replace(year=debut_mois.year + 1, month=1)
    else:
        fin_mois = debut_mois.replace(month=debut_mois.month + 1)
    
    # Contrats du mois
    contrats = Contrat.objects.filter(
        maitre_hotel=request.user,
        date_evenement__gte=debut_mois,
        date_evenement__lt=fin_mois
    ).select_related('livraison', 'checklist').order_by('date_evenement', 'heure_debut_prevue')
    
    # Grouper par date
    contrats_par_date = {}
    for contrat in contrats:
        date_key = contrat.date_evenement.isoformat()
        if date_key not in contrats_par_date:
            contrats_par_date[date_key] = []
        contrats_par_date[date_key].append({
            'id': str(contrat.id),
            'numero': contrat.numero_contrat,
            'nom': contrat.nom_evenement,
            'heure': contrat.heure_debut_prevue.strftime('%H:%M'),
            'status': contrat.status,
            'client': contrat.client_nom,
        })
    
    context = {
        'mois': debut_mois,
        'contrats_json': json.dumps(contrats_par_date),
    }
    
    return render(request, 'maitre_hotel/calendrier.html', context)


@login_required
def detail_contrat(request, contrat_id):
    """Détail d'un contrat"""
    
    contrat = get_object_or_404(
        Contrat.objects.select_related('livraison', 'checklist', 'maitre_hotel'),
        id=contrat_id,
        maitre_hotel=request.user
    )
    
    # Photos du contrat
    photos = contrat.photos.all()
    peut_ajouter_photo = photos.count() < 10
    
    # Historique
    historique = contrat.historique.select_related('effectue_par')[:20]

    livreurs = []
    if contrat.livraison:
        # Récupérer les livreurs via la route associée à la livraison
        livraison_routes = contrat.livraison.livraisonroute_set.select_related('route').all()
        for lr in livraison_routes:
            if lr.route:
                livreurs.extend(lr.route.livreurs.all())
    
    # Checklist liée
    checklist_items = None
    if contrat.checklist:
        checklist_items = contrat.checklist.items.select_related('objet').all()
    
    context = {
        'contrat': contrat,
        'photos': photos,
        'peut_ajouter_photo': peut_ajouter_photo,
        'historique': historique,
        'checklist_items': checklist_items,
        'livreurs': livreurs,
    }
    
    return render(request, 'maitre_hotel/detail_contrat.html', context)


@login_required
@require_http_methods(["POST"])
def commencer_contrat(request, contrat_id):
    """Démarre un contrat"""
    
    contrat = get_object_or_404(Contrat, id=contrat_id, maitre_hotel=request.user)
    
    if contrat.commencer():
        # Log dans l'historique
        HistoriqueContrat.objects.create(
            contrat=contrat,
            type_action='debut',
            description=f"Contrat démarré à {timezone.now().strftime('%H:%M')}",
            effectue_par=request.user
        )
        
        return JsonResponse({'success': True, 'heure_debut': contrat.heure_debut_reelle.isoformat()})
    
    return JsonResponse({'success': False, 'error': 'Impossible de démarrer ce contrat'}, status=400)


@login_required
@require_http_methods(["POST"])
def terminer_contrat(request, contrat_id):
    """Termine un contrat"""
    
    contrat = get_object_or_404(Contrat, id=contrat_id, maitre_hotel=request.user)
    
    data = json.loads(request.body)
    notes_finales = data.get('notes_finales', '')
    
    if contrat.terminer(notes_finales):
        # Log dans l'historique
        HistoriqueContrat.objects.create(
            contrat=contrat,
            type_action='fin',
            description=f"Contrat terminé à {timezone.now().strftime('%H:%M')}",
            effectue_par=request.user
        )
        
        return JsonResponse({
            'success': True,
            'heure_fin': contrat.heure_fin_reelle.isoformat(),
            'duree': contrat.duree_reelle()
        })
    
    return JsonResponse({'success': False, 'error': 'Impossible de terminer ce contrat'}, status=400)


@login_required
@require_http_methods(["POST"])
def rapport_boissons(request, contrat_id):
    """Enregistre le rapport des boissons"""
    
    contrat = get_object_or_404(Contrat, id=contrat_id, maitre_hotel=request.user)
    
    data = json.loads(request.body)
    rapport = data.get('rapport', '')
    
    contrat.rapport_boissons = rapport
    contrat.save()
    
    # Log dans l'historique
    HistoriqueContrat.objects.create(
        contrat=contrat,
        type_action='rapport_boissons',
        description="Rapport de boissons ajouté/modifié",
        effectue_par=request.user
    )
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def ajouter_photo(request, contrat_id):
    """Ajoute une photo au contrat"""
    
    contrat = get_object_or_404(Contrat, id=contrat_id, maitre_hotel=request.user)
    
    # Vérifier la limite
    if contrat.photos.count() >= 10:
        return JsonResponse({'success': False, 'error': 'Maximum 10 photos autorisées'}, status=400)
    
    image = request.FILES.get('image')
    legende = request.POST.get('legende', '')
    
    if not image:
        return JsonResponse({'success': False, 'error': 'Aucune image fournie'}, status=400)
    
    # Créer la photo
    photo = PhotoContrat.objects.create(
        contrat=contrat,
        image=image,
        legende=legende,
        ordre=contrat.photos.count(),
        ajoute_par=request.user
    )
    
    # Log dans l'historique
    HistoriqueContrat.objects.create(
        contrat=contrat,
        type_action='photo',
        description=f"Photo ajoutée: {legende or 'Sans légende'}",
        effectue_par=request.user
    )
    
    return JsonResponse({
        'success': True,
        'photo': {
            'id': photo.id,
            'url': photo.image.url,
            'legende': photo.legende,
            'ordre': photo.ordre,
        }
    })


@login_required
@require_http_methods(["DELETE"])
def supprimer_photo(request, photo_id):
    """Supprime une photo"""
    
    photo = get_object_or_404(PhotoContrat, id=photo_id, contrat__maitre_hotel=request.user)
    contrat = photo.contrat
    
    photo.delete()
    
    return JsonResponse({'success': True})


# API Endpoints

@login_required
def api_contrats(request):
    """API: Liste des contrats"""
    
    date_str = request.GET.get('date')
    if date_str:
        date_selectionnee = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        date_selectionnee = timezone.now().date()
    
    contrats = Contrat.objects.filter(
        maitre_hotel=request.user,
        date_evenement=date_selectionnee
    ).select_related('livraison', 'checklist')
    
    data = []
    for contrat in contrats:
        data.append({
            'id': str(contrat.id),
            'numero': contrat.numero_contrat,
            'nom': contrat.nom_evenement,
            'client': contrat.client_nom,
            'adresse': contrat.adresse_complete,
            'heure_debut': contrat.heure_debut_prevue.strftime('%H:%M'),
            'heure_fin': contrat.heure_fin_prevue.strftime('%H:%M'),
            'status': contrat.status,
            'nb_convives': contrat.nb_convives,
            'a_checklist': contrat.checklist_id is not None,
            'a_livraison': contrat.livraison_id is not None,
        })
    
    return JsonResponse({'contrats': data})


@login_required
def api_detail_contrat(request, contrat_id):
    """API: Détail d'un contrat"""
    
    contrat = get_object_or_404(
        Contrat.objects.select_related('livraison', 'checklist'),
        id=contrat_id,
        maitre_hotel=request.user
    )
    
    data = {
        'id': str(contrat.id),
        'numero': contrat.numero_contrat,
        'nom': contrat.nom_evenement,
        'client': {
            'nom': contrat.client_nom,
            'telephone': contrat.client_telephone,
            'email': contrat.client_email,
            'contact_sur_site': contrat.contact_sur_site,
        },
        'adresse': contrat.adresse_complete,
        'date': contrat.date_evenement.isoformat(),
        'heure_debut_prevue': contrat.heure_debut_prevue.strftime('%H:%M'),
        'heure_fin_prevue': contrat.heure_fin_prevue.strftime('%H:%M'),
        'heure_debut_reelle': contrat.heure_debut_reelle.isoformat() if contrat.heure_debut_reelle else None,
        'heure_fin_reelle': contrat.heure_fin_reelle.isoformat() if contrat.heure_fin_reelle else None,
        'status': contrat.status,
        'nb_convives': contrat.nb_convives,
        'deroule': contrat.deroule_evenement,
        'informations': contrat.informations_supplementaires,
        'rapport_boissons': contrat.rapport_boissons,
        'notes_finales': contrat.notes_finales,
        'duree_reelle': contrat.duree_reelle(),
    }
    
    return JsonResponse(data)

# maitre_hotel/views.py
# Ajouter cette nouvelle vue API

@login_required
def api_contrats_mois(request):
    """API: Contrats par mois pour le calendrier"""
    
    mois_str = request.GET.get('mois')  # Format: YYYY-MM
    if mois_str:
        try:
            annee, mois = map(int, mois_str.split('-'))
            date_debut = datetime(annee, mois, 1).date()
            if mois == 12:
                date_fin = datetime(annee + 1, 1, 1).date()
            else:
                date_fin = datetime(annee, mois + 1, 1).date()
        except ValueError:
            return JsonResponse({'error': 'Format de mois invalide'}, status=400)
    else:
        # Mois actuel par défaut
        maintenant = timezone.now()
        date_debut = maintenant.replace(day=1).date()
        if maintenant.month == 12:
            date_fin = maintenant.replace(year=maintenant.year + 1, month=1, day=1).date()
        else:
            date_fin = maintenant.replace(month=maintenant.month + 1, day=1).date()
    
    # Récupérer tous les contrats du mois
    contrats = Contrat.objects.filter(
        maitre_hotel=request.user,
        date_evenement__gte=date_debut,
        date_evenement__lt=date_fin
    ).select_related('livraison', 'checklist')
    
    # Grouper par date
    contrats_par_date = {}
    stats = {
        'total': 0,
        'planifies': 0,
        'en_cours': 0,
        'termines': 0
    }
    
    for contrat in contrats:
        date_key = contrat.date_evenement.isoformat()
        if date_key not in contrats_par_date:
            contrats_par_date[date_key] = []
        
        contrats_par_date[date_key].append({
            'id': str(contrat.id),
            'numero': contrat.numero_contrat,
            'nom': contrat.nom_evenement,
            'client': contrat.client_nom,
            'heure': f"{contrat.heure_debut_prevue.strftime('%H:%M')} - {contrat.heure_fin_prevue.strftime('%H:%M')}",
            'status': contrat.status,
            'nb_convives': contrat.nb_convives,
            'a_checklist': contrat.checklist_id is not None,
            'a_livraison': contrat.livraison_id is not None,
        })
        
        # Stats
        stats['total'] += 1
        if contrat.status == 'planifie':
            stats['planifies'] += 1
        elif contrat.status == 'en_cours':
            stats['en_cours'] += 1
        elif contrat.status == 'termine':
            stats['termines'] += 1
    
    return JsonResponse({
        'contrats_par_date': contrats_par_date,
        'stats': stats
    })


@login_required
@require_http_methods(["GET"])
def get_livreur_info(request, contrat_id):
    """
    API pour récupérer les informations des livreurs d'un contrat
    
    Returns:
        JSON avec la liste des livreurs et leurs informations
    """
    try:
        contrat = get_object_or_404(Contrat, id=contrat_id)
        
        livreurs_data = []
        livreurs_ids_vus = set()  # Pour éviter les doublons
        
        if contrat.livraison:
            # Parcourir toutes les routes associées à cette livraison
            livraison_routes = contrat.livraison.livraisonroute_set.select_related(
                'route', 
                'route__vehicule'
            ).prefetch_related(
                'route__livreurs'
            ).all()
            
            for livraison_route in livraison_routes:
                if livraison_route.route:
                    route = livraison_route.route
                    
                    # Parcourir tous les livreurs de cette route
                    for livreur in route.livreurs.all():
                        # Éviter les doublons si un livreur est sur plusieurs routes
                        if livreur.id not in livreurs_ids_vus:
                            livreurs_ids_vus.add(livreur.id)
                            
                            livreurs_data.append({
                                'id': livreur.id,
                                'nom_complet': livreur.get_full_name(),
                                'username': livreur.username,
                                'telephone': livreur.telephone or '',
                                'email': livreur.email or '',
                                'role': livreur.get_role_display(),
                                'route_nom': route.nom,
                                'route_id': str(route.id),
                                'route_status': route.get_status_display(),
                                'heure_depart': route.heure_depart.strftime('%H:%M') if route.heure_depart else None,
                                'vehicule': str(route.vehicule) if route.vehicule else None,
                            })
        
        return JsonResponse({
            'success': True,
            'livreurs': livreurs_data,
            'count': len(livreurs_data)
        })
        
    except Contrat.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Contrat non trouvé'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur serveur: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_livraison_status(request, contrat_id):
    """
    API pour récupérer le statut actuel de la livraison et des livreurs
    Utile pour un rafraîchissement en temps réel
    """
    try:
        contrat = get_object_or_404(Contrat, id=contrat_id)
        
        if not contrat.livraison:
            return JsonResponse({
                'success': True,
                'has_livraison': False,
                'message': 'Aucune livraison associée'
            })
        
        livraison = contrat.livraison
        
        # Compter les livreurs assignés
        nb_livreurs = 0
        routes_info = []
        
        livraison_routes = livraison.livraisonroute_set.select_related('route').prefetch_related('route__livreurs').all()
        
        for livraison_route in livraison_routes:
            if livraison_route.route:
                route = livraison_route.route
                nb_livreurs_route = route.livreurs.count()
                nb_livreurs += nb_livreurs_route
                
                routes_info.append({
                    'id': str(route.id),
                    'nom': route.nom,
                    'status': route.status,
                    'status_display': route.get_status_display(),
                    'nb_livreurs': nb_livreurs_route,
                    'heure_depart': route.heure_depart.strftime('%H:%M') if route.heure_depart else None,
                })
        
        return JsonResponse({
            'success': True,
            'has_livraison': True,
            'livraison': {
                'id': str(livraison.id),
                'numero': livraison.numero_livraison,
                'status': livraison.status,
                'status_display': livraison.get_status_display(),
                'date': livraison.date_livraison.strftime('%Y-%m-%d'),
                'periode': livraison.periode,
                'periode_display': livraison.get_periode_display(),
            },
            'nb_livreurs_total': nb_livreurs,
            'routes': routes_info
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)