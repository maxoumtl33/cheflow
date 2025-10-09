import requests
from decimal import Decimal
import time
import re

class GeocodingService:
    """Service de géocodage ultra-précis pour Québec"""
    
    # Mapping code postal -> ville
    CODE_POSTAL_VILLE = {
        'H': 'Montréal',
        'J': 'Laval',  # ou Longueuil, Brossard, etc.
    }
    
    # Villes de la grande région de Montréal
    VILLES_CONNUES = [
        'Montréal', 'Montreal', 
        'Laval',
        'Longueuil',
        'Brossard',
        'Saint-Laurent',
        'Westmount',
        'Outremont',
        'Côte-Saint-Luc',
        'Dollard-des-Ormeaux',
        'Pointe-Claire',
        'Verdun',
        'LaSalle',
    ]
    
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {
            'User-Agent': 'RestaurantManager/1.0'
        }
        self.cache = {}
    
    def detecter_ville_depuis_code_postal(self, code_postal):
        """Détecte la ville probable depuis le code postal"""
        if not code_postal:
            return 'Montréal'  # Par défaut
        
        code_clean = code_postal.replace(' ', '').upper()
        
        if not code_clean:
            return 'Montréal'
        
        premiere_lettre = code_clean[0]
        
        # H = Montréal, J = Laval/Rive-Sud
        if premiere_lettre == 'H':
            return 'Montréal'
        elif premiere_lettre == 'J':
            # J commence souvent par Laval, mais peut être Longueuil/Brossard
            # On retourne Laval par défaut, sera précisé par le géocodage
            return 'Laval'
        
        return 'Montréal'  # Défaut
    
    def extraire_ville_de_adresse(self, adresse_complete):
        """Extrait la ville mentionnée dans l'adresse"""
        if not adresse_complete:
            return None
        
        adresse_lower = adresse_complete.lower()
        
        for ville in self.VILLES_CONNUES:
            if ville.lower() in adresse_lower:
                return ville
        
        return None
    
    def extraire_adresse_precise(self, adresse_complete):
        """
        Extrait l'adresse en gardant SEULEMENT numéro + rue
        Exemples:
        - "3940, Boulevard Saint-Elzéar Ouest, 17eme etage, Laval" 
          -> "3940, Boulevard Saint-Elzéar Ouest"
        - "6767, Chemin de la Côte-de-Liesse, Livrer à la réception, Montréal"
          -> "6767, Chemin de la Côte-de-Liesse"
        """
        if not adresse_complete:
            return '', None
        
        # D'abord détecter la ville si présente
        ville_detectee = self.extraire_ville_de_adresse(adresse_complete)
        
        # Séparer par virgules
        parties = [p.strip() for p in adresse_complete.split(',')]
        
        # Filtrer les parties à garder
        parties_adresse = []
        
        for i, partie in enumerate(parties):
            partie_lower = partie.lower()
            
            # Ignorer les villes
            if any(v.lower() == partie_lower for v in self.VILLES_CONNUES):
                continue
            
            # Ignorer les codes postaux
            if re.match(r'^[A-Z]\d[A-Z]\s?\d[A-Z]\d$', partie.upper()):
                continue
            
            # Ignorer les instructions de livraison
            mots_instructions = [
                'livrer', 'reception', 'réception', 'installer', 'etage', 
                'étage', 'bureau', 'suite', 'app', 'appartement', 'local'
            ]
            if any(mot in partie_lower for mot in mots_instructions):
                continue
            
            # Ignorer les parties vides
            if not partie.strip():
                continue
            
            parties_adresse.append(partie)
            
            # Garder maximum 2 parties (numéro + rue)
            if len(parties_adresse) >= 2:
                break
        
        # Construire l'adresse
        if len(parties_adresse) >= 2:
            adresse = f"{parties_adresse[0]}, {parties_adresse[1]}"
        elif len(parties_adresse) == 1:
            adresse = parties_adresse[0]
        else:
            adresse = parties[0] if parties else ''
        
        # Nettoyer
        adresse = adresse.replace('#', '').replace('  ', ' ').strip()
        
        return adresse, ville_detectee
    
    def formater_code_postal(self, code_postal):
        """Formate le code postal canadien"""
        if not code_postal:
            return ''
        
        code = str(code_postal).upper().strip()
        code = code.replace('CANADA', '').replace(' ', '')
        
        if len(code) == 6 and code[0].isalpha():
            return f"{code[:3]} {code[3:]}"
        
        return code
    
    def geocoder_adresse(self, adresse_complete, ville=None, code_postal=None):
        """
        Géocode avec stratégie intelligente
        Retourne latitude, longitude, place_id ET ville détectée
        """
        # Extraire adresse précise ET ville depuis l'adresse
        adresse_precise, ville_detectee = self.extraire_adresse_precise(adresse_complete)
        code_postal_clean = self.formater_code_postal(code_postal) if code_postal else None
        
        # Déterminer la ville à utiliser
        ville_finale = None
        
        # Priorité 1: Ville détectée dans l'adresse
        if ville_detectee:
            ville_finale = ville_detectee
        # Priorité 2: Ville depuis code postal
        elif code_postal_clean:
            ville_finale = self.detecter_ville_depuis_code_postal(code_postal_clean)
        # Priorité 3: Ville passée en paramètre (ignorée généralement)
        elif ville:
            ville_finale = ville
        # Défaut
        else:
            ville_finale = 'Montréal'
        
        print(f"🔍 Géocodage: {adresse_precise} | {code_postal_clean} | {ville_finale}")
        
        # Cache
        cache_key = f"{adresse_precise}|{code_postal_clean}|{ville_finale}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # STRATÉGIE 1: Adresse + Code postal + Ville (OPTIMAL)
        if code_postal_clean and adresse_precise:
            query = f"{adresse_precise}, {code_postal_clean}, {ville_finale}, Québec, Canada"
            result = self._geocoder_query(query)
            
            if result['success']:
                result['ville_utilisee'] = ville_finale
                self.cache[cache_key] = result
                return result
        
        # STRATÉGIE 2: Adresse + Ville
        if adresse_precise:
            query = f"{adresse_precise}, {ville_finale}, Québec, Canada"
            result = self._geocoder_query(query)
            
            if result['success']:
                result['approximatif'] = True
                result['ville_utilisee'] = ville_finale
                self.cache[cache_key] = result
                return result
        
        # STRATÉGIE 3: Code postal + Ville (dernier recours)
        if code_postal_clean:
            query = f"{code_postal_clean}, {ville_finale}, Québec, Canada"
            result = self._geocoder_query(query)
            
            if result['success']:
                result['approximatif'] = True
                result['base_code_postal'] = True
                result['ville_utilisee'] = ville_finale
                self.cache[cache_key] = result
                return result
        
        return {
            'success': False,
            'error': 'Géocodage impossible',
            'adresse_originale': adresse_complete,
            'ville_utilisee': ville_finale
        }
    
    def _geocoder_query(self, query):
        """Effectue la requête de géocodage"""
        try:
            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1,
                'countrycodes': 'ca'
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            time.sleep(1)  # Respecter rate limit Nominatim
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    result = data[0]
                    lat = float(result['lat'])
                    lon = float(result['lon'])
                    
                    # Vérifier zone Québec étendue (Montréal + Laval + Rive-Sud)
                    if 45.3 <= lat <= 45.8 and -74.0 <= lon <= -73.4:
                        return {
                            'success': True,
                            'latitude': Decimal(str(lat)),
                            'longitude': Decimal(str(lon)),
                            'place_id': str(result.get('place_id', '')),
                            'display_name': result.get('display_name', ''),
                            'query_used': query
                        }
            
            return {'success': False}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}