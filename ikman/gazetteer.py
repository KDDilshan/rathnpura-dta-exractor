"""Sri Lankan town -> district lookup, used to audit a listing's stated location.

ikman's location facet is what the *seller* picked, and sellers who advertise
across the country routinely leave it on one district while the advert itself is
for a town elsewhere. Resolving the town named in the title against this table
is what catches that.

Only towns we are confident about are listed. Anything absent resolves to
``None`` and is reported as unverified rather than guessed - a wrong district is
worse than an admitted gap.
"""
from __future__ import annotations

import re

RATNAPURA = "Ratnapura"

# town (lowercase) -> district
GAZETTEER: dict[str, str] = {}


def _add(district: str, *towns: str) -> None:
    for town in towns:
        GAZETTEER[town.lower()] = district


_add(RATNAPURA,
     "ratnapura", "rathnapura", "eheliyagoda", "ahaliyagoda", "ehaliyagoda",
     "kuruwita", "pussella", "pelmadulla", "balangoda", "embilipitiya",
     "abilipitiya", "abililipitya", "rakwana", "kahawatta", "opanayaka",
     "kiriella", "nivithigala", "kalawana", "godakawela", "weligepola",
     "ayagama", "elapatha", "imbulpe", "kolonna", "belihuloya", "halpe",
     "pambahinna", "pambahinnda", "hidellana", "udawalawe", "udawalawa",
     "uda kandha", "gillimale", "karawita", "kalthota", "panadugama")

_add("Kurunegala",
     "dambadeniya", "giriulla", "wariyapola", "padeniya", "melsiripura",
     "polgahawela", "kurunegala", "narammala", "alawwa", "nikaweratiya")

_add("Gampaha",
     "nittambuwa", "attanagalla", "aththanagalla", "athanagalla", "kirindiwela",
     "kiridiwela", "wathupitiwala", "mirigama", "kiribathgoda", "bopitiya",
     "pasyala", "gampaha", "negombo", "ja-ela", "veyangoda", "divulapitiya")

_add("Colombo",
     "colombo", "mount lavinia", "meegoda", "hokandara", "thalawathugoda",
     "madiwala", "piliyandala", "nawagamuwa", "maharagama", "kottawa",
     "homagama", "dehiwala", "nugegoda", "pliyandala", "dampe")

_add("Kalutara", "kalutara", "wadduwa", "panadura", "horana", "beruwala", "hirana")
_add("Hambantota", "hambantota", "walasmulla", "walasmulla", "tangalle",
     "tissamaharama", "thanamalwila")
_add("Kegalle", "kegalle", "kitulgala", "mawanella", "rambukkana", "warakapola")
_add("Badulla", "badulla", "bandarawela", "welimada", "haputale", "ella",
     "kirimetitenna")
_add("Galle", "galle", "hikkaduwa", "ambalangoda", "elpitiya")
_add("Matara", "matara", "weligama", "akuressa", "deniyaya")
_add("Kandy", "kandy", "peradeniya", "gampola", "katugastota", "digana")

# Sinhala place names that appear in advert titles.
_add(RATNAPURA,
     "රත්නපුර", "ඇහැලියගොඩ", "ඇහැළියගොඩ", "පැල්මඩුල්ල", "බලන්ගොඩ",
     "ඇඹිලිපිටිය", "ඇබිලිපිටිය", "කිරිඇල්ල", "උඩවලව", "හිදැල්ලන")
_add("Kurunegala", "දඹදෙණිය")
_add("Gampaha", "නිට්ටඹුව", "වතුපිටිවල")
_add("Hambantota", "වලස්මුල්ල", "වළස්මුල්ල")

# Sellers spell the same town several ways, and Sinhala titles give it in
# Sinhala. Without canonical names one town splits into several groups and any
# per-town aggregate is wrong, so every variant maps to one English form.
CANONICAL: dict[str, str] = {
    "rathnapura": "Ratnapura", "රත්නපුර": "Ratnapura",
    "ahaliyagoda": "Eheliyagoda", "ehaliyagoda": "Eheliyagoda",
    "ඇහැලියගොඩ": "Eheliyagoda", "ඇහැළියගොඩ": "Eheliyagoda",
    "abilipitiya": "Embilipitiya", "abililipitya": "Embilipitiya",
    "ඇඹිලිපිටිය": "Embilipitiya", "ඇබිලිපිටිය": "Embilipitiya",
    "පැල්මඩුල්ල": "Pelmadulla", "බලන්ගොඩ": "Balangoda",
    "කිරිඇල්ල": "Kiriella", "හිදැල්ලන": "Hidellana",
    "udawalawa": "Udawalawe", "උඩවලව": "Udawalawe",
    "pambahinnda": "Pambahinna",
    "kiridiwela": "Kirindiwela",
    "aththanagalla": "Attanagalla", "athanagalla": "Attanagalla",
    "දඹදෙණිය": "Dambadeniya", "නිට්ටඹුව": "Nittambuwa",
    "වතුපිටිවල": "Wathupitiwala",
    "වලස්මුල්ල": "Walasmulla", "වළස්මුල්ල": "Walasmulla",
    "pliyandala": "Piliyandala",
}


def canonical_town(town: str | None) -> str | None:
    """One spelling per town, so per-town aggregates group correctly."""
    if not town:
        return None
    key = town.strip().lower()
    if key in CANONICAL:
        return CANONICAL[key]
    return CANONICAL.get(town.strip(), town.strip().title() if town.isascii()
                          else town.strip())


# Longest first so "uda kandha" wins over "kandy"-style partial collisions.
_SORTED_TOWNS = sorted(GAZETTEER, key=len, reverse=True)


def district_of(town: str | None) -> str | None:
    """District for an exact town name, or None when we do not know it."""
    if not town:
        return None
    key = re.sub(r"\s+", " ", town.strip().lower())
    key = re.sub(r"\b(town|city|new town|district)\b", "", key).strip(" ,-")
    return GAZETTEER.get(key)


def find_town(text: str | None) -> tuple[str | None, str | None]:
    """Scan free text for the first known town. -> (town, district).

    Matching is on word boundaries for Latin script; Sinhala has no spaces
    between a place name and its case suffix, so those match as substrings.
    """
    if not text:
        return None, None
    low = text.lower()
    for town in _SORTED_TOWNS:
        if town.isascii():
            if re.search(rf"\b{re.escape(town)}\b", low):
                return canonical_town(town), GAZETTEER[town]
        elif town in text:
            return canonical_town(town), GAZETTEER[town]
    return None, None
