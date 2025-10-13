# ==================== ventes/views.py ====================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Checklist, ItemChecklist, CategorieObjet, ObjetChecklist
from django.contrib import messages
import json
from hotel.models import Contrat
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required
def dashboard_vendeuse(request):
    """Dashboard principal avec calendrier et pagination"""
    today = timezone.now().date()
    start_date = today.replace(day=1)
    
    if start_date.month == 12:
        end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_date = start_date.replace(month=start_date.month + 1, day=1) - timedelta(days=1)
    
    # Checklists du mois pour le calendrier
    checklists_mois = Checklist.objects.filter(
        date_evenement__gte=start_date,
        date_evenement__lte=end_date
    ).select_related('creee_par').prefetch_related('items')
    
    # TOUTES les checklists pour le tableau
    all_checklists = Checklist.objects.select_related(
        'creee_par', 'contrat'
    ).prefetch_related('items').order_by('-date_evenement')
    
    checklists_par_date = {}
    for checklist in checklists_mois:
        date_str = checklist.date_evenement.strftime('%Y-%m-%d')
        if date_str not in checklists_par_date:
            checklists_par_date[date_str] = []
        checklists_par_date[date_str].append({
            'id': str(checklist.id),
            'name': checklist.numero_commande,
            'isMine': checklist.creee_par == request.user,
            'progression': checklist.progression()
        })
    
    # ============ CONTRATS ============
    from hotel.models import Contrat
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Récupérer tous les contrats
    contrats = Contrat.objects.select_related(
        'maitre_hotel', 'cree_par'
    ).order_by('-date_evenement')
    
    # Liste des maîtres d'hôtel pour les filtres
    maitres_hotel = User.objects.filter(role='maitre_hotel', is_active=True)
    
    # ============ SOUMISSIONS ============
    from ventes.models import Soumission
    
    # Récupérer toutes les soumissions
    soumissions = Soumission.objects.select_related(
        'cree_par'
    ).order_by('-date_evenement')
    # =====================================
    
    context = {
        'checklists_data': json.dumps(checklists_par_date),
        'all_checklists': all_checklists,
        'contrats': contrats,
        'maitres_hotel': maitres_hotel,
        'soumissions': soumissions,
        'today': today.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'ventes/vendeuse/dashboard.html', context)
@login_required
def checklists_by_date(request, date):
    """Liste des checklists pour une date donnée"""
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Date invalide")
        return redirect('ventes:dashboard_vendeuse')
    
    # Filtrer selon l'onglet (all ou mine)
    view_type = request.GET.get('view', 'all')
    
    # CORRECTION: Utiliser date_evenement
    checklists = Checklist.objects.filter(date_evenement=date_obj)
    
    if view_type == 'mine':
        checklists = checklists.filter(creee_par=request.user)
    
    checklists = checklists.select_related('creee_par').prefetch_related('items')
    
    context = {
        'date': date_obj,
        'checklists': checklists,
        'view_type': view_type,
    }
    
    return render(request, 'ventes/vendeuse/checklists_date.html', context)



@login_required
def checklist_detail(request, pk):
    """Détail d'une checklist avec possibilité de validation"""
    checklist = get_object_or_404(
        Checklist.objects.select_related('creee_par', 'verificateur'),
        pk=pk
    )
    
    items = checklist.items.select_related(
        'objet__categorie', 
        'verifie_par'
    ).order_by('objet__categorie__ordre', 'objet__nom')
    
    # Grouper par catégorie
    items_par_categorie = {}
    for item in items:
        cat_nom = item.objet.categorie.nom
        if cat_nom not in items_par_categorie:
            items_par_categorie[cat_nom] = []
        items_par_categorie[cat_nom].append(item)
    
    # Calculer les statistiques
    total_items = items.count()
    verified_items = items.filter(statut_verification = 'valide').count()
    pending_items = total_items - verified_items
    
    # Vérifier les permissions
    can_edit = (
        checklist.creee_par == request.user or 
        request.user.groups.filter(name__in=['Responsable', 'Checklist']).exists()
    )
    
    context = {
        'checklist': checklist,
        'items_par_categorie': items_par_categorie,
        'can_edit': can_edit,
        'total_items': total_items,
        'verified_items': verified_items,
        'pending_items': pending_items,
    }
    
    return render(request, 'ventes/vendeuse/checklist_detail.html', context)


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Prefetch
from .models import Checklist, ItemChecklist, CategorieObjet, ObjetChecklist


@login_required
def checklist_create(request):
    """Créer une nouvelle checklist"""
    categories = CategorieObjet.objects.prefetch_related(
        Prefetch('objets', queryset=ObjetChecklist.objects.filter(actif=True))
    ).filter(objets__actif=True).distinct()
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        numero_commande_brut = request.POST.get('numero_commande', '').strip()
        date_evenement = request.POST.get('date_evenement')
        notes = request.POST.get('notes', '')
        items_data = request.POST.getlist('items[]')
        
        # ✅ FORMATER LE NUMÉRO DE COMMANDE
        # Si l'utilisateur entre "49589", on transforme en "CMD-49589"
        if numero_commande_brut:
            # Enlever le préfixe CMD- s'il existe déjà (au cas où)
            numero_sans_prefix = numero_commande_brut.replace('CMD-', '').strip()
            # Ajouter le préfixe CMD-
            numero_commande = f"CMD-{numero_sans_prefix}"
        else:
            numero_commande = ''
        
        # Debug
        print(f"DEBUG - numero_commande_brut: {numero_commande_brut}")
        print(f"DEBUG - numero_commande formaté: {numero_commande}")
        print(f"nom: {nom}, date: {date_evenement}")
        
        # Vérifier que les champs obligatoires sont présents
        if not nom or not numero_commande or not date_evenement:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
            context = {
                'categories': categories,
                'form_data': {
                    'nom': nom,
                    'numero_commande': numero_commande_brut,
                    'date_evenement': date_evenement,
                    'notes': notes
                }
            }
            return render(request, 'ventes/vendeuse/checklist_create.html', context)
        
        # Vérifier si le numéro de commande existe déjà
        if Checklist.objects.filter(numero_commande=numero_commande).exists():
            messages.error(request, f"Une checklist avec le numéro {numero_commande} existe déjà.")
            context = {
                'categories': categories,
                'form_data': {
                    'nom': nom,
                    'numero_commande': numero_commande_brut,
                    'date_evenement': date_evenement,
                    'notes': notes
                }
            }
            return render(request, 'ventes/vendeuse/checklist_create.html', context)
        
        try:
            # Créer la checklist
            checklist = Checklist.objects.create(
                nom=nom,
                numero_commande=numero_commande,  # ✅ Avec le préfixe CMD-
                creee_par=request.user,
                date_evenement=date_evenement,
                notes=notes,
                status='brouillon'
            )
            
            # Ajouter les items
            for item_str in items_data:
                try:
                    objet_id, quantite = item_str.split(':')
                    ItemChecklist.objects.create(
                        checklist=checklist,
                        objet_id=int(objet_id),
                        quantite=float(quantite)
                    )
                except (ValueError, IndexError) as e:
                    print(f"Erreur parsing item {item_str}: {e}")
                    continue
            
            messages.success(request, f"✅ Checklist {numero_commande} créée avec succès!")
            return redirect('ventes:checklist_detail', pk=checklist.pk)
        
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'ventes/vendeuse/checklist_create.html', context)


