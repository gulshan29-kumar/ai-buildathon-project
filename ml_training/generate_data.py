from __future__ import annotations

import argparse
import csv
import math
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set, Tuple


PAYMENT_METHODS = ["UPI", "CARD", "NETBANKING", "WALLET"]
GATEWAYS = ["GATEWAY_A", "GATEWAY_B", "GATEWAY_C"]

FAILURE_CODES = [
    "GATEWAY_TIMEOUT",
    "BANK_UNAVAILABLE",
    "INSUFFICIENT_FUNDS",
    "CARD_DECLINED",
    "CARD_EXPIRED",
    "OTP_FAILURE",
    "AUTH_TIMEOUT",
    "HIGH_RISK",
    "CUSTOMER_ABANDONED",
    "PAYMENT_PENDING",
    "DUPLICATE_PAYMENT",
    "ORDER_CREATION_FAILED",
]

FAILURE_CATEGORY_MAP = {
    "GATEWAY_TIMEOUT": "TEMPORARY",
    "BANK_UNAVAILABLE": "BANK",
    "INSUFFICIENT_FUNDS": "CUSTOMER",
    "CARD_DECLINED": "PAYMENT_METHOD",
    "CARD_EXPIRED": "PAYMENT_METHOD",
    "OTP_FAILURE": "AUTHENTICATION",
    "AUTH_TIMEOUT": "AUTHENTICATION",
    "HIGH_RISK": "RISK",
    "CUSTOMER_ABANDONED": "ABANDONMENT",
    "PAYMENT_PENDING": "PENDING",
    "DUPLICATE_PAYMENT": "DUPLICATE",
    "ORDER_CREATION_FAILED": "MERCHANT",
}

MERCHANT_TYPES = [
    ("E-commerce", 0.35, 1200.0, 3500.0),
    ("SaaS / Subscriptions", 0.20, 799.0, 4999.0),
    ("Food & Delivery", 0.20, 250.0, 850.0),
    ("Travel & Hospitality", 0.15, 3500.0, 18000.0),
    ("Utilities & Bills", 0.10, 450.0, 2500.0),
]


