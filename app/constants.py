"""Application constants and verified organization mappings.

Defines the verified institutions Fact Box Consult has worked with,
enabling automatic logo matching and portfolio filtering by organization.
"""
from typing import Dict, Any, Optional

ORGANIZATIONS: Dict[str, Dict[str, Any]] = {
    "mercy-corps": {
        "slug": "mercy-corps",
        "name": "Mercy Corps",
        "short_name": "Mercy Corps",
        "logo_static": "img/partners/mercy-corps.png",
        "keywords": ["mercy corps", "mercy"],
        "description": "Global humanitarian agency providing community relief, resilience strengthening, and livelihood support.",
    },
    "international-alert": {
        "slug": "international-alert",
        "name": "International Alert",
        "short_name": "International Alert",
        "logo_static": "img/partners/international-alert.jpg",
        "keywords": ["international alert", "alert"],
        "description": "Independent peacebuilding organisation working with communities affected by conflict across the globe.",
    },
    "malaria-consortium": {
        "slug": "malaria-consortium",
        "name": "Malaria Consortium",
        "short_name": "Malaria Consortium",
        "logo_static": "img/partners/malaria-consortium.png",
        "keywords": ["malaria consortium", "malaria"],
        "description": "Leading global non-profit dedicated to comprehensive control of malaria and communicable diseases.",
    },
    "giz": {
        "slug": "giz",
        "name": "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ)",
        "short_name": "GIZ",
        "logo_static": "img/partners/giz.png",
        "keywords": ["giz", "deutsche gesellschaft", "zusammenarbeit"],
        "description": "German federal enterprise providing sustainable international development solutions worldwide.",
    },
    "norwegian-refugee-council": {
        "slug": "norwegian-refugee-council",
        "name": "Norwegian Refugee Council (NRC)",
        "short_name": "NRC",
        "logo_static": "img/partners/norwegian-refugee-council.gif",
        "keywords": ["norwegian refugee council", "nrc", "norwegian"],
        "description": "Independent humanitarian organisation helping people forced to flee conflict and human rights violations.",
    },
    "public-services-international": {
        "slug": "public-services-international",
        "name": "Public Services International (PSI)",
        "short_name": "PSI",
        "logo_static": "img/partners/psi.png",
        "keywords": ["public services international", "psi"],
        "description": "Global union federation representing 30 million public service workers across 154 countries.",
    },
    "capacity-4-dev": {
        "slug": "capacity-4-dev",
        "name": "Capacity 4 Sustainable Development Ltd.",
        "short_name": "Capacity 4 Dev",
        "logo_static": "img/partners/capacity-4-dev.jpg",
        "keywords": ["capacity 4 sustainable development", "capacity 4 dev", "capacity4dev", "capacity 4"],
        "description": "Consulting and development initiative focused on organizational strengthening and systems development.",
    },
}


import re


def match_client_to_org(client_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Match a project's client_name string to a known organization entry."""
    if not client_name:
        return None
    cn_lower = client_name.lower().strip()
    for slug, org in ORGANIZATIONS.items():
        if any(kw in cn_lower for kw in org["keywords"]):
            return org
    return None


def get_org_slug(name: Optional[str]) -> str:
    """Generate or retrieve a verified URL-safe slug for an organization."""
    if not name:
        return ""
    org = match_client_to_org(name)
    if org:
        return org["slug"]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug

