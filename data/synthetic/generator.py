from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class PaymentEvent:
    event_id: str
    customer_id: str
    merchant_id: str
    order_id: str
    amount: float
    failure_type: str
    failure_category: str
    payment_method: str
    attempt_count: int


def generate_synthetic_events(count: int = 20) -> List[PaymentEvent]:
    failure_map = [
        ("CARD_DECLINED", "PAYMENT_METHOD"),
        ("BANK_UNAVAILABLE", "BANK"),
        ("GATEWAY_TIMEOUT", "TECHNICAL"),
        ("OTP_FAILURE", "AUTHENTICATION"),
        ("CUSTOMER_ABANDONED", "ABANDONMENT"),
        ("INSUFFICIENT_FUNDS", "BANK"),
        ("HIGH_RISK", "RISK"),
        ("PAYMENT_PENDING", "PENDING"),
    ]

    events: List[PaymentEvent] = []
    for i in range(count):
        failure_type, failure_category = random.choice(failure_map)
        events.append(
            PaymentEvent(
                event_id=f"evt_{i + 1:04d}",
                customer_id=f"cust_{random.randint(1, 500)}",
                merchant_id=f"merch_{random.randint(1, 80)}",
                order_id=f"ord_{random.randint(1000, 9999)}",
                amount=round(random.uniform(150, 7500), 2),
                failure_type=failure_type,
                failure_category=failure_category,
                payment_method=random.choice(["CARD", "UPI", "NETBANKING", "WALLET"]),
                attempt_count=random.randint(1, 4),
            )
        )
    return events


if __name__ == "__main__":
    sample = generate_synthetic_events(5)
    for event in sample:
        print(asdict(event))
