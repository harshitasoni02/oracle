from django.apps import AppConfig


class OracleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'oracle'

    def ready(self):
        from django.db.backends.signals import connection_created

        def enable_wal(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA busy_timeout=30000;')

        connection_created.connect(enable_wal)
