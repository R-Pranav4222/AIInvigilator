import os
import threading
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AppMainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        """Called when Django starts. Pre-warm ML models in background thread
        so the first camera connection is near-instant instead of 15-20s delay."""
        # Only pre-warm when running the actual server, not during migrate/collectstatic
        import sys
        if 'runserver' not in sys.argv and 'daphne' not in ' '.join(sys.argv):
            return

        # Start pre-warming in a background thread so server boot isn't blocked
        thread = threading.Thread(target=self._prewarm_ml, daemon=True)
        thread.start()
        logger.info("ML model pre-warming started in background thread...")

    @staticmethod
    def _prewarm_ml():
        """Load and warm YOLO models so first camera use is instant."""
        try:
            from django.conf import settings
            ml_path = os.path.join(settings.BASE_DIR, 'ML')

            import sys
            if ml_path not in sys.path:
                sys.path.insert(0, ml_path)

            from frame_processor import prewarm_models
            prewarm_models()
            logger.info("ML models pre-warmed successfully at server startup")
        except Exception as e:
            logger.warning(f"ML pre-warm at startup failed (will retry on first use): {e}")
