import importlib, pkgutil

# Φόρτωσε ΟΛΑ τα submodules (models.*) για να γραφτούν οι κλάσεις στο registry
for m in pkgutil.iter_modules(__path__, __name__ + "."):
    importlib.import_module(m.name)

# Προαιρετικό export αν κάπου γίνεται "from models import User"
try:
    from .user import User  # noqa: F401
except Exception:
    pass