@login_required
def checklist_edit(request, pk):
    """Modifier une checklist"""
    checklist = get_object_or_404(Checklist, pk=pk)
    
    # Vérifier les permissions
    if (checklist.creee_par != request.user and 
        not request.user.groups.filter(name__in=['Responsable', 'Checklist']).exists()):
        messages.error(request, "Vous n'avez pas la permission de modifier cette checklist")
        return redirect('ventes:checklist_detail', pk=pk)
    
    categories = CategorieObjet.objects.prefetch_related(
        Prefetch('objets', queryset=ObjetChecklist.objects.filter(actif=True))
    ).filter(objets__actif=True).distinct()
    
    items = checklist.items.select_related('objet__categorie')
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        numero_commande_brut = request.POST.get('numero_commande', '').strip()
        date_evenement = request.POST.get('date_evenement')
        notes = request.POST.get('notes', '')
        items_data = request.POST.getlist('items[]')
        
        # ✅ FORMATER LE NUMÉRO DE COMMANDE
        if numero_commande_brut:
            numero_sans_prefix = numero_commande_brut.replace('CMD-', '').strip()
            numero_commande = f"CMD-{numero_sans_prefix}"
        else:
            numero_commande = ''
        
        # Debug
        print(f"POST data: nom={nom}, numero={numero_commande}, date={date_evenement}")
        print(f"Items: {items_data}")
        
        # Vérifier les champs obligatoires
        if not nom or not numero_commande or not date_evenement:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
            context = {
                'checklist': checklist,
                'categories': categories,
                'items': items,
            }
            return render(request, 'ventes/vendeuse/checklist_edit.html', context)
        
        # Vérifier si le numéro de commande existe (sauf pour la checklist actuelle)
        if Checklist.objects.filter(numero_commande=numero_commande).exclude(pk=pk).exists():
            messages.error(request, f"Une autre checklist avec le numéro {numero_commande} existe déjà.")
            context = {
                'checklist': checklist,
                'categories': categories,
                'items': items,
            }
            return render(request, 'ventes/vendeuse/checklist_edit.html', context)
        
        try:
            # Mettre à jour les informations de base de la checklist
            checklist.nom = nom
            checklist.numero_commande = numero_commande  # ✅ Avec le préfixe CMD-
            checklist.date_evenement = date_evenement
            checklist.notes = notes
            checklist.save()
            
            # Convertir les nouvelles données en dictionnaire {objet_id: quantite}
            new_items = {}
            for item_str in items_data:
                try:
                    objet_id, quantite = item_str.split(':')
                    new_items[int(objet_id)] = float(quantite)
                except (ValueError, IndexError):
                    continue
            
            # Récupérer les items existants
            existing_items = {item.objet_id: item for item in checklist.items.all()}
            
            # 1. Mettre à jour ou supprimer les items existants
            for objet_id, item in existing_items.items():
                if objet_id in new_items:
                    # Item existe toujours, mettre à jour la quantité si nécessaire
                    nouvelle_quantite = new_items[objet_id]
                    if item.quantite != nouvelle_quantite:
                        item.quantite = nouvelle_quantite
                        item.save()
                else:
                    # Item n'est plus dans la liste
                    if item.statut_verification in ['valide', 'refuse']:
                        messages.warning(
                            request, 
                            f"⚠️ L'item '{item.objet.nom}' n'a pas été supprimé car il a déjà été {item.get_statut_verification_display().lower()}."
                        )
                    else:
                        item.delete()
            
            # 2. Ajouter les nouveaux items
            for objet_id, quantite in new_items.items():
                if objet_id not in existing_items:
                    ItemChecklist.objects.create(
                        checklist=checklist,
                        objet_id=objet_id,
                        quantite=quantite
                    )
            
            messages.success(request, "✅ Checklist modifiée avec succès!")
            return redirect('ventes:checklist_detail', pk=pk)
        
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    context = {
        'checklist': checklist,
        'categories': categories,
        'items': items,
    }
    
    return render(request, 'ventes/vendeuse/checklist_edit.html', context)


@login_required
def checklist_delete(request, pk):
    """Supprimer une checklist"""
    checklist = get_object_or_404(Checklist, pk=pk)
    
    # Vérifier les permissions
    if (checklist.creee_par != request.user and 
        not request.user.groups.filter(name__in=['Responsable', 'Checklist']).exists()):
        messages.error(request, "Vous n'avez pas la permission de supprimer cette checklist")
        return redirect('ventes:checklist_detail', pk=pk)
    
    if request.method == 'POST':
        numero_commande = checklist.numero_commande
        checklist.delete()
        messages.success(request, f"Checklist {numero_commande} supprimée avec succès!")
        return redirect('ventes:dashboard_responsable')
    
    return render(request, 'ventes/vendeuse/checklist_confirm_delete.html', {'checklist': checklist})

@login_required
def checklist_duplicate(request, pk):
    """Dupliquer une checklist"""
    original = get_object_or_404(Checklist, pk=pk)
    
    # Générer un nouveau numéro unique
    base_num = f"{original.numero_commande} - Copie"
    numero_commande = base_num
    counter = 1
    
    while Checklist.objects.filter(numero_commande=numero_commande).exists():
        numero_commande = f"{base_num} {counter}"
        counter += 1
    
    try:
        # Créer une copie
        nouvelle_checklist = Checklist.objects.create(
            numero_commande=numero_commande,
            nom=f"{original.nom} - Copie",
            creee_par=request.user,
            date_evenement=original.date_evenement,
            notes=original.notes,
            status='en_preparation'
        )
        
        # Copier les items
        for item in original.items.all():
            ItemChecklist.objects.create(
                checklist=nouvelle_checklist,
                objet=item.objet,
                quantite=item.quantite
            )
        
        messages.success(request, f"Checklist dupliquée avec succès! Nouveau numéro: {nouvelle_checklist.numero_commande}")
        return redirect('ventes:checklist_detail', pk=nouvelle_checklist.pk)
    
    except Exception as e:
        messages.error(request, f"Erreur lors de la duplication: {str(e)}")
        return redirect('ventes:checklist_detail', pk=pk)


