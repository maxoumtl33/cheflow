# checklist/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from datetime import datetime, timedelta
from ventes.models import Checklist, ItemChecklist, ObjetChecklist, CategorieObjet
from livraison.models import Livraison
import json

@login_required
def dashboard_verificateur(request):
    """Dashboard principal avec calendrier des checklists"""
    
    # Date sélectionnée
    date_str = request.GET.get('date')
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        selected_date = timezone.now().date()

    objets = ObjetChecklist.objects.filter(actif=True).select_related('categorie')
    categories = CategorieObjet.objects.filter(actif=True)
    
    # Toutes les checklists pour le calendrier
    all_checklists = Checklist.objects.select_related(
        'creee_par', 'verificateur'
    ).prefetch_related(
        Prefetch('items', queryset=ItemChecklist.objects.select_related('objet'))
    ).annotate(
        total_items=Count('items'),
        items_verifies=Count('items', filter=Q(items__verifie=True))
    )
    
    # Stats globales
    stats = {
        'total_checklists': all_checklists.count(),
        'en_attente': all_checklists.filter(status='en_attente').count(),
        'en_cours': all_checklists.filter(status='en_cours').count(),
        'validees': all_checklists.filter(status='validee').count(),
    }
    
    # Livraisons du jour sélectionné (pour la section impression)
    livraisons_jour = Livraison.objects.filter(
        date_livraison=selected_date
    ).select_related('mode_envoi', 'checklist').order_by('periode', 'heure_souhaitee')
    
    context = {
        'selected_date': selected_date,
        'checklists': all_checklists,  # Toutes les checklists pour le JS
        'stats': stats,
        'livraisons': livraisons_jour,
        'objets': objets,
        'categories': categories,
    }
    
    return render(request, 'checklist/dashboard_verificateur.html', context)


# checklist/views.py

# checklist/views.py - VERSION COMPLÈTE

@login_required
def verification_checklist(request, checklist_id):
    """Page de vérification d'une checklist (optimisée tablette) - VERSION AVANCÉE"""
    
    checklist = get_object_or_404(
        Checklist.objects.select_related('creee_par', 'verificateur')
        .prefetch_related(
            Prefetch('items', queryset=ItemChecklist.objects.select_related('objet', 'objet__categorie').order_by('ordre', 'id'))
        ),
        id=checklist_id
    )
    
    # Passer en statut "en_cours" si c'est la première fois
    if checklist.status == 'en_attente':
        checklist.status = 'en_cours'
        checklist.verificateur = request.user
        checklist.save(update_fields=['status', 'verificateur'])
    
    # Compter les items validés
    items_verifies_count = checklist.items.filter(statut_verification='valide').count()
    
    # Grouper items par catégorie
    items_par_categorie = {}
    for item in checklist.items.all():
        cat_nom = item.objet.categorie.nom
        if cat_nom not in items_par_categorie:
            items_par_categorie[cat_nom] = {
                'categorie': item.objet.categorie,
                'items': []
            }
        items_par_categorie[cat_nom]['items'].append(item)
    
    # ✨ NOUVEAU : Détecter TOUS les changements (modifications, ajouts ET suppressions)
    from ventes.models import ItemChecklistHistorique
    
    changements = []
    items_modifies = 0
    items_ajoutes = 0
    items_supprimes = 0
    
    # 1. Récupérer les items actuels avec modifications
    for item in checklist.items.all():
        if item.modifie_depuis_verification:
            # Récupérer le dernier historique de cet item
            dernier_historique = item.historique.first()
            
            if dernier_historique and dernier_historique.type_modification == 'quantite':
                # Item modifié avec historique de quantité
                difference = float(dernier_historique.quantite_apres - dernier_historique.quantite_avant)
                
                changements.append({
                    'type': 'modification',
                    'objet': item.objet.nom,
                    'objet_id': item.objet.id,
                    'quantite_avant': float(dernier_historique.quantite_avant),
                    'quantite_apres': float(dernier_historique.quantite_apres),
                    'difference': difference,
                    'unite': item.objet.unite,
                    'categorie': item.objet.categorie.nom,
                    'date_modification': dernier_historique.date_modification,
                    'modifie_par': dernier_historique.modifie_par,
                })
                items_modifies += 1
                
            elif not item.date_verification:
                # Nouvel item ajouté
                changements.append({
                    'type': 'ajout',
                    'objet': item.objet.nom,
                    'objet_id': item.objet.id,
                    'quantite': float(item.quantite),
                    'unite': item.objet.unite,
                    'categorie': item.objet.categorie.nom,
                })
                items_ajoutes += 1
    
    # 2. Récupérer les items SUPPRIMÉS depuis l'historique
    # On cherche tous les historiques de type 'suppression' pour cette checklist
    historiques_suppression = ItemChecklistHistorique.objects.filter(
        item__checklist=checklist,
        type_modification='suppression'
    ).select_related('item__objet', 'item__objet__categorie', 'modifie_par').order_by('-date_modification')
    
    # Pour éviter les doublons, on ne prend que les suppressions récentes
    # (depuis la dernière vérification ou les 7 derniers jours)
    from datetime import timedelta
    date_limite = timezone.now() - timedelta(days=7)
    if checklist.date_verification:
        date_limite = checklist.date_verification
    
    for hist in historiques_suppression:
        if hist.date_modification >= date_limite:
            # Vérifier que l'item n'existe plus dans la checklist
            if not checklist.items.filter(objet=hist.item.objet).exists():
                changements.append({
                    'type': 'suppression',
                    'objet': hist.item.objet.nom,
                    'quantite_avant': float(hist.quantite_avant) if hist.quantite_avant else 0,
                    'unite': hist.item.objet.unite,
                    'categorie': hist.item.objet.categorie.nom,
                    'date_modification': hist.date_modification,
                    'modifie_par': hist.modifie_par,
                })
                items_supprimes += 1
    
    # Trier les changements : suppressions d'abord, puis ajouts, puis modifications
    changements.sort(key=lambda x: (
        0 if x['type'] == 'suppression' else (1 if x['type'] == 'ajout' else 2),
        x.get('date_modification', timezone.now())
    ), reverse=True)
    
    total_changements = items_modifies + items_ajoutes + items_supprimes
    
    context = {
        'checklist': checklist,
        'items_par_categorie': items_par_categorie,
        'items_verifies_count': items_verifies_count,
        'changements': changements,
        'total_changements': total_changements,
        'items_modifies': items_modifies,
        'items_ajoutes': items_ajoutes,
        'items_supprimes': items_supprimes,
    }
    
    return render(request, 'checklist/verification_checklist.html', context)
