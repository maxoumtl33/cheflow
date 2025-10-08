# maitre_hotel/forms.py
from django import forms
from .models import Contrat, PhotoContrat


class ContratForm(forms.ModelForm):
    """Formulaire pour créer/modifier un contrat"""
    
    class Meta:
        model = Contrat
        fields = [
            'numero_contrat',
            'nom_evenement',
            'client_nom',
            'client_telephone',
            'client_email',
            'contact_sur_site',
            'adresse_complete',
            'ville',
            'code_postal',
            'date_evenement',
            'heure_debut_prevue',
            'heure_fin_prevue',
            'nb_convives',
            'deroule_evenement',
            'informations_supplementaires',
            'livraison',
            'checklist',
        ]
        widgets = {
            'numero_contrat': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: CTR-2025-001'
            }),
            'nom_evenement': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nom de l\'événement'
            }),
            'client_nom': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nom du client'
            }),
            'client_telephone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '+1 (XXX) XXX-XXXX'
            }),
            'client_email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'email@exemple.com'
            }),
            'contact_sur_site': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Personne à contacter sur place'
            }),
            'adresse_complete': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Adresse complète de l\'événement'
            }),
            'ville': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Montréal'
            }),
            'code_postal': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'H2X 1Y9'
            }),
            'date_evenement': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'heure_debut_prevue': forms.TimeInput(attrs={
                'class': 'form-input',
                'type': 'time'
            }),
            'heure_fin_prevue': forms.TimeInput(attrs={
                'class': 'form-input',
                'type': 'time'
            }),
            'nb_convives': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nombre de convives',
                'min': 0
            }),
            'deroule_evenement': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 8,
                'placeholder': 'Détaillez le déroulement prévu de l\'événement...'
            }),
            'informations_supplementaires': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Informations complémentaires, instructions spéciales...'
            }),
            'livraison': forms.Select(attrs={
                'class': 'form-select'
            }),
            'checklist': forms.Select(attrs={
                'class': 'form-select'
            }),
        }


class PhotoContratForm(forms.ModelForm):
    """Formulaire pour ajouter une photo"""
    
    class Meta:
        model = PhotoContrat
        fields = ['image', 'legende']
        widgets = {
            'image': forms.FileInput(attrs={
                'accept': 'image/jpeg,image/jpg,image/png'
            }),
            'legende': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Description de la photo (optionnel)'
            })
        }