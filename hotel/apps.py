from django.apps import AppConfig


class HotelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hotel'
    verbose_name = 'Gestion Hôtel'
    
    def ready(self):
        """Importe les signals quand Django démarre"""
        import hotel.signals

