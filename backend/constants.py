"""Shared constants used by both the SQLite and Postgres db backends."""
import re

KEYS = ("zg", "zb", "ng", "nb")
META_KEYS = ("theme", "message_zn", "message_nz", "jours_sans_course")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_PERSONS = ("z", "n")
# "free": whole day; "evening": activity in the evening but the night together
# is possible; "busy": legacy value from the old 3-state tap, kept readable.
VALID_STATUSES = ("free", "evening", "busy")
NOTE_MAX_LEN = 200

# ── liste de courses ──
SHOP_MAX_LEN = 60          # longueur d'un article
SHOP_MAX_ADD = 20          # articles ajoutés d'un coup (saisie séparée par des virgules)
SHOP_KEEP_HOURS = 24       # un article coché reste visible 24 h, puis disparaît
SHOP_SUGGESTIONS = 14      # nombre d'articles proposés en raccourci


def clean_shopping_texts(texts):
    """Normalise une saisie de courses en [(label, texte affiché)].

    `label` est la forme minuscule qui sert de clé : c'est elle qui repère un
    doublon dans la liste et qui regroupe l'historique des raccourcis, pour que
    « Lait » et « lait » ne fassent qu'un."""
    if isinstance(texts, str):
        texts = [texts]
    out, seen = [], set()
    for raw in texts or []:
        if not isinstance(raw, str):
            continue
        text = " ".join(raw.split())[:SHOP_MAX_LEN]
        label = text.lower()
        if not text or label in seen:
            continue
        seen.add(label)
        out.append((label, text))
        if len(out) >= SHOP_MAX_ADD:
            break
    return out