# checklist/views.py

@login_required
def valider_item(request, item_id):
    """Valider/Refuser un item via AJAX"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    item = get_object_or_404(ItemChecklist, id=item_id)
    action = request.POST.get('action')
    
    if action == 'valider':
        item.statut_verification = 'valide'
        item.verifie = True
        item.verifie_par = request.user
        item.date_verification = timezone.now()
        item.modifie_depuis_verification = False
        item.save()
            
    elif action == 'refuser':
        item.statut_verification = 'refuse'
        item.verifie = False
        item.verifie_par = request.user
        item.date_verification = timezone.now()
        item.modifie_depuis_verification = False
        item.save()
    
    # Recharger l'item pour avoir les valeurs à jour
    item.refresh_from_db()
    checklist = item.checklist
    
    # Calculer la progression
    progression = checklist.progression()
    
    return JsonResponse({
        'success': True,
        'statut': item.statut_verification,
        'verifie': item.verifie,
        'progression': progression,
        'checklist_status': checklist.status
    })
# checklist/views.py

@login_required
def modifier_item(request, item_id):
    """Modifier le nom ou la quantité d'un item"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    item = get_object_or_404(ItemChecklist, id=item_id)
    
    nouveau_nom = request.POST.get('nom')
    nouvelle_quantite = request.POST.get('quantite')
    
    # Modification du nom (ajouter une note)
    if nouveau_nom and nouveau_nom != item.objet.nom:
        item.notes = f"Modifié: {nouveau_nom} (original: {item.objet.nom})"
    
    # Modification de la quantité
    if nouvelle_quantite:
        try:
            nouvelle_quantite_float = float(nouvelle_quantite)
            item.quantite = nouvelle_quantite_float
            # Le signal pre_save va gérer le changement de statut de CET item uniquement
        except ValueError:
            return JsonResponse({'error': 'Quantité invalide'}, status=400)
    
    # Sauvegarder (le signal gère le reste)
    item.save()
    
    return JsonResponse({
        'success': True,
        'nom': nouveau_nom or item.objet.nom,
        'quantite': float(item.quantite),
        'notes': item.notes,
        'modifie_depuis_verification': item.modifie_depuis_verification,
        'statut_verification': item.statut_verification
    })