@login_required
def toggle_item_validation(request, pk):
    """Toggle validation d'un item (AJAX)"""
    if request.method == 'POST':
        item = get_object_or_404(ItemChecklist, pk=pk)
        
        # Toggle la validation - UTILISER LE BON CHAMP
        item.verifie = not item.verifie  # Au lieu de 'valide'
        if item.verifie:
            item.date_verification = timezone.now()  # Au lieu de 'date_validation'
            item.verifie_par = request.user  # Au lieu de 'valideur'
        else:
            item.date_verification = None
            item.verifie_par = None
        item.save()
        
        # Vérifier si toute la checklist est complétée
        checklist = item.checklist
        all_valid = all(i.verifie for i in checklist.items.all())
        
        # Mettre à jour le statut
        if all_valid:
            checklist.status = 'validee'
            checklist.verificateur = request.user
            checklist.date_verification = timezone.now()
        else:
            checklist.status = 'en_cours'  # ou 'brouillon'
        checklist.save()
        
        return JsonResponse({
            'success': True,
            'verifie': item.verifie,
            'progression': checklist.progression(),  # Méthode de votre modèle
            'status': checklist.status
        })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=400)

@login_required
def update_item_quantity(request, pk):
    """Mettre à jour la quantité d'un item (AJAX)"""
    if request.method == 'POST':
        item = get_object_or_404(ItemChecklist, pk=pk)
        
        try:
            quantite = int(request.POST.get('quantite', 1))
            
            if quantite > 0:
                item.quantite = quantite
                item.save()
                return JsonResponse({
                    'success': True, 
                    'quantite': quantite
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': 'La quantité doit être supérieure à 0'
                }, status=400)
        
        except ValueError:
            return JsonResponse({
                'success': False, 
                'error': 'Quantité invalide'
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=400)


from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.db.models import Count
from .models import Checklist, ObjetChecklist, CategorieObjet

User = get_user_model()

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count
from collections import defaultdict
from datetime import date
from .models import Checklist, ObjetChecklist, CategorieObjet

User = get_user_model()

@login_required
def dashboard_responsable(request):
    """Dashboard pour les responsables ventes"""
    
    # Vérifier que l'utilisateur est responsable ventes
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    # Récupérer toutes les checklists
    checklists = Checklist.objects.select_related(
        'creee_par'
    ).order_by('-date_evenement')[:50]
    
    # Récupérer tous les objets
    objets = ObjetChecklist.objects.select_related(
        'categorie'
    ).order_by('categorie__ordre', 'ordre', 'nom')
    
    # Récupérer toutes les catégories avec le nombre d'objets
    categories = CategorieObjet.objects.annotate(
        objets_count=Count('objets')
    ).order_by('ordre', 'nom')
    
    # Récupérer toutes les vendeuses (role = vendeur)
    vendeuses = User.objects.filter(
        role='vendeur'
    ).annotate(
        checklists_count=Count('checklists_creees')
    ).order_by('first_name', 'last_name')
    
    # Récupérer tous les contrats
    contrats = Contrat.objects.select_related(
        'maitre_hotel', 'cree_par'
    ).order_by('-date_evenement')

    contrats_by_date = {}
    for contrat in contrats:
        date_key = contrat.date_evenement.strftime('%Y-%m-%d')
        if date_key not in contrats_by_date:
            contrats_by_date[date_key] = []
        contrats_by_date[date_key].append(contrat)
    
    # Organiser les checklists par date pour le calendrier
    checklists_by_date = defaultdict(list)
    all_checklists = Checklist.objects.select_related('creee_par').all()
    
    for checklist in all_checklists:
        date_str = checklist.date_evenement.strftime('%Y-%m-%d')
        checklists_by_date[date_str].append(checklist)

    soumissions = Soumission.objects.select_related('cree_par').order_by('-date_evenement')
    
    # Organiser les soumissions par date pour le calendrier
    soumissions_by_date = {}
    for soumission in soumissions:
        date_key = soumission.date_evenement.strftime('%Y-%m-%d')
        if date_key not in soumissions_by_date:
            soumissions_by_date[date_key] = []
        soumissions_by_date[date_key].append(soumission)
    
    # Statistiques
    stats = {
        'total_checklists': Checklist.objects.count(),
        'total_objets': ObjetChecklist.objects.filter(actif=True).count(),
        'total_categories': CategorieObjet.objects.filter(actif=True).count(),
        'total_vendeuses': User.objects.filter(role='vendeur', is_active=True).count(),
        'total_soumissions': Soumission.objects.count(),
    }
    
    context = {
        'checklists': checklists,
        'objets': objets,
        'categories': categories,
        'vendeuses': vendeuses,
        'contrats': contrats,
        'soumissions': soumissions,
        'stats': stats,
        'checklists_by_date': dict(checklists_by_date),
        'today': date.today().strftime('%Y-%m-%d'),
        'contrats_by_date': contrats_by_date,
        'soumissions_by_date': soumissions_by_date,
    }
    
    return render(request, 'ventes/responsable/dashboard_responsable.html', context)


# views.py

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ObjetChecklist, CategorieObjet

User = get_user_model()

# ============ CRUD OBJETS ============

@login_required
def objet_create(request):
    """Créer un nouvel objet"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    categories = CategorieObjet.objects.filter(actif=True).order_by('ordre', 'nom')
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        categorie_id = request.POST.get('categorie')
        unite = request.POST.get('unite', 'unité')
        description = request.POST.get('description', '')
        ordre = request.POST.get('ordre', 0)
        actif = request.POST.get('actif') == 'on'
        
        if not nom or not categorie_id:
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            return render(request, 'ventes/responsable/objet_form.html', {
                'categories': categories,
                'form': request.POST
            })
        
        try:
            ObjetChecklist.objects.create(
                nom=nom,
                categorie_id=categorie_id,
                unite=unite,
                description=description,
                ordre=int(ordre),
                actif=actif
            )
            messages.success(request, f"Objet '{nom}' créé avec succès!")
            return redirect('ventes:dashboard_responsable')
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
    
    return render(request, 'ventes/responsable/objet_form.html', {'categories': categories})


@login_required
def objet_edit(request, pk):
    """Modifier un objet"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    objet = get_object_or_404(ObjetChecklist, pk=pk)
    categories = CategorieObjet.objects.filter(actif=True).order_by('ordre', 'nom')
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        categorie_id = request.POST.get('categorie')
        unite = request.POST.get('unite', 'unité')
        description = request.POST.get('description', '')
        ordre = request.POST.get('ordre', 0)
        actif = request.POST.get('actif') == 'on'
        
        if not nom or not categorie_id:
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            return render(request, 'ventes/responsable/objet_form.html', {
                'objet': objet,
                'categories': categories,
                'form': request.POST
            })
        
        try:
            objet.nom = nom
            objet.categorie_id = categorie_id
            objet.unite = unite
            objet.description = description
            objet.ordre = int(ordre)
            objet.actif = actif
            objet.save()
            
            messages.success(request, f"Objet '{nom}' modifié avec succès!")
            return redirect('ventes:dashboard_responsable')
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
    
    form_data = {
        'nom': {'value': objet.nom},
        'categorie': {'value': objet.categorie_id},
        'unite': {'value': objet.unite},
        'description': {'value': objet.description},
        'ordre': {'value': objet.ordre},
        'actif': {'value': objet.actif},
    }
    
    return render(request, 'ventes/responsable/objet_form.html', {
        'objet': objet,
        'categories': categories,
        'form': form_data
    })


@login_required
def objet_delete(request, pk):
    """Supprimer un objet"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    objet = get_object_or_404(ObjetChecklist, pk=pk)
    
    if request.method == 'POST':
        nom = objet.nom
        objet.delete()
        messages.success(request, f"Objet '{nom}' supprimé avec succès!")
        return redirect('ventes:dashboard_responsable')
    
    return render(request, 'ventes/responsable/objet_confirm_delete.html', {'objet': objet})


# ============ CRUD CATÉGORIES ============

@login_required
def categorie_create(request):
    """Créer une nouvelle catégorie"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    colors = [
        ('slate', 'Ardoise'), ('red', 'Rouge'), ('orange', 'Orange'),
        ('amber', 'Ambre'), ('yellow', 'Jaune'), ('lime', 'Citron vert'),
        ('green', 'Vert'), ('emerald', 'Émeraude'), ('teal', 'Sarcelle'),
        ('cyan', 'Cyan'), ('sky', 'Ciel'), ('blue', 'Bleu'),
        ('indigo', 'Indigo'), ('violet', 'Violet'), ('purple', 'Violet foncé'),
        ('fuchsia', 'Fuchsia'), ('pink', 'Rose'), ('rose', 'Rose foncé'),
    ]
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        icone = request.POST.get('icone', '')
        couleur = request.POST.get('couleur', 'slate')
        ordre = request.POST.get('ordre', 0)
        actif = request.POST.get('actif') == 'on'
        
        if not nom:
            messages.error(request, "Le nom est obligatoire")
            return render(request, 'ventes/responsable/categorie_form.html', {
                'colors': colors,
                'form': request.POST
            })
        
        try:
            CategorieObjet.objects.create(
                nom=nom,
                icone=icone,
                couleur=couleur,
                ordre=int(ordre),
                actif=actif
            )
            messages.success(request, f"Catégorie '{nom}' créée avec succès!")
            return redirect('ventes:dashboard_responsable')
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
    
    return render(request, 'ventes/responsable/categorie_form.html', {'colors': colors})


