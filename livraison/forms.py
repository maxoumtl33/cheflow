from django import forms
from django.utils import timezone


class ExcelUploadForm(forms.Form):
    """Formulaire pour uploader un fichier Excel"""
    fichier = forms.FileField(
        label='Fichier Excel',
        help_text='Formats acceptés: .xlsx, .xls',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'
        })
    )
    
    date_livraison = forms.DateField(
        label='Date de livraison',
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    def clean_fichier(self):
        fichier = self.cleaned_data['fichier']
        
        # Vérifier l'extension
        if not fichier.name.endswith(('.xlsx', '.xls')):
            raise forms.ValidationError('Le fichier doit être au format Excel (.xlsx ou .xls)')
        
        # Vérifier la taille (max 10 MB)
        if fichier.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Le fichier ne doit pas dépasser 10 MB')
        
        return fichier