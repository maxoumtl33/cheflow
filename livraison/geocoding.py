import requests
from decimal import Decimal
import time
import re

class GeocodingService:
    """Service de géocodage ultra-précis pour Montréal"""
    
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {
            'User-Agent': 'RestaurantManager/1.0'
        }
        self.cache = {}
    
    def extraire_adresse_precise(self, adresse_complete):
        """
        Extrait l'adresse en gardant tout AVANT la 2ème virgule
        Exemple: "5445, Avenue de Gaspé, bureau 1005, Montréal" 
        -> "5445, Avenue de Gaspé"
        """
        if not adresse_complete:
            return ''
        
        # Compter les virgules et prendre jusqu'à la 2ème
        parties = adresse_complete.split(',')
        
        if len(parties) >= 2:
            # Garder les 2 premières parties (numéro + rue)
            adresse = ','.join(parties[:2]).strip()
        else:
            # Si une seule virgule ou aucune, prendre tout
            adresse = adresse_complete.strip()
        
        # Nettoyer
        adresse = adresse.replace('#', '').replace('  ', ' ')
        
        return adresse
    
    def formater_code_postal(self, code_postal):
        """Formate le code postal canadien"""
        if not code_postal:
            return ''
        
        code = str(code_postal).upper().strip()
        code = code.replace('CANADA', '').replace(' ', '')
        
        if len(code) == 6 and code[0].isalpha():
            return f"{code[:3]} {code[3:]}"
        
        return code
    
    def geocoder_adresse(self, adresse_complete, ville="Montréal", code_postal=None):
        """
        Géocode avec stratégie: adresse avant 2ème virgule + code postal
        Retourne latitude, longitude ET place_id
        """
        # Extraire adresse précise
        adresse_precise = self.extraire_adresse_precise(adresse_complete)
        code_postal_clean = self.formater_code_postal(code_postal) if code_postal else None
        
        # Cache
        cache_key = f"{adresse_precise}|{code_postal_clean}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # STRATÉGIE 1: Adresse précise + Code postal (MEILLEURE)
        if code_postal_clean and adresse_precise:
            query = f"{adresse_precise}, {code_postal_clean}, Montréal, Québec, Canada"
            result = self._geocoder_query(query)
            
            if result['success']:
                self.cache[cache_key] = result
                return result
        
        # STRATÉGIE 2: Adresse précise seulement
        if adresse_precise:
            query = f"{adresse_precise}, Montréal, Québec, Canada"
            result = self._geocoder_query(query)
            
            if result['success']:
                result['approximatif'] = True
                self.cache[cache_key] = result
                return result
        
        # STRATÉGIE 3: Code postal seul (dernier recours)
        if code_postal_clean:
            query = f"{code_postal_clean}, Montréal, Québec, Canada"
            result = self._geocoder_query(query)
            
            if result['success']:
                result['approximatif'] = True
                result['base_code_postal'] = True
                self.cache[cache_key] = result
                return result
        
        return {
            'success': False,
            'error': 'Géocodage impossible',
            'adresse_originale': adresse_complete
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
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    result = data[0]
                    lat = float(result['lat'])
                    lon = float(result['lon'])
                    
                    # Vérifier zone Montréal étendue
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