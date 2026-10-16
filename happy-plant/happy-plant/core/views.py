from django.db import connection
from django.http import JsonResponse


def health(request):
    """Proves the chain works: Railway -> Django -> database. Reports the truth, never a guess."""
    engine = connection.vendor  # "postgresql" on Railway + Neon, "sqlite" on a laptop
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
        return JsonResponse({"ok": True, "database": "connected", "engine": engine})
    except Exception as e:
        return JsonResponse({"ok": False, "database": "error", "engine": engine, "error": str(e)[:200]}, status=503)
