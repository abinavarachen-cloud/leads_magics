from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'  # or 'campaigns' depending on your app name
    
    def ready(self):
        # Import signals if you have any
        try:
            import api.signals
        except ImportError:
            pass