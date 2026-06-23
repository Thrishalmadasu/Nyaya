"""Curated offence -> lay-synonym map for statute chunk enrichment.

Why this exists
---------------
Retrieval embeds the section text and matches it against the advocate's query.
That works when the query uses the same words as the statute ("punishment for
murder" -> "Punishment for murder"), but a fact-pattern query phrased in plain
language can miss the right section: e.g. "taking someone's property secretly"
did not retrieve the theft section, because the embedding of that phrase did not
sit close enough to the word "theft".

To close that gap cheaply (no LLM, fully deterministic), we attach a short line
of lay synonyms to each chunk's embedded text and store them in a `keywords`
metadata field. When a section's title/body mentions a known offence, the
matching synonyms are added so plain-language queries land on the right law.

How to extend
-------------
Add a (triggers, synonyms) row below. `triggers` are substrings expected in the
statute title/body (legal terms); `synonyms` are the everyday words a user might
type. Keep synonyms short and unambiguous — they are appended verbatim to the
embedded text, so noise here becomes retrieval noise.
"""
from __future__ import annotations

# Each row: (triggers found in statute text, lay synonyms to inject).
# Triggers are matched case-insensitively against the title + start of the body.
OFFENCE_SYNONYMS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("murder", "culpable homicide", "homicide"),
     ("killing", "killed", "kill", "caused death", "took a life", "fatal attack")),
    (("theft",),
     ("stealing", "stole", "taking property", "took property", "took belongings")),
    (("robbery",),
     ("robbed", "forceful taking", "snatching with force")),
    (("dacoity",),
     ("gang robbery", "armed robbery by group")),
    (("extortion",),
     ("blackmail", "demanding money by threat", "ransom demand")),
    (("cheating",),
     ("fraud", "defrauding", "deceiving", "deceived", "scam", "conned")),
    (("forgery", "forged", "false document"),
     ("fake document", "counterfeit", "faked signature", "forged papers")),
    (("criminal breach of trust", "misappropriation"),
     ("embezzlement", "embezzled", "siphoned funds", "misused entrusted money")),
    (("rape", "sexual assault", "sexual harassment", "outraging"),
     ("sexual assault", "molestation", "forced sex", "non-consensual", "assaulted a woman")),
    (("kidnapping", "abduction"),
     ("abducted", "taken away by force", "child taken", "held captive")),
    (("grievous hurt", "hurt", "assault", "criminal force"),
     ("injury", "injured", "beating", "attacked", "wounding", "physical harm")),
    (("criminal intimidation",),
     ("threat", "threatening", "threatened", "intimidation", "menacing")),
    (("defamation",),
     ("slander", "libel", "damaging reputation", "false statement about a person")),
    (("mischief",),
     ("property damage", "vandalism", "destroyed property")),
    (("trespass",),
     ("unlawful entry", "entered without permission", "broke in")),
    (("bribery", "corruption", "public servant"),
     ("bribe", "kickback", "illegal gratification")),
    (("abetment", "abet"),
     ("aiding", "instigating", "encouraging the crime", "helped commit")),
    (("conspiracy",),
     ("plotting", "planned together", "agreed to commit")),
    (("common intention", "common object", "unlawful assembly"),
     ("acted together", "joint liability", "mob", "group acting together")),
    (("attempt",),
     ("tried to", "attempted", "did not complete")),
    (("dowry",),
     ("dowry death", "bride harassment", "demand for dowry")),
    (("negligence", "rash", "negligent"),
     ("careless", "reckless", "accidental", "without due care")),
    (("defamation", "insult", "provocation"),
     ("insulted", "provoked")),
]


def keywords_for(title: str, body: str = "", *, scan_body_chars: int = 400) -> list[str]:
    """Return lay synonyms for any offences mentioned in the section title/body.

    Matches each row's triggers against the title plus the first
    ``scan_body_chars`` of the body (the title is the strongest signal; the body
    head catches sections whose title is generic). Synonyms are returned in
    definition order, de-duplicated.
    """
    haystack = f"{title} {body[:scan_body_chars]}".lower()
    out: list[str] = []
    seen: set[str] = set()
    for triggers, synonyms in OFFENCE_SYNONYMS:
        if any(t in haystack for t in triggers):
            for s in synonyms:
                if s not in seen:
                    seen.add(s)
                    out.append(s)
    return out