@login_required
def categorie_edit(request, pk):
    """Modifier une catégorie"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    categorie = get_object_or_404(CategorieObjet, pk=pk)
    colors = [
        ('slate', 'Ardoise'), ('red', 'Rouge'), ('orange', 'Orange'),
        ('amber', 'Ambre'), ('yellow', 'Jaune'), ('lime', 'Citron vert'),
        ('green', 'Vert'), ('emerald', 'Émeraude'), ('teal', 'Sarcelle'),
        ('cyan', 'Cyan'), ('sky', 'Ciel'), ('blue', 'Bleu'),
        ('indigo', 'Indigo'), ('violet', 'Violet'), ('purple', 'Violet foncé'),
        ('fuchsia', 'Fuchsia'), ('pink', 'Rose'), ('rose', 'Rose foncé'),
    ]
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        icone = request.POST.get('icone', '')
        couleur = request.POST.get('couleur', 'slate')
        ordre = request.POST.get('ordre', 0)
        actif = request.POST.get('actif') == 'on'
        
        if not nom:
            messages.error(request, "Le nom est obligatoire")
            return render(request, 'ventes/responsable/categorie_form.html', {
                'categorie': categorie,
                'colors': colors,
                'form': request.POST
            })
        
        try:
            categorie.nom = nom
            categorie.icone = icone
            categorie.couleur = couleur
            categorie.ordre = int(ordre)
            categorie.actif = actif
            categorie.save()
            
            messages.success(request, f"Catégorie '{nom}' modifiée avec succès!")
            return redirect('ventes:dashboard_responsable')
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
    
    form_data = {
        'nom': {'value': categorie.nom},
        'icone': {'value': categorie.icone},
        'couleur': {'value': categorie.couleur},
        'ordre': {'value': categorie.ordre},
        'actif': {'value': categorie.actif},
    }
    
    return render(request, 'ventes/responsable/categorie_form.html', {
        'categorie': categorie,
        'colors': colors,
        'form': form_data
    })


@login_required
def categorie_delete(request, pk):
    """Supprimer une catégorie"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    categorie = get_object_or_404(CategorieObjet, pk=pk)
    
    if request.method == 'POST':
        if categorie.objets.exists():
            messages.error(request, "Impossible de supprimer une catégorie contenant des objets")
            return redirect('ventes:dashboard_responsable')
        
        nom = categorie.nom
        categorie.delete()
        messages.success(request, f"Catégorie '{nom}' supprimée avec succès!")
        return redirect('ventes:dashboard_responsable')
    
    return render(request, 'ventes/responsable/categorie_confirm_delete.html', {'categorie': categorie})


# ============ CRUD VENDEUSES ============

