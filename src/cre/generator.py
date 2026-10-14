"""Générateur de CRE (comptes rendus d'événements) bancaires fictifs.

Toutes les données sont synthétiques : IBAN, noms et montants sont tirés au
hasard et ne correspondent à aucune personne réelle.
"""

from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

FIRST_NAMES = ["Anne", "Yann", "Morgane", "Loïc", "Gwen", "Erwan", "Nolwenn", "Ronan", "Maëlle", "Tanguy"]
LAST_NAMES = ["Le Gall", "Kerbrat", "Morvan", "Le Bihan", "Quéméner", "Tanguy", "Riou", "Guivarc'h", "Abgrall", "Le Roux"]

# Type d'opération -> (sens, montant min, montant max)
OPERATIONS = {
    "CB_PAIEMENT": ("DEBIT", 1, 300),
    "CB_RETRAIT": ("DEBIT", 20, 500),
    "VIREMENT_EMIS": ("DEBIT", 10, 5000),
    "VIREMENT_RECU": ("CREDIT", 10, 5000),
    "VIREMENT_INSTANT": ("DEBIT", 1, 15000),
    "PRELEVEMENT": ("DEBIT", 5, 800),
    "REMISE_CHEQUE": ("CREDIT", 10, 3000),
}
OPERATION_WEIGHTS = [50, 12, 10, 10, 6, 10, 2]

CHANNELS = ["CARTE", "MOBILE", "WEB", "AGENCE", "GAB"]
MERCHANT_CATEGORIES = ["ALIMENTATION", "CARBURANT", "RESTAURATION", "TRANSPORT", "LOISIRS", "SANTE", "E_COMMERCE"]
CITIES = ["Brest", "Quimper", "Landerneau", "Morlaix", "Rennes", "Vannes", "Lorient", "Saint-Brieuc"]
ENTITIES = ["CMB", "CMSO", "ARKEA_DIRECT", "FORTUNEO"]
STATUSES = ["COMPTABILISE", "EN_ATTENTE", "REJETE"]
STATUS_WEIGHTS = [94, 5, 1]


def _iban(rng: random.Random) -> str:
    return "FR76" + "".join(rng.choices(string.digits, k=23))


@dataclass
class Account:
    account_id: str
    iban: str
    holder: str
    entity: str
    balance: float = field(default=0.0)


class CreGenerator:
    """Produit un flux de CRE réalistes sur un portefeuille de comptes fixe."""

    def __init__(self, accounts: int = 5000, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.accounts = [
            Account(
                account_id=f"ACC{i:08d}",
                iban=_iban(self.rng),
                holder=f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}",
                entity=self.rng.choice(ENTITIES),
                balance=round(self.rng.uniform(100, 20000), 2),
            )
            for i in range(accounts)
        ]

    def event(self, now: datetime | None = None) -> dict:
        rng = self.rng
        account = rng.choice(self.accounts)
        op = rng.choices(list(OPERATIONS), weights=OPERATION_WEIGHTS)[0]
        direction, low, high = OPERATIONS[op]
        amount = round(rng.uniform(low, high), 2)
        status = rng.choices(STATUSES, weights=STATUS_WEIGHTS)[0]

        if status == "COMPTABILISE":
            account.balance = round(account.balance + (amount if direction == "CREDIT" else -amount), 2)

        is_card = op.startswith("CB_")
        category = rng.choice(MERCHANT_CATEGORIES) if is_card else None
        city = rng.choice(CITIES)
        timestamp = (now or datetime.now(timezone.utc)).isoformat()

        return {
            "event_id": str(uuid.UUID(int=rng.getrandbits(128))),
            "@timestamp": timestamp,
            "generated_at": timestamp,
            "account_id": account.account_id,
            "iban": account.iban,
            "holder_name": account.holder,
            "entity": account.entity,
            "operation_type": op,
            "direction": direction,
            "amount": amount,
            "currency": "EUR",
            "balance_after": account.balance,
            "channel": "CARTE" if is_card else rng.choice(CHANNELS[1:]),
            "merchant_category": category,
            "city": city,
            "status": status,
            "label": self._label(op, category, city),
        }

    def _label(self, op: str, category: str | None, city: str) -> str:
        if op == "CB_PAIEMENT":
            return f"PAIEMENT CB {category} {city.upper()} {self.rng.randint(1000, 9999)}"
        if op == "CB_RETRAIT":
            return f"RETRAIT DAB {city.upper()}"
        if op == "PRELEVEMENT":
            return f"PRLV SEPA {self.rng.choice(['EDF', 'ORANGE', 'MUTUELLE', 'ASSURANCE', 'LOYER'])}"
        return f"{op.replace('_', ' ')} REF {self.rng.randint(100000, 999999)}"
