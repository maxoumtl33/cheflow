import pandas as pd
from datetime import datetime, time
from django.utils import timezone
from decimal import Decimal
import re

from .models import Livraison, ModeEnvoi
from .geocoding import GeocodingService


class ExcelImportService:
    """Service pour importer/mettre à jour les livraisons depuis Excel"""
    
    def __init__(self):
        self.geocoding_service = GeocodingService()
        self.erreurs = []
        self.success_count = 0
        self.updated_count = 0
        self.skip_count = 0
        self.geocoding_failed = []
    
    def nettoyer_code_postal(self, code_postal):
        """Nettoie et formate le code postal"""
        if pd.isna(code_postal):
            return ''
        
        code = str(code_postal).upper().strip()
        code = code.replace('CANADA', '').replace(' ', '')
        
        if len(code) == 6 and code[0].isalpha():
            return f"{code[:3]} {code[3:]}"
        
        return code
    
    def parser_heure(self, heure_str):
        """Parse l'heure depuis différents formats"""
        if pd.isna(heure_str):
            return None
        
        heure_str = str(heure_str).strip()
        
        # Format HH:MM
        match = re.match(r'(\d{1,2}):(\d{2})', heure_str)
        if match:
            heure = int(match.group(1))
            minute = int(match.group(2))
            return time(heure, minute)
        
        # Format HHhMM (français: 07h00, 11h30)
        match = re.match(r'(\d{1,2})h(\d{2})', heure_str)
        if match:
            heure = int(match.group(1))
            minute = int(match.group(2))
            return time(heure, minute)
        
        # Format HHMM
        match = re.match(r'(\d{1,2})(\d{2})', heure_str)
        if match:
            heure = int(match.group(1))
            minute = int(match.group(2))
            return time(heure, minute)
        
        return None
    
    def determiner_periode(self, heure):
        """Détermine la période selon l'heure"""
        if not heure:
            return 'matin'
        
        if time(5, 0) <= heure < time(9, 30):
            return 'matin'
        elif time(9, 30) <= heure < time(13, 0):
            return 'midi'
        else:
            return 'apres_midi'
    
    def extraire_numero_base(self, numero):
        """Extrait le numéro de base (sans .1, .2, etc.)"""
        if pd.isna(numero):
            return ''
        
        numero_str = str(numero).strip()
        
        if '.' in numero_str:
            return numero_str.split('.')[0]
        
        return numero_str
    
    def extraire_adresse_base(self, adresse_complete):
        """
        Extrait uniquement le numéro et le nom de la rue
        Exemples:
        - "600, Maisonneuve Boulevard West, suite 1500" -> "600, Maisonneuve Boulevard West"
        - "5445, Avenue de Gaspé, bureau 1005" -> "5445, Avenue de Gaspé"
        - "123 Rue Saint-Denis, App 405" -> "123 Rue Saint-Denis"
        """
        if not adresse_complete:
            return ''
        
        # Nettoyer d'abord
        adresse = adresse_complete.strip()
        
        # Patterns à ignorer (suite, bureau, app, etc.)
        patterns_a_retirer = [
            r',\s*suite\s+\d+',
            r',\s*bureau\s+\d+',
            r',\s*app\.?\s*\d+',
            r',\s*apt\.?\s*\d+',
            r',\s*#\s*\d+',
            r',\s*unit[eé]\s+\d+',
        ]
        
        for pattern in patterns_a_retirer:
            adresse = re.sub(pattern, '', adresse, flags=re.IGNORECASE)
        
        # Séparer par virgules
        parties = [p.strip() for p in adresse.split(',')]
        
        # Filtrer les parties vides et les doublons
        parties_propres = []
        for partie in parties:
            if partie and partie.lower() not in ['montreal', 'montréal', 'quebec', 'québec']:
                # Ignorer si c'est un code postal (pattern: A1A 1A1 ou A1A1A1)
                if not re.match(r'^[A-Z]\d[A-Z]\s?\d[A-Z]\d$', partie.upper()):
                    if partie not in parties_propres:
                        parties_propres.append(partie)
        
        # Garder seulement les 2 premières parties (numéro + rue)
        if len(parties_propres) >= 2:
            return f"{parties_propres[0]}, {parties_propres[1]}"
        elif len(parties_propres) == 1:
            return parties_propres[0]
        
        return adresse.split(',')[0].strip() if ',' in adresse else adresse
    
    def get_safe_value(self, row, col_name):
        """Récupère une valeur en gérant les NaN"""
        val = row.get(col_name, '')
        if pd.isna(val) or str(val) == 'nan':
            return ''
        return str(val).strip()
    
    def adresse_a_change(self, livraison, nouvelle_adresse, nouveau_code_postal):
        """Vérifie si l'adresse ou le code postal ont changé"""
        return (
            livraison.adresse_complete != nouvelle_adresse or
            livraison.code_postal != nouveau_code_postal
        )
    
    def ajouter_geocoding_failed(self, numero, nom, adresse, raison):
        """Ajoute une livraison non géocodée à la liste"""
        self.geocoding_failed.append({
            'numero': numero,
            'nom': nom or 'Sans nom',
            'adresse': adresse or 'Adresse manquante',
            'raison': raison
        })
    
    def mettre_a_jour_livraison(self, livraison, row, date_livraison):
        """Met à jour une livraison existante avec les nouvelles données"""
        champs_modifies = []
        needs_geocoding = False
        
        # ========== NOM ÉVÉNEMENT ==========
        nom_evenement = self.get_safe_value(row, 'Nom de l\'événement')
        if nom_evenement and livraison.nom_evenement != nom_evenement:
            livraison.nom_evenement = nom_evenement
            champs_modifies.append('nom_evenement')
        
        # ========== CONTACT SUR SITE ==========
        contact_sur_site = self.get_safe_value(row, 'Livraison et personne à contacter sur le site')
        if contact_sur_site != livraison.contact_sur_site:
            livraison.contact_sur_site = contact_sur_site
            champs_modifies.append('contact_sur_site')
        
        # ========== ADRESSE ==========
        adresse_base = self.get_safe_value(row, 'Adresse')
        app = self.get_safe_value(row, 'APP')
        ligne2 = self.get_safe_value(row, 'Ligne 2')
        
        parts = []
        if adresse_base:
            parts.append(adresse_base)
        if app:
            parts.append(f"App {app}")
        if ligne2:
            parts.append(ligne2)
        
        adresse_complete = ', '.join(parts) if parts else ''
        code_postal_raw = self.get_safe_value(row, 'Code postal')
        code_postal = self.nettoyer_code_postal(code_postal_raw)
        
        # Vérifier si adresse a changé
        if self.adresse_a_change(livraison, adresse_complete, code_postal):
            livraison.adresse_complete = adresse_complete
            livraison.app = app
            livraison.ligne_adresse_2 = ligne2
            livraison.code_postal = code_postal
            champs_modifies.extend(['adresse_complete', 'app', 'ligne_adresse_2', 'code_postal'])
            needs_geocoding = True
        
        # ========== HEURE ==========
        heure_str = row.get('Heure livraison', '')
        heure_souhaitee = self.parser_heure(heure_str)
        if heure_souhaitee != livraison.heure_souhaitee:
            livraison.heure_souhaitee = heure_souhaitee
            periode = self.determiner_periode(heure_souhaitee)
            livraison.periode = periode
            champs_modifies.extend(['heure_souhaitee', 'periode'])
        
        # ========== MODE ENVOI ==========
        mode_envoi_nom = self.get_safe_value(row, 'Mode d\'envoi')
        if mode_envoi_nom:
            mode_envoi, _ = ModeEnvoi.objects.get_or_create(nom=mode_envoi_nom)
            if livraison.mode_envoi != mode_envoi:
                livraison.mode_envoi = mode_envoi
                champs_modifies.append('mode_envoi')
        
        # ========== NB CONVIVES ==========
        nb_convives = row.get('Nb convives', 0)
        try:
            nb_convives = int(nb_convives) if not pd.isna(nb_convives) else 0
        except:
            nb_convives = 0
        
        if nb_convives != livraison.nb_convives:
            livraison.nb_convives = nb_convives
            champs_modifies.append('nb_convives')
        
        # ========== CONSEILLER ==========
        nom_conseiller = self.get_safe_value(row, 'Nom du conseiller')
        if nom_conseiller != livraison.nom_conseiller:
            livraison.nom_conseiller = nom_conseiller
            champs_modifies.append('nom_conseiller')
        
        # ========== INFOS SUPPLÉMENTAIRES ==========
        informations_supplementaires = self.get_safe_value(row, 'Informations supplémentaires')
        if informations_supplementaires != livraison.informations_supplementaires:
            livraison.informations_supplementaires = informations_supplementaires
            champs_modifies.append('informations_supplementaires')
        
        # ========== GÉOCODAGE SI NÉCESSAIRE ==========
        if needs_geocoding:
            if not adresse_complete:
                self.ajouter_geocoding_failed(
                    livraison.numero_livraison,
                    livraison.nom_evenement,
                    'Aucune adresse',
                    'Adresse manquante dans le fichier Excel'
                )
            elif not code_postal:
                self.ajouter_geocoding_failed(
                    livraison.numero_livraison,
                    livraison.nom_evenement,
                    adresse_complete,
                    'Code postal manquant'
                )
            else:
                geo_result = self.geocoding_service.geocoder_adresse(
                    adresse_complete,
                    'Montréal',
                    code_postal
                )
                
                if geo_result['success']:
                    livraison.latitude = geo_result['latitude']
                    livraison.longitude = geo_result['longitude']
                    livraison.place_id = str(geo_result.get('place_id', ''))
                    champs_modifies.extend(['latitude', 'longitude', 'place_id'])
                    
                    note_geo = f"\n🔄 Géocodage mis à jour le {timezone.now().strftime('%d/%m/%Y à %H:%M')}"
                    if geo_result.get('approximatif'):
                        note_geo += " (approximatif)"
                    livraison.notes_internes = (livraison.notes_internes or '') + note_geo
                    champs_modifies.append('notes_internes')
                else:
                    raison_echec = geo_result.get('error', 'Erreur API Google Maps')
                    self.ajouter_geocoding_failed(
                        livraison.numero_livraison,
                        livraison.nom_evenement,
                        f"{adresse_complete}, {code_postal}",
                        raison_echec
                    )
                    livraison.notes_internes = (livraison.notes_internes or '') + f"\n❌ Échec géocodage le {timezone.now().strftime('%d/%m/%Y à %H:%M')}: {raison_echec}"
                    champs_modifies.append('notes_internes')
        
        # ========== BESOINS AUTOMATIQUES ==========
        nom_lower = livraison.nom_evenement.lower() if livraison.nom_evenement else ''
        besoin_cafe = 'café' in nom_lower or 'cafe' in nom_lower
        besoin_the = 'thé' in nom_lower or 'the' in nom_lower
        besoin_part_chaud = 'part chaud' in nom_lower or 'chaud' in nom_lower
        besoin_sac_glace = 'glace' in nom_lower or 'glacé' in nom_lower
        
        if besoin_cafe != livraison.besoin_cafe:
            livraison.besoin_cafe = besoin_cafe
            champs_modifies.append('besoin_cafe')
        if besoin_the != livraison.besoin_the:
            livraison.besoin_the = besoin_the
            champs_modifies.append('besoin_the')
        if besoin_part_chaud != livraison.besoin_part_chaud:
            livraison.besoin_part_chaud = besoin_part_chaud
            champs_modifies.append('besoin_part_chaud')
        if besoin_sac_glace != livraison.besoin_sac_glace:
            livraison.besoin_sac_glace = besoin_sac_glace
            champs_modifies.append('besoin_sac_glace')
        
        # Sauvegarder si des champs ont changé
        if champs_modifies:
            livraison.save()
        
        return champs_modifies
    
    def importer(self, fichier_excel, date_livraison=None):
        """Importe ou met à jour les livraisons depuis un fichier Excel"""
        self.erreurs = []
        self.success_count = 0
        self.updated_count = 0
        self.skip_count = 0
        self.geocoding_failed = []
        
        if date_livraison is None:
            date_livraison = timezone.now().date()
        
        try:
            df = pd.read_excel(fichier_excel, skiprows=3)
            
            print("=" * 80)
            print("IMPORT DE LIVRAISONS")
            print("=" * 80)
            print(f"Date de livraison: {date_livraison}")
            print(f"Nombre de lignes: {len(df)}")
            print()
            
            for index, row in df.iterrows():
                try:
                    # ========== NUMÉRO COMMANDE ==========
                    numero_brut = self.get_safe_value(row, '# Commande')
                    numero_base = self.extraire_numero_base(numero_brut)
                    
                    if not numero_base:
                        continue
                    
                    # ========== VÉRIFIER SI LIVRAISON EXISTE ==========
                    livraison_existante = Livraison.objects.filter(
                        numero_livraison=numero_base,
                        date_livraison=date_livraison,
                        est_recuperation=False
                    ).first()
                    
                    if livraison_existante:
                        # ========== MISE À JOUR ==========
                        champs_modifies = self.mettre_a_jour_livraison(
                            livraison_existante,
                            row,
                            date_livraison
                        )
                        
                        # Vérifier liaison avec checklist
                        if not livraison_existante.checklist:
                            livraison_existante.lier_checklist_automatiquement()
                        
                        if champs_modifies:
                            self.updated_count += 1
                            print(f"🔄 #{numero_base} mis à jour: {', '.join(champs_modifies[:3])}...")
                        else:
                            self.skip_count += 1
                            print(f"⏭️  #{numero_base} - aucun changement")
                        
                        continue
                    
                    # ========== CRÉATION NOUVELLE LIVRAISON ==========
                    nom_evenement = self.get_safe_value(row, 'Nom de l\'événement')
                    
                    # Client
                    client_nom = self.get_safe_value(row, 'Nom du client commandé')
                    if not client_nom:
                        client_nom = 'Client Inconnu'
                    
                    contact_sur_site = self.get_safe_value(row, 'Livraison et personne à contacter sur le site')
                    
                    # Adresse
                    adresse_base = self.get_safe_value(row, 'Adresse')
                    app = self.get_safe_value(row, 'APP')
                    ligne2 = self.get_safe_value(row, 'Ligne 2')
                    
                    parts = []
                    if adresse_base:
                        parts.append(adresse_base)
                    if app:
                        parts.append(f"App {app}")
                    if ligne2:
                        parts.append(ligne2)
                    
                    adresse_complete = ', '.join(parts) if parts else ''
                    
                    code_postal_raw = self.get_safe_value(row, 'Code postal')
                    code_postal = self.nettoyer_code_postal(code_postal_raw)
                    
                    # Heure
                    heure_str = row.get('Heure livraison', '')
                    heure_souhaitee = self.parser_heure(heure_str)
                    periode = self.determiner_periode(heure_souhaitee)
                    
                    # Nb convives
                    nb_convives = row.get('Nb convives', 0)
                    try:
                        nb_convives = int(nb_convives) if not pd.isna(nb_convives) else 0
                    except:
                        nb_convives = 0
                    
                    # Mode envoi
                    mode_envoi_nom = self.get_safe_value(row, 'Mode d\'envoi')
                    mode_envoi = None
                    if mode_envoi_nom:
                        mode_envoi, _ = ModeEnvoi.objects.get_or_create(nom=mode_envoi_nom)
                    
                    nom_conseiller = self.get_safe_value(row, 'Nom du conseiller')
                    informations_supplementaires = self.get_safe_value(row, 'Informations supplémentaires')
                    
                    # Notes internes
                    notes_internes = f"Importé le {timezone.now().strftime('%d/%m/%Y à %H:%M')}"
                    if numero_brut != numero_base:
                        notes_internes += f"\nNuméro original: {numero_brut}"
                    if contact_sur_site:
                        notes_internes += f"\nContact sur site: {contact_sur_site}"
                    if nom_conseiller:
                        notes_internes += f"\nConseiller: {nom_conseiller}"
                    
                    # Géocodage
                    latitude = None
                    longitude = None
                    place_id = ''
                    
                    if not adresse_complete:
                        self.ajouter_geocoding_failed(
                            numero_base,
                            nom_evenement,
                            'Aucune adresse',
                            'Adresse manquante dans le fichier Excel'
                        )
                        notes_internes += "\n❌ Géocodage impossible: adresse manquante"
                    elif not code_postal:
                        self.ajouter_geocoding_failed(
                            numero_base,
                            nom_evenement,
                            adresse_complete,
                            'Code postal manquant'
                        )
                        notes_internes += "\n❌ Géocodage impossible: code postal manquant"
                    else:
                        geo_result = self.geocoding_service.geocoder_adresse(
                            adresse_complete,
                            'Montréal',
                            code_postal
                        )
                        
                        if geo_result['success']:
                            latitude = geo_result['latitude']
                            longitude = geo_result['longitude']
                            place_id = str(geo_result.get('place_id', ''))
                            
                            if geo_result.get('approximatif'):
                                notes_internes += "\n⚠️ Géocodage approximatif"
                        else:
                            raison_echec = geo_result.get('error', 'Erreur API Google Maps')
                            self.ajouter_geocoding_failed(
                                numero_base,
                                nom_evenement,
                                f"{adresse_complete}, {code_postal}",
                                raison_echec
                            )
                            notes_internes += f"\n❌ Géocodage échoué: {raison_echec}"
                    
                    # Besoins automatiques
                    nom_lower = nom_evenement.lower() if nom_evenement else ''
                    besoin_cafe = 'café' in nom_lower or 'cafe' in nom_lower
                    besoin_the = 'thé' in nom_lower or 'the' in nom_lower
                    besoin_part_chaud = 'part chaud' in nom_lower or 'chaud' in nom_lower
                    besoin_sac_glace = 'glace' in nom_lower or 'glacé' in nom_lower
                    
                    # Création
                    nouvelle_livraison = Livraison.objects.create(
                        numero_livraison=numero_base,
                        nom_evenement=nom_evenement,
                        client_nom=client_nom,
                        contact_sur_site=contact_sur_site,
                        adresse_complete=adresse_complete,
                        app=app,
                        ligne_adresse_2=ligne2,
                        code_postal=code_postal,
                        latitude=latitude,
                        longitude=longitude,
                        place_id=place_id,
                        date_livraison=date_livraison,
                        heure_souhaitee=heure_souhaitee,
                        periode=periode,
                        mode_envoi=mode_envoi,
                        nb_convives=nb_convives,
                        nom_conseiller=nom_conseiller,
                        informations_supplementaires=informations_supplementaires,
                        besoin_cafe=besoin_cafe,
                        besoin_the=besoin_the,
                        besoin_part_chaud=besoin_part_chaud,
                        besoin_sac_glace=besoin_sac_glace,
                        notes_internes=notes_internes,
                        status='non_assignee'
                    )
                    
                    # Lier automatiquement une checklist si elle existe
                    nouvelle_livraison.lier_checklist_automatiquement()
                    
                    self.success_count += 1
                    coord_info = f"({latitude}, {longitude})" if latitude else "(non géocodé)"
                    checklist_info = " 🔗" if nouvelle_livraison.checklist else ""
                    print(f"✅ #{numero_base}: {nom_evenement[:35] if nom_evenement else 'OK'} {coord_info}{checklist_info}")
                    
                except Exception as e:
                    error_msg = f"Ligne {index + 5}: {str(e)}"
                    print(f"❌ {error_msg}")
                    self.erreurs.append(error_msg)
            
            print()
            print("=" * 80)
            print(f"RÉSULTAT: {self.success_count} créées | {self.updated_count} mises à jour | {self.skip_count} inchangées | {len(self.erreurs)} erreurs")
            if self.geocoding_failed:
                print(f"⚠️  {len(self.geocoding_failed)} livraison(s) non géocodée(s)")
            print("=" * 80)
            
            return {
                'success': True,
                'imported': self.success_count,
                'updated': self.updated_count,
                'skipped': self.skip_count,
                'errors': self.erreurs,
                'geocoding_failed': self.geocoding_failed
            }
            
        except Exception as e:
            print(f"ERREUR GLOBALE: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'imported': self.success_count,
                'updated': self.updated_count,
                'skipped': self.skip_count,
                'errors': self.erreurs,
                'geocoding_failed': self.geocoding_failed
            }