@login_required
def vendeuse_create(request):
    """Créer une nouvelle vendeuse"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        is_active = request.POST.get('is_active') == 'on'
        
        # Validation
        if not all([username, first_name, last_name, email, password1, password2]):
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            return render(request, 'ventes/responsable/vendeuse_form.html', {'form': request.POST})
        
        if password1 != password2:
            messages.error(request, "Les mots de passe ne correspondent pas")
            return render(request, 'ventes/responsable/vendeuse_form.html', {'form': request.POST})
        
        if len(password1) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères")
            return render(request, 'ventes/responsable/vendeuse_form.html', {'form': request.POST})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur existe déjà")
            return render(request, 'ventes/responsable/vendeuse_form.html', {'form': request.POST})
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà utilisé")
            return render(request, 'ventes/responsable/vendeuse_form.html', {'form': request.POST})
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                role='vendeur'
            )
            
            
            
            messages.success(request, f"Vendeuse '{user.get_full_name()}' créée avec succès!")
            return redirect('ventes:dashboard_responsable')
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
    
    return render(request, 'ventes/responsable/vendeuse_form.html', {})


@login_required
def vendeuse_edit(request, pk):
    """Modifier une vendeuse"""
    if request.user.role != 'resp_ventes':
        messages.error(request, "Accès réservé aux responsables ventes")
        return redirect('ventes:dashboard_vendeuse')
    
    vendeuse = get_object_or_404(User, pk=pk, groups__name='Vendeuse')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        is_active = request.POST.get('is_active') == 'on'
        
        if not all([first_name, last_name, email]):
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            return render(request, 'ventes/responsable/vendeuse_form.html', {
                'vendeuse': vendeuse,
                'form': request.POST
            })
        
        # Vérifier si l'email existe déjà (sauf pour cet utilisateur)
        if User.objects.filter(email=email).exclude(pk=pk).exists():
            messages.error(request, "Cet email est déjà utilisé")
            return render(request, 'ventes/vendeuse_form.html', {
                'vendeuse': vendeuse,
                'form': request.POST
            })
        
        try:
            vendeuse.first_name = first_name
            vendeuse.last_name = last_name
            vendeuse.email = email
            vendeuse.is_active = is_active
            vendeuse.save()
            
            messages.success(request, f"Vendeuse '{vendeuse.get_full_name()}' modifiée avec succès!")
            return redirect('ventes:dashboard_responsable')
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
    
    form_data = {
        'username': {'value': vendeuse.username},
        'first_name': {'value': vendeuse.first_name},
        'last_name': {'value': vendeuse.last_name},
        'email': {'value': vendeuse.email},
        'is_active': {'value': vendeuse.is_active},
    }
    
    return render(request, 'ventes/responsable/vendeuse_form.html', {
        'vendeuse': vendeuse,
        'form': form_data
    })


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from users.models import CustomUser

@login_required
def vendeuse_delete(request, pk):
    """Suppression d'une vendeuse"""
    
    # Vérifier que l'utilisateur a les droits (responsable uniquement)
    if request.user.role != 'resp_ventes':
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('ventes:dashboard_vendeuse')
    
    try:
        # Récupérer l'utilisateur vendeuse
        vendeuse = get_object_or_404(CustomUser, pk=pk, role='vendeur')
        
        if request.method == 'POST':
            vendeuse_nom = vendeuse.get_full_name() or vendeuse.username
            vendeuse.delete()
            messages.success(request, f"La vendeuse {vendeuse_nom} a été supprimée avec succès.")
            return redirect('ventes:dashboard_responsable')
        
        # Si GET, afficher une page de confirmation
        context = {
            'vendeuse': vendeuse,
        }
        return render(request, 'ventes/responsable/vendeuse_confirm_delete.html', context)
        
    except Http404:
        messages.error(request, "Cette vendeuse n'existe pas ou a déjà été supprimée.")
        return redirect('ventes:dashboard_responsable')
    except Exception as e:
        messages.error(request, f"Erreur lors de la suppression : {str(e)}")
        return redirect('ventes:dashboard_responsable')

# ventes/views.py

@login_required
def supprimer_item_checklist(request, item_id):
    """Supprimer un item d'une checklist avec confirmation si vérifié"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    item = get_object_or_404(ItemChecklist, id=item_id)
    objet_nom = item.objet.nom
    statut = item.statut_verification
    
    # ✅ Si l'item a été vérifié (validé ou refusé), demander confirmation
    if item.date_verification and not request.POST.get('force_delete'):
        return JsonResponse({
            'success': False,
            'needs_confirmation': True,
            'message': f"⚠️ L'item '{objet_nom}' a été {item.get_statut_verification_display().lower()}.\n\nSa suppression créera une alerte pour le vérificateur.\n\nÊtes-vous sûr de vouloir continuer ?",
            'item_id': item_id,
            'statut': statut
        })
    
    # Suppression confirmée ou item jamais vérifié
    item.delete()  # Le signal post_delete gère l'historique automatiquement
    
    return JsonResponse({
        'success': True,
        'message': f"Item '{objet_nom}' supprimé avec succès"
    })

# ============ CRUD CONTRATS - Ajout à ventes/views.py ============

from hotel.models import Contrat, PhotoContrat, HistoriqueContrat
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def contrat_list(request):
    """Liste des contrats (onglet Contrats du dashboard)"""
    contrats = Contrat.objects.select_related(
        'maitre_hotel', 'livraison', 'checklist', 'cree_par'
    ).order_by('-date_evenement')
    
    # Filtres optionnels
    status_filter = request.GET.get('status')
    maitre_hotel_filter = request.GET.get('maitre_hotel')
    
    if status_filter:
        contrats = contrats.filter(status=status_filter)
    
    if maitre_hotel_filter:
        contrats = contrats.filter(maitre_hotel_id=maitre_hotel_filter)
    
    # Liste des maîtres d'hôtel pour le filtre
    maitres_hotel = User.objects.filter(role='maitre_hotel', is_active=True)
    
    context = {
        'contrats': contrats,
        'maitres_hotel': maitres_hotel,
        'status_choices': Contrat.STATUS_CHOICES,
    }
    
    return render(request, 'ventes/contrats/contrat_list.html', context)


@login_required
def contrat_create_step1(request):
    """Étape 1: Identifiants + associer un maître d'hôtel"""
    
    # ✅ NETTOYER LA SESSION au début si c'est une nouvelle création
    if request.method == 'GET' and 'new' in request.GET:
        # Supprimer les données de session si on commence une nouvelle création
        if 'contrat_step1' in request.session:
            del request.session['contrat_step1']
        if 'contrat_step2' in request.session:
            del request.session['contrat_step2']
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        numero_contrat_input = request.POST.get('numero_contrat', '').strip()
        nom_evenement = request.POST.get('nom_evenement')
        maitre_hotel_id = request.POST.get('maitre_hotel')
        checklist_id = request.POST.get('checklist')
        livraison_id = request.POST.get('livraison')
        
        # Validation
        if not numero_contrat_input or not nom_evenement:
            messages.error(request, "Le numéro de contrat et le nom de l'événement sont obligatoires")
            return redirect('ventes:contrat_create_step1')
        
        # Ajouter automatiquement le préfixe CMD-
        numero_contrat = f"CMD-{numero_contrat_input}"
        
        # Vérifier unicité du numéro
        if Contrat.objects.filter(numero_contrat=numero_contrat).exists():
            messages.error(request, f"Un contrat avec le numéro {numero_contrat} existe déjà")
            return redirect('ventes:contrat_create_step1')
        
        # Stocker en session pour passer à l'étape suivante
        request.session['contrat_step1'] = {
            'numero_contrat': numero_contrat,
            'nom_evenement': nom_evenement,
            'maitre_hotel_id': maitre_hotel_id if maitre_hotel_id else None,
            'checklist_id': checklist_id if checklist_id else None,
            'livraison_id': livraison_id if livraison_id else None,
        }
        
        return redirect('ventes:contrat_create_step2')
    
    # GET - Afficher le formulaire
    maitres_hotel = User.objects.filter(role='maitre_hotel', is_active=True)
    checklists = Checklist.objects.filter(status='validee').order_by('-date_evenement')
    
    # Importer le modèle Livraison si disponible
    try:
        from livraison.models import Livraison
        livraisons = Livraison.objects.filter(statut='planifiee').order_by('-date_livraison')
    except:
        livraisons = []
    
    context = {
        'maitres_hotel': maitres_hotel,
        'checklists': checklists,
        'livraisons': livraisons,
    }
    
    return render(request, 'ventes/contrats/contrat_create_step1.html', context)
# Dans ventes/views.py - Remplacer la fonction contrat_create_step2

from django.conf import settings