def generate_realistic_dataset(
    num_customers: int,
    num_transactions: int,
    seed: int,
    output_dir: str,
) -> Dict[str, int]:
    """Generates realistic synthetic fintech data with causal domain relationships."""
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    base_time = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Generate Merchants
    num_merchants = max(50, min(1000, num_customers // 20))
    merchants: List[Dict[str, Any]] = []
    for m_idx in range(1, num_merchants + 1):
        m_type, _, _, _ = random.choices(
            MERCHANT_TYPES, weights=[m[1] for m in MERCHANT_TYPES], k=1
        )[0]
        merchants.append({
            "merchant_id": f"merch_{m_idx:04d}",
            "name": f"Merchant_{m_idx:04d}_{m_type.split()[0]}",
            "business_type": m_type,
            "risk_score": round(random.betavariate(1.2, 8.0), 3),
            "created_at": (base_time - timedelta(days=random.randint(180, 720))).isoformat(),
            "updated_at": (base_time - timedelta(days=random.randint(1, 30))).isoformat(),
        })

    # 2. Generate Customers with Archetypes (Returning vs New, Risk Tiers)
    customers: List[Dict[str, Any]] = []
    customer_history_map: Dict[str, Dict[str, Any]] = {}

    for c_idx in range(1, num_customers + 1):
        is_returning = random.random() < 0.65
        cust_id = f"cust_{c_idx:06d}"

        if is_returning:
            total_txns = random.randint(5, 80)
            fail_rate = random.uniform(0.05, 0.20)
            failed_txns = int(total_txns * fail_rate)
            success_txns = total_txns - failed_txns
            success_rate = round(success_txns / total_txns, 3)
            risk_score = round(random.betavariate(1.5, 9.0), 3)  # mostly low risk
            customer_days = random.randint(90, 600)
            pref_method = random.choices(PAYMENT_METHODS, weights=[0.55, 0.25, 0.12, 0.08], k=1)[0]
            avg_amount = round(random.uniform(500, 4500), 2)
        else:
            total_txns = random.randint(0, 3)
            failed_txns = random.randint(0, total_txns)
            success_txns = total_txns - failed_txns
            success_rate = round(success_txns / total_txns, 3) if total_txns > 0 else 0.0
            risk_score = round(random.betavariate(2.0, 5.0), 3)  # slightly wider variance
            customer_days = random.randint(1, 60)
            pref_method = random.choices(PAYMENT_METHODS, weights=[0.45, 0.30, 0.15, 0.10], k=1)[0]
            avg_amount = round(random.uniform(300, 3000), 2)

        cust_since = base_time - timedelta(days=customer_days)

        cust_record = {
            "customer_id": cust_id,
            "total_transactions": total_txns,
            "successful_transactions": success_txns,
            "failed_transactions": failed_txns,
            "success_rate": success_rate,
            "average_transaction_amount": avg_amount,
            "preferred_payment_method": pref_method,
            "customer_since": cust_since.isoformat(),
            "risk_score": risk_score,
            "created_at": cust_since.isoformat(),
            "updated_at": (cust_since + timedelta(days=random.randint(0, customer_days))).isoformat(),
        }
        customers.append(cust_record)
        customer_history_map[cust_id] = cust_record

    # 3. Stream CSV Generation for Transactions, Attempts, CheckoutSessions, Subscriptions
    txn_file = os.path.join(output_dir, "transactions.csv")
    att_file = os.path.join(output_dir, "payment_attempts.csv")
    chk_file = os.path.join(output_dir, "checkout_sessions.csv")
    sub_file = os.path.join(output_dir, "subscriptions.csv")
    merch_file = os.path.join(output_dir, "merchants.csv")
    cust_file = os.path.join(output_dir, "customers.csv")

    # Write merchants and customers
    with open(merch_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(merchants[0].keys()))
        writer.writeheader()
        writer.writerows(merchants)

    with open(cust_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(customers[0].keys()))
        writer.writeheader()
        writer.writerows(customers)

    attempt_counter = 0
    subscription_counter = 0
    session_counter = 0

    # Merchant volume distribution (Pareto 80/20)
    merchant_weights = [1.0 / (idx ** 0.8) for idx in range(1, len(merchants) + 1)]

    # Open transaction and related files for streaming writes
    with open(txn_file, "w", newline="", encoding="utf-8") as f_txn, \
         open(att_file, "w", newline="", encoding="utf-8") as f_att, \
         open(chk_file, "w", newline="", encoding="utf-8") as f_chk, \
         open(sub_file, "w", newline="", encoding="utf-8") as f_sub:

        txn_fields = [
            "transaction_id", "customer_id", "merchant_id", "amount", "currency",
            "payment_method", "gateway", "status", "failure_code", "failure_category",
            "risk_score", "attempt_number", "created_at", "updated_at"
        ]
        att_fields = [
            "attempt_id", "transaction_id", "attempt_number", "payment_method",
            "gateway", "status", "failure_code", "timestamp"
        ]
        chk_fields = [
            "session_id", "transaction_id", "customer_id", "status",
            "abandonment_reason", "total_amount", "created_at", "updated_at"
        ]
        sub_fields = [
            "subscription_id", "customer_id", "merchant_id", "plan_name",
            "status", "renewal_amount", "created_at", "updated_at"
        ]

        w_txn = csv.DictWriter(f_txn, fieldnames=txn_fields)
        w_att = csv.DictWriter(f_att, fieldnames=att_fields)
        w_chk = csv.DictWriter(f_chk, fieldnames=chk_fields)
        w_sub = csv.DictWriter(f_sub, fieldnames=sub_fields)

        w_txn.writeheader()
        w_att.writeheader()
        w_chk.writeheader()
        w_sub.writeheader()

        # Cache recent transactions for deterministic duplicate generation
        recent_txns: List[Dict[str, Any]] = []

        for t_idx in range(1, num_transactions + 1):
            txn_id = f"txn_{t_idx:07d}"

            # Customer selection: Returning customers transact more frequently
            cust = random.choice(customers)
            cust_id = cust["customer_id"]
            cust_history = customer_history_map[cust_id]

            # Merchant selection via power-law weight
            merch = random.choices(merchants, weights=merchant_weights, k=1)[0]
            merch_id = merch["merchant_id"]
            m_type = merch["business_type"]

            # Realistic timestamp within the last 30 days
            day_offset = random.randint(0, 30)
            # Diurnal distribution: peak 10:00 - 22:00
            hour = random.choices(
                population=list(range(24)),
                weights=[1, 1, 1, 1, 2, 3, 5, 8, 12, 16, 20, 22, 22, 21, 20, 19, 21, 24, 25, 23, 18, 12, 6, 3],
                k=1
            )[0]
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            created_dt = base_time + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)

            # Payment method selection (aligns with customer preference)
            if random.random() < 0.70:
                payment_method = cust["preferred_payment_method"]
            else:
                payment_method = random.choice(PAYMENT_METHODS)

            # Gateway selection with individual reliability
            gateway = random.choice(GATEWAYS)

            # Realistic amount distribution (strictly positive)
            if payment_method == "UPI":
                amount = round(random.lognormvariate(6.5, 0.8), 2)  # median ~665 INR
            elif payment_method == "CARD":
                amount = round(random.lognormvariate(7.8, 0.9), 2)  # median ~2440 INR
            elif payment_method == "NETBANKING":
                amount = round(random.lognormvariate(8.4, 0.9), 2)  # median ~4400 INR
            else:  # WALLET
                amount = round(random.lognormvariate(5.8, 0.6), 2)  # median ~330 INR

            amount = max(10.0, min(150000.0, amount))

            # Transaction risk calculation (correlated with customer risk, amount, and merchant)
            amount_risk_factor = min(1.0, amount / 50000.0)
            txn_risk_score = round(
                0.60 * cust["risk_score"] +
                0.25 * merch["risk_score"] +
                0.15 * amount_risk_factor,
                3
            )

            # Causal determination of initial payment attempt
            # Returning customer bonus
            loyalty_factor = 0.15 if cust["total_transactions"] > 5 else -0.05
            failure_penalty = -0.12 if cust["failed_transactions"] > 2 else 0.0
            risk_penalty = -0.40 if txn_risk_score > 0.75 else 0.0

            base_success_prob = 0.82 + loyalty_factor + failure_penalty + risk_penalty
            base_success_prob = max(0.05, min(0.97, base_success_prob))

            # Check if this is a deliberate duplicate payment scenario (~1.5% chance)
            is_duplicate = False
            if recent_txns and random.random() < 0.015:
                ref_txn = random.choice(recent_txns[-50:])
                if ref_txn["status"] == "FAILED":
                    is_duplicate = True
                    cust_id = ref_txn["customer_id"]
                    merch_id = ref_txn["merchant_id"]
                    amount = ref_txn["amount"]
                    payment_method = ref_txn["payment_method"]
                    created_dt = datetime.fromisoformat(ref_txn["created_at"]) + timedelta(seconds=random.randint(10, 110))

            # Generate CheckoutSession
            session_counter += 1
            session_id = f"chk_{session_counter:07d}"
            session_dt = created_dt - timedelta(seconds=random.randint(15, 300))

            # Determine failure code if failure occurs
            failure_code = None
            failure_category = None
            txn_status = "SUCCESS"

            if is_duplicate:
                failure_code = "DUPLICATE_PAYMENT"
                failure_category = "DUPLICATE"
                txn_status = "FAILED"
            elif random.random() > base_success_prob:
                txn_status = "FAILED"
                if txn_risk_score > 0.75 or random.random() < 0.06:
                    failure_code = "HIGH_RISK"
                elif payment_method == "CARD" and random.random() < 0.25:
                    failure_code = random.choice(["CARD_DECLINED", "CARD_EXPIRED"])
                elif gateway == "GATEWAY_B" and random.random() < 0.30:
                    failure_code = "GATEWAY_TIMEOUT"
                elif random.random() < 0.20:
                    failure_code = "BANK_UNAVAILABLE"
                elif random.random() < 0.20:
                    failure_code = "INSUFFICIENT_FUNDS"
                elif random.random() < 0.20:
                    failure_code = random.choice(["OTP_FAILURE", "AUTH_TIMEOUT"])
                elif random.random() < 0.15:
                    failure_code = "CUSTOMER_ABANDONED"
                elif random.random() < 0.10:
                    failure_code = "PAYMENT_PENDING"
                else:
                    failure_code = "ORDER_CREATION_FAILED"

                failure_category = FAILURE_CATEGORY_MAP[failure_code]

            # Generate Payment Attempts with Causal Logic
            num_attempts = 1
            if txn_status == "SUCCESS":
                # Some successful transactions took 2 attempts after initial transient failure
                if random.random() < 0.18:
                    num_attempts = 2
                    first_failure = random.choice(["GATEWAY_TIMEOUT", "OTP_FAILURE"])
                else:
                    num_attempts = 1
                    first_failure = None
            else:
                # Failed transaction attempts
                if failure_code == "GATEWAY_TIMEOUT":
                    # Temporary gateway failures can retry up to 2-3 times
                    num_attempts = random.choices([1, 2, 3], weights=[0.4, 0.4, 0.2], k=1)[0]
                elif failure_code in {"CARD_EXPIRED", "HIGH_RISK", "DUPLICATE_PAYMENT"}:
                    # Unrecoverable on same card / risk / duplicate stops immediately
                    num_attempts = 1
                elif failure_code == "INSUFFICIENT_FUNDS":
                    # Customer balance deficit: 1 or 2 quick retries that also fail
                    num_attempts = random.choices([1, 2], weights=[0.7, 0.3], k=1)[0]
                else:
                    num_attempts = random.choices([1, 2], weights=[0.6, 0.4], k=1)[0]

            attempt_dt = created_dt
            for att_num in range(1, num_attempts + 1):
                attempt_counter += 1
                att_id = f"att_{attempt_counter:08d}"

                if att_num > 1:
                    attempt_dt = attempt_dt + timedelta(seconds=random.randint(15, 120))

                if txn_status == "SUCCESS":
                    if att_num < num_attempts:
                        # Preceding failed attempt
                        att_status = "FAILED"
                        att_fail_code = first_failure
                    else:
                        # Final attempt is SUCCESS
                        att_status = "SUCCESS"
                        att_fail_code = None
                else:
                    att_status = "FAILED"
                    # Expired cards always fail on retry with same code
                    att_fail_code = failure_code

                w_att.writerow({
                    "attempt_id": att_id,
                    "transaction_id": txn_id,
                    "attempt_number": att_num,
                    "payment_method": payment_method,
                    "gateway": gateway,
                    "status": att_status,
                    "failure_code": att_fail_code or "",
                    "timestamp": attempt_dt.isoformat(),
                })

            updated_dt = attempt_dt + timedelta(seconds=random.randint(1, 5))

            # Write Transaction
            txn_record = {
                "transaction_id": txn_id,
                "customer_id": cust_id,
                "merchant_id": merch_id,
                "amount": amount,
                "currency": "INR",
                "payment_method": payment_method,
                "gateway": gateway,
                "status": txn_status,
                "failure_code": failure_code or "",
                "failure_category": failure_category or "",
                "risk_score": txn_risk_score,
                "attempt_number": num_attempts,
                "created_at": created_dt.isoformat(),
                "updated_at": updated_dt.isoformat(),
            }
            w_txn.writerow(txn_record)
            recent_txns.append(txn_record)
            if len(recent_txns) > 200:
                recent_txns.pop(0)

            # Write CheckoutSession
            chk_status = "COMPLETED" if txn_status == "SUCCESS" else "ABANDONED"
            chk_reason = None
            if chk_status == "ABANDONED":
                chk_reason = failure_code if failure_code else "CHECKOUT_TIMEOUT"

            w_chk.writerow({
                "session_id": session_id,
                "transaction_id": txn_id,
                "customer_id": cust_id,
                "status": chk_status,
                "abandonment_reason": chk_reason or "",
                "total_amount": amount,
                "created_at": session_dt.isoformat(),
                "updated_at": updated_dt.isoformat(),
            })

            # Subscription creation for SaaS recurring merchants (~10% of transactions)
            if m_type == "SaaS / Subscriptions" and random.random() < 0.35:
                subscription_counter += 1
                sub_id = f"sub_{subscription_counter:06d}"
                sub_status = "ACTIVE" if txn_status == "SUCCESS" else "PAST_DUE"
                w_sub.writerow({
                    "subscription_id": sub_id,
                    "customer_id": cust_id,
                    "merchant_id": merch_id,
                    "plan_name": f"Subscription Plan {random.choice(['Basic', 'Pro', 'Enterprise'])}",
                    "status": sub_status,
                    "renewal_amount": amount,
                    "created_at": session_dt.isoformat(),
                    "updated_at": updated_dt.isoformat(),
                })

    return {
        "merchants": len(merchants),
        "customers": len(customers),
        "transactions": num_transactions,
        "payment_attempts": attempt_counter,
        "checkout_sessions": session_counter,
        "subscriptions": subscription_counter,
    }


def validate_dataset(output_dir: str) -> None:
    """Validates data integrity, causal constraints, and invariants."""
    txn_file = os.path.join(output_dir, "transactions.csv")
    att_file = os.path.join(output_dir, "payment_attempts.csv")
    cust_file = os.path.join(output_dir, "customers.csv")
    merch_file = os.path.join(output_dir, "merchants.csv")
    chk_file = os.path.join(output_dir, "checkout_sessions.csv")

    for path in [txn_file, att_file, cust_file, merch_file, chk_file]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing required dataset file: {path}")

    # Load customers and merchants IDs
    customer_ids: Set[str] = set()
    with open(cust_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            customer_ids.add(row["customer_id"])

    merchant_ids: Set[str] = set()
    with open(merch_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            merchant_ids.add(row["merchant_id"])

    # Load attempts by transaction
    attempts_by_txn: Dict[str, List[Dict[str, Any]]] = {}
    with open(att_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            attempts_by_txn.setdefault(row["transaction_id"], []).append(row)

    # Validate transactions
    txns_count = 0
    duplicate_count = 0

    with open(txn_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            txns_count += 1
            txn_id = row["transaction_id"]
            amount = float(row["amount"])
            status = row["status"]
            cust_id = row["customer_id"]
            merch_id = row["merchant_id"]
            created_at = datetime.fromisoformat(row["created_at"])
            updated_at = datetime.fromisoformat(row["updated_at"])

            # 1. No negative or zero amounts
            if amount <= 0:
                raise AssertionError(f"Transaction {txn_id} has invalid non-positive amount: {amount}")

            # 2. Referential integrity
            if cust_id not in customer_ids:
                raise AssertionError(f"Transaction {txn_id} references unknown customer: {cust_id}")
            if merch_id not in merchant_ids:
                raise AssertionError(f"Transaction {txn_id} references unknown merchant: {merch_id}")

            # 3. Timestamp sanity
            if updated_at < created_at:
                raise AssertionError(f"Transaction {txn_id} has updated_at before created_at")

            # 4. Attempt checks
            attempts = attempts_by_txn.get(txn_id, [])
            if not attempts:
                raise AssertionError(f"Transaction {txn_id} has no payment attempts")

            if status == "SUCCESS":
                successful_attempts = [a for a in attempts if a["status"] == "SUCCESS"]
                if len(successful_attempts) != 1:
                    raise AssertionError(f"Successful transaction {txn_id} must have exactly 1 successful attempt, got {len(successful_attempts)}")
                # Terminal attempt must be the successful one
                if attempts[-1]["status"] != "SUCCESS":
                    raise AssertionError(f"Terminal attempt of successful transaction {txn_id} must be SUCCESS")
            elif status == "FAILED":
                successful_attempts = [a for a in attempts if a["status"] == "SUCCESS"]
                if successful_attempts:
                    raise AssertionError(f"Failed transaction {txn_id} has impossible successful attempt")

            # 5. Duplicate identifiability
            if row["failure_code"] == "DUPLICATE_PAYMENT":
                duplicate_count += 1
                if row["failure_category"] != "DUPLICATE":
                    raise AssertionError(f"Duplicate payment {txn_id} must have failure_category DUPLICATE")

    print(f"Validation passed for {txns_count} transactions ({duplicate_count} duplicate payment events identified).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Synthetic Fintech Dataset Generator")
    parser.add_argument("--customers", type=int, default=20000, help="Number of customers to generate")
    parser.add_argument("--transactions", type=int, default=100000, help="Number of transactions to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument("--output", type=str, default="data/synthetic", help="Output directory path")
    parser.add_argument("--skip-validation", action="store_true", help="Skip post-generation validation")

    args = parser.parse_args()

    print(f"Starting deterministic dataset generation:")
    print(f"  Seed: {args.seed}")
    print(f"  Customers: {args.customers}")
    print(f"  Transactions: {args.transactions}")
    print(f"  Output Directory: {args.output}")

    counts = generate_realistic_dataset(
        num_customers=args.customers,
        num_transactions=args.transactions,
        seed=args.seed,
        output_dir=args.output,
    )

    print("Generation complete:")
    for entity, count in counts.items():
        print(f"  - {entity}: {count:,}")

    if not args.skip_validation:
        print("Running validation suite...")
        validate_dataset(args.output)
        print("Dataset validation successful!")


if __name__ == "__main__":
    main()
