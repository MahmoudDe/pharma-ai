from __future__ import annotations

import re

from app.warehouse.matching import canonical_key


_ARABIC_CHAR = re.compile(r"[\u0600-\u06FF]")

# Normalized Arabic key → English INCI (canonical_key applied on lookup)
_ARABIC_ALIASES: dict[str, str] = {
    "ايتانول جي": "ethanol",
    "كحول": "ethanol",
    "تكسابون": "sodium laureth sulfate",
    "تكسابون مغنزيوم": "magnesium laureth sulfate",
    "بيتائين": "betaine",
    "كمبرلان": "cocamidopropyl betaine",
    "غليسيرين": "glycerin",
    "جليسيرين": "glycerin",
    "بروبلين غليكول": "propylene glycol",
    "بروبيلين غليكول": "propylene glycol",
    "بروبيل برابين": "propylparaben",
    "متيل برابين": "methylparaben",
    "بنزوفينون": "benzophenone",
    "بولي كواترنيوم 10": "polyquaternium-10",
    "بولي كواترنيوم 7": "polyquaternium-7",
    "توين 20": "polysorbate 20",
    "ستيول اتش اي": "steareth",
    "ستريث 29": "steareth-29",
    "ستريث2": "steareth-2",
    "ستريث 2": "steareth-2",
    "لانيت 16": "ceteareth-16",
    "لانيت او": "ceteareth",
    "لانيت أو": "ceteareth",
    "ايمولجين ب2": "ceteareth-2",
    "كريمافور الماني": "cetearyl alcohol",
    "كريمافور ألماني": "cetearyl alcohol",
    "زيت اللوز": "almond oil",
    "زيت لوز حلو": "sweet almond oil",
    "زيت جوز الهند": "coconut oil",
    "زيت برافين": "mineral oil",
    "برافين": "paraffin",
    "بانتينول": "panthenol",
    "آلانتوئين": "allantoin",
    "الانتوئين": "allantoin",
    "سوربيتول": "sorbitol",
    "زانتان غام": "xanthan gum",
    "كوزميديا غوار": "guar hydroxypropyltrimonium chloride",
    "كاؤولان": "kaolin",
    "جي ام اس": "glyceryl monostearate",
    "جي أم أس": "glyceryl monostearate",
    "سيلكون 350": "dimethicone",
    "دي ام دي ام": "dmdm hydantoin",
    "دي أم دي أم": "dmdm hydantoin",
    "زنك برثيون": "zinc pyrithione",
    "زنك": "zinc oxide",
    "سالسيليك اسيد": "salicylic acid",
    "سالسيليك أسيد": "salicylic acid",
    "حمض الفواكه": "citric acid",
    "فيتامين سي": "ascorbic acid",
    "مغنزيوم اسكوربيك فوسفات": "magnesium ascorbyl phosphate",
    "هيالورينيك اسيد": "hyaluronic acid",
    "صوديوم هيالورينات": "sodium hyaluronate",
    "هيدروكينون": "hydroquinone",
    "اربوتين بيتا": "arbutin",
    "أربوتين بيتا": "arbutin",
    "أربوتين الفا": "alpha arbutin",
    "أربوتين ألفا": "alpha arbutin",
    "الفا اربوتين": "alpha arbutin",
    "ألفا أربوتين": "alpha arbutin",
    "آلانتوئين": "allantoin",
    "الانتوئين": "allantoin",
    "بانتينول": "panthenol",
    "تيتان": "titanium dioxide",
    "دواء": "active pharmaceutical ingredient",
    "صباغات": "colorant",
    "مقصب": "preservative",
    "ايزو بروبيل ميرستات": "isopropyl myristate",
    "ميرستات": "myristic acid",
    "ميرتول 318": "methylchloroisothiazolinone",
    "بي اتش تي": "phenoxyethanol",
    "تيتان": "titanium dioxide",
    "اكواجل": "acrylates copolymer",
    "أكواجل": "acrylates copolymer",
    "اوليفيرا": "aloe vera",
    "أوليفيرا": "aloe vera",
    "زبدة الشيا": "shea butter",
    "كولاجين": "collagen",
    "كرياتين": "creatine",
    "لانولين": "lanolin",
    "ديكوارت": "edta",
    "سينمات": "cinnamate",
    "كلمبازول": "climbazole",
    "ليفسكول": "licorice extract",
}


def has_arabic(text: str) -> bool:
    return bool(_ARABIC_CHAR.search(text))


def normalize_arabic_key(text: str) -> str:
    s = text.strip()
    s = re.sub(r"\s+", " ", s)
    for src, dst in (
        ("أ", "ا"),
        ("إ", "ا"),
        ("آ", "ا"),
        ("ى", "ي"),
        ("ؤ", "و"),
        ("ئ", "ي"),
        ("ة", "ه"),
        ("ـ", ""),
    ):
        s = s.replace(src, dst)
    return s.lower()


def resolve_arabic_alias(raw: str) -> tuple[str, float] | None:
    if not has_arabic(raw):
        return None
    key = normalize_arabic_key(raw)
    inci = _ARABIC_ALIASES.get(key)
    if inci:
        return canonical_key(inci), 0.93
    # Fuzzy among Arabic keys
    try:
        from rapidfuzz import fuzz, process

        match = process.extractOne(key, list(_ARABIC_ALIASES.keys()), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 88:
            return canonical_key(_ARABIC_ALIASES[match[0]]), min(0.88, match[1] / 100.0)
    except ImportError:
        pass
    return None