@login_required
def contrat_create_step2(request):
    """Étape 2: Informations client + Adresse + Date/heure + Infos supplémentaires"""
    
    # Vérifier que l'étape 1 est complétée
    if 'contrat_step1' not in request.session:
        messages.warning(request, "Veuillez d'abord compléter l'étape 1")
        return redirect('ventes:contrat_create_step1')
    
    if request.method == 'POST':
        # Récupérer toutes les données
        step2_data = {
            'client_nom': request.POST.get('client_nom'),
            'client_telephone': request.POST.get('client_telephone'),
            'client_email': request.POST.get('client_email', ''),
            'contact_sur_site': request.POST.get('contact_sur_site', ''),
            'adresse_complete': request.POST.get('adresse_complete'),
            'ville': request.POST.get('ville', 'Montréal'),
            'code_postal': request.POST.get('code_postal', ''),
            'date_evenement': request.POST.get('date_evenement'),
            'heure_debut_prevue': request.POST.get('heure_debut_prevue'),
            'heure_fin_prevue': request.POST.get('heure_fin_prevue'),
            'nb_convives': request.POST.get('nb_convives', 0),
            'informations_supplementaires': request.POST.get('informations_supplementaires', ''),
            'instructions_speciales': request.POST.get('instructions_speciales', ''),
        }
        
        # Validation
        required_fields = ['client_nom', 'client_telephone', 'adresse_complete', 
                          'date_evenement', 'heure_debut_prevue', 'heure_fin_prevue']
        
        if not all(step2_data.get(field) for field in required_fields):
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            context = {
                'form_data': step2_data,
                'google_api_key': settings.GOOGLE_PLACES_API_KEY,  # ✅ Ajouter la clé API
            }
            return render(request, 'ventes/contrats/contrat_create_step2.html', context)
        
        # Stocker en session
        request.session['contrat_step2'] = step2_data
        
        return redirect('ventes:contrat_create_step3')
    
    # GET - Afficher le formulaire
    # Pré-remplir avec les données de la checklist si disponible
    form_data = request.session.get('contrat_step2', {})
    
    # ✅ Si pas de données en session, utiliser les valeurs par défaut de la checklist (si existe)
    if not form_data:
        step1 = request.session.get('contrat_step1', {})
        if step1.get('checklist_id'):
            try:
                from .models import Checklist
                checklist = Checklist.objects.get(pk=step1['checklist_id'])
                form_data = {
                    'date_evenement': checklist.date_evenement.strftime('%Y-%m-%d'),
                    'ville': 'Montréal',
                    'informations_supplementaires': checklist.notes if checklist.notes else '',
                }
            except:
                pass
    
    context = {
        'form_data': form_data,
        'google_api_key': settings.GOOGLE_MAPS_API_KEY,  # ✅ Ajouter la clé API
    }
    
    return render(request, 'ventes/contrats/contrat_create_step2.html', context)

@login_required
def contrat_create_step3(request):
    """Étape 3: Déroulé de l'événement + Confirmation avec résumé"""
    
    # Vérifier que les étapes précédentes sont complétées
    if 'contrat_step1' not in request.session or 'contrat_step2' not in request.session:
        messages.warning(request, "Veuillez compléter les étapes précédentes")
        return redirect('ventes:contrat_create_step1')
    
    if request.method == 'POST':
        deroule_evenement = request.POST.get('deroule_evenement', '')
        
        # Récupérer toutes les données des étapes précédentes
        step1 = request.session.get('contrat_step1')
        step2 = request.session.get('contrat_step2')
        
        try:
            # Créer le contrat
            contrat = Contrat.objects.create(
                # Étape 1
                numero_contrat=step1['numero_contrat'],
                nom_evenement=step1['nom_evenement'],
                maitre_hotel_id=step1.get('maitre_hotel_id'),
                checklist_id=step1.get('checklist_id'),
                livraison_id=step1.get('livraison_id'),
                
                # Étape 2
                client_nom=step2['client_nom'],
                client_telephone=step2['client_telephone'],
                client_email=step2.get('client_email', ''),
                contact_sur_site=step2.get('contact_sur_site', ''),
                adresse_complete=step2['adresse_complete'],
                ville=step2.get('ville', 'Montréal'),
                code_postal=step2.get('code_postal', ''),
                date_evenement=step2['date_evenement'],
                heure_debut_prevue=step2['heure_debut_prevue'],
                heure_fin_prevue=step2['heure_fin_prevue'],
                nb_convives=int(step2.get('nb_convives', 0)),
                informations_supplementaires=step2.get('informations_supplementaires', ''),
                instructions_speciales=step2.get('instructions_speciales', ''),
                
                # Étape 3
                deroule_evenement=deroule_evenement,
                
                # Metadata
                cree_par=request.user,
                status='planifie'
            )
            
            # Créer l'historique
            HistoriqueContrat.objects.create(
                contrat=contrat,
                type_action='creation',
                description=f"Contrat créé par {request.user.get_full_name()}",
                effectue_par=request.user
            )
            
            # Nettoyer la session
            del request.session['contrat_step1']
            del request.session['contrat_step2']
            
            messages.success(request, f"✅ Contrat {contrat.numero_contrat} créé avec succès!")
            return redirect('ventes:contrat_detail', pk=contrat.pk)
        
        except Exception as e:
            messages.error(request, f"Erreur lors de la création du contrat: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # GET - Afficher le résumé et le formulaire de déroulé
    step1 = request.session.get('contrat_step1')
    step2 = request.session.get('contrat_step2')
    
    # Récupérer les objets liés pour l'affichage
    maitre_hotel = None
    if step1.get('maitre_hotel_id'):
        try:
            maitre_hotel = User.objects.get(pk=step1['maitre_hotel_id'])
        except:
            pass
    
    checklist = None
    if step1.get('checklist_id'):
        try:
            checklist = Checklist.objects.get(pk=step1['checklist_id'])
        except:
            pass
    
    context = {
        'step1': step1,
        'step2': step2,
        'maitre_hotel': maitre_hotel,
        'checklist': checklist,
    }
    
    return render(request, 'ventes/contrats/contrat_create_step3.html', context)


@login_required
def contrat_detail(request, pk):
    """Détail d'un contrat"""
    contrat = get_object_or_404(
        Contrat.objects.select_related(
            'maitre_hotel', 'checklist', 'livraison', 'cree_par'
        ).prefetch_related('photos', 'historique'),
        pk=pk
    )
    
    photos = contrat.photos.all()
    historique = contrat.historique.all()[:10]
    
    context = {
        'contrat': contrat,
        'photos': photos,
        'historique': historique,
        'can_edit': request.user.role in ['resp_ventes', 'maitre_hotel'],
    }
    
    return render(request, 'ventes/contrats/contrat_detail.html', context)


@login_required
def contrat_edit(request, pk):
    """Modifier un contrat (formulaire tout-en-un)"""
    contrat = get_object_or_404(Contrat, pk=pk)
    
    # Vérifier permissions
    if request.user.role not in ['resp_ventes', 'maitre_hotel']:
        messages.error(request, "Vous n'avez pas la permission de modifier ce contrat")
        return redirect('ventes:contrat_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            # Mise à jour des champs
            contrat.nom_evenement = request.POST.get('nom_evenement')
            contrat.maitre_hotel_id = request.POST.get('maitre_hotel') or None
            contrat.client_nom = request.POST.get('client_nom')
            contrat.client_telephone = request.POST.get('client_telephone')
            contrat.client_email = request.POST.get('client_email', '')
            contrat.contact_sur_site = request.POST.get('contact_sur_site', '')
            contrat.adresse_complete = request.POST.get('adresse_complete')
            contrat.ville = request.POST.get('ville', 'Montréal')
            contrat.code_postal = request.POST.get('code_postal', '')
            contrat.date_evenement = request.POST.get('date_evenement')
            contrat.heure_debut_prevue = request.POST.get('heure_debut_prevue')
            contrat.heure_fin_prevue = request.POST.get('heure_fin_prevue')
            contrat.nb_convives = int(request.POST.get('nb_convives', 0))
            contrat.deroule_evenement = request.POST.get('deroule_evenement', '')
            contrat.informations_supplementaires = request.POST.get('informations_supplementaires', '')
            contrat.instructions_speciales = request.POST.get('instructions_speciales', '')
            
            contrat.save()
            
            # Historique
            HistoriqueContrat.objects.create(
                contrat=contrat,
                type_action='modification',
                description=f"Contrat modifié par {request.user.get_full_name()}",
                effectue_par=request.user
            )
            
            messages.success(request, "✅ Contrat modifié avec succès!")
            return redirect('ventes:contrat_detail', pk=pk)
        
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
    
    # GET
    maitres_hotel = User.objects.filter(role='maitre_hotel', is_active=True)
    
    context = {
        'contrat': contrat,
        'maitres_hotel': maitres_hotel,
    }
    
    return render(request, 'ventes/contrats/contrat_edit.html', context)


@login_required
def contrat_delete(request, pk):
    """Supprimer un contrat"""
    contrat = get_object_or_404(Contrat, pk=pk)
    
    # Vérifier permissions
    if request.user.role != 'resp_ventes':
        messages.error(request, "Seuls les responsables peuvent supprimer un contrat")
        return redirect('ventes:contrat_detail', pk=pk)
    
    if request.method == 'POST':
        numero = contrat.numero_contrat
        contrat.delete()
        messages.success(request, f"Contrat {numero} supprimé avec succès")
        return redirect('ventes:dashboard_vendeuse')
    
    context = {'contrat': contrat}
    return render(request, 'ventes/contrats/contrat_confirm_delete.html', context)


# Ajouter cette vue dans ventes/views.py

@login_required
def contrat_from_checklist(request, checklist_id):
    """Créer un contrat à partir d'une checklist existante"""
    
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    
    # Extraire le numéro (avec ou sans préfixe)
    numero_commande = checklist.numero_commande.strip()
    
    # Si le numéro commence déjà par CMD-, on le garde tel quel
    # Sinon, on l'ajoute
    if not numero_commande.startswith('CMD-'):
        numero_avec_prefix = f"CMD-{numero_commande}"
    else:
        numero_avec_prefix = numero_commande
    
    request.session['contrat_step1'] = {
        'numero_contrat': numero_avec_prefix,  # ✅ AVEC le préfixe CMD-
        'nom_evenement': checklist.nom,
        'maitre_hotel_id': None,
        'checklist_id': str(checklist.id),
        'livraison_id': str(checklist.livraison.id) if checklist.livraison else None,
    }
    
    # Pré-remplir l'étape 2 avec la date de l'événement
    request.session['contrat_step2'] = {
        'client_nom': '',
        'client_telephone': '',
        'client_email': '',
        'contact_sur_site': '',
        'adresse_complete': '',
        'ville': 'Montréal',
        'code_postal': '',
        'date_evenement': checklist.date_evenement.strftime('%Y-%m-%d'),
        'heure_debut_prevue': '',
        'heure_fin_prevue': '',
        'nb_convives': 0,
        'informations_supplementaires': checklist.notes if checklist.notes else '',
        'instructions_speciales': '',
    }
    
    messages.info(request, f"Création d'un contrat basé sur la checklist {checklist.numero_commande}")
    
    # Rediriger vers l'étape 2 (puisque l'étape 1 est déjà pré-remplie)
    return redirect('ventes:contrat_create_step2')

# ventes/views.py - Ajouter à la fin du fichier

from .models import Soumission

# ============ CRUD SOUMISSIONS ============

@login_required
def soumission_list(request):
    """Liste des soumissions (pour l'onglet dans dashboard_responsable)"""
    soumissions = Soumission.objects.select_related('cree_par').order_by('-date_evenement')
    
    # Filtres optionnels
    statut_filter = request.GET.get('statut')
    if statut_filter:
        soumissions = soumissions.filter(statut=statut_filter)
    
    context = {
        'soumissions': soumissions,
        'statut_choices': Soumission.STATUT_CHOICES,
    }
    
    return render(request, 'ventes/soumissions/soumission_list.html', context)



# ventes/views.py

from django.conf import settings

@login_required
def soumission_create(request):
    """Créer une nouvelle soumission"""
    if request.user.role not in ['resp_ventes', 'vendeur']:
        messages.error(request, "Vous n'avez pas la permission de créer une soumission")
        return redirect('ventes:dashboard_responsable')
    
    if request.method == 'POST':
        nom_compagnie = request.POST.get('nom_compagnie')
        date_evenement = request.POST.get('date_evenement')
        nombre_personnes = request.POST.get('nombre_personnes')
        adresse = request.POST.get('adresse')
        avec_service = request.POST.get('avec_service') == 'on'
        location_materiel = request.POST.get('location_materiel') == 'on'
        avec_alcool = request.POST.get('avec_alcool') == 'on'
        commande_par = request.POST.get('commande_par')
        email = request.POST.get('email')
        telephone = request.POST.get('telephone')
        notes = request.POST.get('notes', '')
        # notes_client supprimé
        
        # Validation
        if not all([nom_compagnie, date_evenement, nombre_personnes, 
                   adresse, commande_par, email, telephone]):
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            context = {
                'form_data': request.POST,
                'google_api_key': settings.GOOGLE_MAPS_API_KEY,  # ✅ AJOUTÉ
            }
            return render(request, 'ventes/soumissions/soumission_form.html', context)
        
        try:
            soumission = Soumission.objects.create(
                nom_compagnie=nom_compagnie,
                date_evenement=date_evenement,
                nombre_personnes=int(nombre_personnes),
                adresse=adresse,
                avec_service=avec_service,
                location_materiel=location_materiel,
                avec_alcool=avec_alcool,
                commande_par=commande_par,
                email=email,
                telephone=telephone,
                notes=notes,
                # notes_client supprimé
                cree_par=request.user,
                statut='en_cours'
            )
            
            messages.success(request, f"✅ Soumission {soumission.numero_soumission} créée avec succès!")
            return redirect('ventes:soumission_detail', pk=soumission.pk)
        
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
            import traceback
            traceback.print_exc()
    
    context = {
        'google_api_key': settings.GOOGLE_MAPS_API_KEY,  # ✅ AJOUTÉ
    }
    return render(request, 'ventes/soumissions/soumission_form.html', context)


@login_required
def soumission_edit(request, pk):
    """Modifier une soumission"""
    soumission = get_object_or_404(Soumission, pk=pk)
    
    # Vérifier permissions
    if request.user.role not in ['resp_ventes', 'vendeur']:
        messages.error(request, "Vous n'avez pas la permission de modifier cette soumission")
        return redirect('ventes:soumission_detail', pk=pk)
    
    if request.method == 'POST':
        nom_compagnie = request.POST.get('nom_compagnie')
        date_evenement = request.POST.get('date_evenement')
        nombre_personnes = request.POST.get('nombre_personnes')
        adresse = request.POST.get('adresse')
        avec_service = request.POST.get('avec_service') == 'on'
        location_materiel = request.POST.get('location_materiel') == 'on'
        avec_alcool = request.POST.get('avec_alcool') == 'on'
        commande_par = request.POST.get('commande_par')
        email = request.POST.get('email')
        telephone = request.POST.get('telephone')
        notes = request.POST.get('notes', '')
        # notes_client supprimé
        statut = request.POST.get('statut', soumission.statut)
        
        # Validation
        if not all([nom_compagnie, date_evenement, nombre_personnes, adresse, 
                   commande_par, email, telephone]):
            messages.error(request, "Veuillez remplir tous les champs obligatoires")
            context = {
                'soumission': soumission,
                'google_api_key': settings.GOOGLE_MAPS_API_KEY,  # ✅ AJOUTÉ
            }
            return render(request, 'ventes/soumissions/soumission_form.html', context)
        
        try:
            soumission.nom_compagnie = nom_compagnie
            soumission.date_evenement = date_evenement
            soumission.nombre_personnes = int(nombre_personnes)
            soumission.adresse = adresse
            soumission.avec_service = avec_service
            soumission.location_materiel = location_materiel
            soumission.avec_alcool = avec_alcool
            soumission.commande_par = commande_par
            soumission.email = email
            soumission.telephone = telephone
            soumission.notes = notes
            # notes_client supprimé
            soumission.statut = statut
            soumission.save()
            
            messages.success(request, "✅ Soumission modifiée avec succès!")
            return redirect('ventes:soumission_detail', pk=pk)
        
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
    
    context = {
        'soumission': soumission,
        'google_api_key': settings.GOOGLE_MAPS_API_KEY,  # ✅ AJOUTÉ
    }
    return render(request, 'ventes/soumissions/soumission_form.html', context)

@login_required
def soumission_detail(request, pk):
    """Détail d'une soumission"""
    soumission = get_object_or_404(
        Soumission.objects.select_related('cree_par'),
        pk=pk
    )
    
    context = {
        'soumission': soumission,
        'can_edit': request.user.role in ['resp_ventes', 'vendeur'],
    }
    
    return render(request, 'ventes/soumissions/soumission_detail.html', context)




@login_required
def soumission_delete(request, pk):
    """Supprimer une soumission"""
    soumission = get_object_or_404(Soumission, pk=pk)
    
    # Vérifier permissions
    if request.user.role != 'resp_ventes':
        messages.error(request, "Seuls les responsables peuvent supprimer une soumission")
        return redirect('ventes:soumission_detail', pk=pk)
    
    if request.method == 'POST':
        numero = soumission.numero_soumission
        soumission.delete()
        messages.success(request, f"Soumission {numero} supprimée avec succès")
        return redirect('ventes:dashboard_responsable')
    
    context = {'soumission': soumission}
    return render(request, 'ventes/soumissions/soumission_confirm_delete.html', context)


@login_required
def soumission_duplicate(request, pk):
    """Dupliquer une soumission"""
    original = get_object_or_404(Soumission, pk=pk)
    
    try:
        # ✅ Ne pas spécifier de numéro, il sera auto-généré
        nouvelle_soumission = Soumission.objects.create(
            # numero_soumission sera auto-généré
            nom_compagnie=original.nom_compagnie,
            date_evenement=original.date_evenement,
            nombre_personnes=original.nombre_personnes,
            adresse=original.adresse,
            avec_service=original.avec_service,
            location_materiel=original.location_materiel,
            avec_alcool=original.avec_alcool,
            commande_par=original.commande_par,
            email=original.email,
            telephone=original.telephone,
            notes=original.notes,
            notes_client=original.notes_client,
            cree_par=request.user,
            statut='en_cours'
        )
        
        messages.success(request, f"Soumission dupliquée avec succès! Nouveau numéro: {nouvelle_soumission.numero_soumission}")
        return redirect('ventes:soumission_detail', pk=nouvelle_soumission.pk)
    
    except Exception as e:
        messages.error(request, f"Erreur lors de la duplication: {str(e)}")
        return redirect('ventes:soumission_detail', pk=pk)

@login_required
def soumission_envoyer(request, pk):
    """Marquer une soumission comme envoyée"""
    soumission = get_object_or_404(Soumission, pk=pk)
    
    if request.method == 'POST':
        soumission.envoyer()
        messages.success(request, f"Soumission {soumission.numero_soumission} marquée comme envoyée!")
        return redirect('ventes:soumission_detail', pk=pk)
    
    return redirect('ventes:soumission_detail', pk=pk)

@login_required
def soumission_accepter(request, pk):
    """Marquer une soumission comme acceptée"""
    if request.method == 'POST':
        soumission = get_object_or_404(Soumission, pk=pk)
        
        # Vérifier permissions
        if request.user.role not in ['resp_ventes', 'vendeur']:
            messages.error(request, "Vous n'avez pas la permission de modifier cette soumission")
            return redirect('ventes:soumission_detail', pk=pk)
        
        soumission.accepter()
        messages.success(request, f"✅ Soumission {soumission.numero_soumission} marquée comme acceptée!")
        return redirect('ventes:soumission_detail', pk=pk)
    
    return redirect('ventes:soumission_detail', pk=pk)


@login_required
def soumission_refuser(request, pk):
    """Marquer une soumission comme refusée"""
    if request.method == 'POST':
        soumission = get_object_or_404(Soumission, pk=pk)
        
        # Vérifier permissions
        if request.user.role not in ['resp_ventes', 'vendeur']:
            messages.error(request, "Vous n'avez pas la permission de modifier cette soumission")
            return redirect('ventes:soumission_detail', pk=pk)
        
        soumission.refuser()
        messages.warning(request, f"❌ Soumission {soumission.numero_soumission} marquée comme refusée")
        return redirect('ventes:soumission_detail', pk=pk)
    
    return redirect('ventes:soumission_detail', pk=pk)