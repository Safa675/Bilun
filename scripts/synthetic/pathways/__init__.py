"""Care pathways for the synthetic demo (v3, P2): schema, loader, expander and validity checks.

A pathway (data/synthetic/pathways/<id>.yaml) is the reviewed description of what one diagnosis in
one care setting produces on a bill. `load_pathway` reads it, `expand.expand` turns it plus its pins into a
clean bill, `checks.run_all` compares it with the catalogs. Import `checks` explicitly: it loads
Polars and the catalogs, the other modules do not.
"""

from .loader import PathwayLoadError, load_all, load_pathway, load_text
from .schema import Pathway, Pins, Problem

# `expand` is not re-exported: it would shadow the module of the same name. Import it with
# `from scripts.synthetic.pathways.expand import expand`.
__all__ = [
    "Pathway",
    "PathwayLoadError",
    "Pins",
    "Problem",
    "load_all",
    "load_pathway",
    "load_text",
]
