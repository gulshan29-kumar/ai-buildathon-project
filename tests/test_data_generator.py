from __future__ import annotations

import csv
import os
import shutil
import tempfile
import pytest

from ml_training.generate_data import (
    generate_realistic_dataset,
    validate_dataset,
)


@pytest.fixture
def temp_output_dir():
    temp_dir = tempfile.mkdtemp(prefix="fintech_gen_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_generator_small_dataset_and_validation(temp_output_dir):
    counts = generate_realistic_dataset(
        num_customers=50,
        num_transactions=200,
        seed=42,
        output_dir=temp_output_dir,
    )
    assert counts["customers"] == 50
    assert counts["transactions"] == 200
    assert counts["merchants"] >= 50
    assert counts["payment_attempts"] >= 200
    assert counts["checkout_sessions"] == 200

    # Ensure validation passes without error
    validate_dataset(temp_output_dir)


def test_generator_determinism(temp_output_dir):
    dir1 = os.path.join(temp_output_dir, "run1")
    dir2 = os.path.join(temp_output_dir, "run2")

    generate_realistic_dataset(num_customers=30, num_transactions=100, seed=123, output_dir=dir1)
    generate_realistic_dataset(num_customers=30, num_transactions=100, seed=123, output_dir=dir2)

    with open(os.path.join(dir1, "transactions.csv"), "r", encoding="utf-8") as f1, \
         open(os.path.join(dir2, "transactions.csv"), "r", encoding="utf-8") as f2:
        assert f1.read() == f2.read()


def test_no_negative_amounts_and_positive_bounds(temp_output_dir):
    generate_realistic_dataset(
        num_customers=40,
        num_transactions=150,
        seed=99,
        output_dir=temp_output_dir,
    )

    txn_path = os.path.join(temp_output_dir, "transactions.csv")
    with open(txn_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            amount = float(row["amount"])
            assert amount > 0.0, f"Negative or zero amount found: {amount}"
            assert row["currency"] == "INR"
            assert row["payment_method"] in {"UPI", "CARD", "NETBANKING", "WALLET"}
            assert row["gateway"] in {"GATEWAY_A", "GATEWAY_B", "GATEWAY_C"}


def test_successful_transactions_have_successful_terminal_attempt(temp_output_dir):
    generate_realistic_dataset(
        num_customers=40,
        num_transactions=150,
        seed=77,
        output_dir=temp_output_dir,
    )

    att_path = os.path.join(temp_output_dir, "payment_attempts.csv")
    attempts_by_txn = {}
    with open(att_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            attempts_by_txn.setdefault(row["transaction_id"], []).append(row)

    txn_path = os.path.join(temp_output_dir, "transactions.csv")
    with open(txn_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            attempts = attempts_by_txn[row["transaction_id"]]
            if row["status"] == "SUCCESS":
                assert attempts[-1]["status"] == "SUCCESS"
                assert sum(1 for a in attempts if a["status"] == "SUCCESS") == 1
            else:
                assert all(a["status"] == "FAILED" for a in attempts)
