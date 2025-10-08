from django.apps import AppConfig

class ChecklistConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'checklist'
    
    def ready(self):
        import checklist.signals  # Importer les signaux