@login_required
def finaliser_checklist(request, checklist_id):
    """Finaliser la vérification de la checklist"""
    
    if request.method != 'POST':
        return redirect('checklist:verification', checklist_id=checklist_id)
    
    checklist = get_object_or_404(Checklist, id=checklist_id)
    
    statut = request.POST.get('statut')  # 'validee' ou 'incomplete'
    notes = request.POST.get('notes_verificateur', '')
    
    checklist.status = statut
    checklist.notes_verificateur = notes
    checklist.date_verification = timezone.now()
    checklist.verificateur = request.user
    checklist.save()
    
    return redirect('checklist:dashboard_verificateur')


@login_required
def imprimer_livraisons(request):
    """Impression des livraisons pour une date"""
    
    date_str = request.GET.get('date')
    if not date_str:
        return HttpResponse("Date manquante", status=400)
    
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    livraisons = Livraison.objects.filter(
        date_livraison=selected_date
    ).select_related('mode_envoi').order_by('periode', 'heure_souhaitee')
    
    # Formater la date en français
    mois_fr = {
        1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
        5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
        9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
    }
    jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    date_formatee = f"{jours_fr[selected_date.weekday()]} {selected_date.day} {mois_fr[selected_date.month]} {selected_date.year}"
    
    context = {
        'livraisons': livraisons,
        'date_selectionnee': selected_date,
        'date_formatee': date_formatee,
    }
    
    return render(request, 'checklist/imprimer_livraisons.html', context)


@login_required
def imprimer_checklists(request):
    """Impression des checklists pour une date"""
    
    date_str = request.GET.get('date')
    if not date_str:
        return HttpResponse("Date manquante", status=400)
    
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    checklists = Checklist.objects.filter(
        date_evenement=selected_date
    ).select_related('creee_par').prefetch_related(
        Prefetch('items', queryset=ItemChecklist.objects.select_related('objet', 'objet__categorie').order_by('ordre'))
    ).order_by('-date_creation')
    
    # Formater la date
    mois_fr = {
        1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
        5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
        9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
    }
    jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    date_formatee = f"{jours_fr[selected_date.weekday()]} {selected_date.day} {mois_fr[selected_date.month]} {selected_date.year}"
    
    # Grouper items par catégorie pour chaque checklist
    for checklist in checklists:
        items_par_cat = {}
        for item in checklist.items.all():
            cat_nom = item.objet.categorie.nom
            if cat_nom not in items_par_cat:
                items_par_cat[cat_nom] = []
            items_par_cat[cat_nom].append(item)
        checklist.items_groupes = items_par_cat
    
    context = {
        'checklists': checklists,
        'date_selectionnee': selected_date,
        'date_formatee': date_formatee,
    }
    
    return render(request, 'checklist/imprimer_checklists.html', context)

from django.http import JsonResponse
from django.db.models import Sum
from django.utils.dateparse import parse_date

def api_total_objets(request):
    """API pour récupérer le total des objets par date"""
    date_str = request.GET.get('date')
    
    if not date_str:
        return JsonResponse({'error': 'Date manquante'}, status=400)
    
    date = parse_date(date_str)
    if not date:
        return JsonResponse({'error': 'Format de date invalide'}, status=400)
    
    # Récupérer toutes les checklists pour cette date
    checklists = Checklist.objects.filter(date_evenement=date)
    
    # Récupérer tous les items de ces checklists et additionner par objet
    objets_totaux = (
        ItemChecklist.objects
        .filter(checklist__in=checklists)
        .values('objet__nom')
        .annotate(total=Sum('quantite'))
        .order_by('objet__nom')
    )
    
    # Formater les résultats
    objets = [
        {
            'nom': obj['objet__nom'],
            'total': obj['total']
        }
        for obj in objets_totaux
    ]
    
    return JsonResponse({
        'date': date_str,
        'objets': objets,
        'total_items': len(objets)
    })

@login_required
def api_update_quantite(request):
    """API pour mettre à jour la quantité d'un objet"""
    try:
        data = json.loads(request.body)
        objet_id = data.get('objet_id')
        quantite = data.get('quantite')
        
        if objet_id is None or quantite is None:
            return JsonResponse({'error': 'Paramètres manquants'}, status=400)
        
        objet = ObjetChecklist.objects.get(id=objet_id)
        objet.quantite = max(0, int(quantite))
        objet.save()
        
        return JsonResponse({
            'success': True,
            'objet_id': objet.id,
            'quantite': objet.quantite
        })
        
    except ObjetChecklist.DoesNotExist:
        return JsonResponse({'error': 'Objet non trouvé'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)