"""API REST de QuickTrack (secciones 6 y 7 del informe).

Reutiliza la lógica de negocio de scripts/quicktrack_crud.py y las consultas
de scripts/consultas_quicktrack.py, por eso agrega la carpeta scripts al
sys.path antes de que se importen los routers.
"""
import sys
from pathlib import Path

__version__ = "1.0.0"
PREFIJO = "/api/v1"

RAIZ = Path(__file__).resolve().parent.parent
_SCRIPTS = str(RAIZ / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
