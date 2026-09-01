from __future__ import annotations

from typing import Dict, Optional


class PaymentSimulator:
    def __init__(self):
        self.outcomes = {
            "RETRY_PAYMENT": {"success": 0.72, "pending": 0.18, "failed": 0.10},
            "SWITCH_PAYMENT_METHOD": {"success": 0.68, "pending": 0.15, "failed": 0.17},
            "SEND_RECOVERY_MESSAGE": {"success": 0.45, "pending": 0.35, "failed": 0.20},
            "SCHEDULE_RETRY": {"success": 0.62, "pending": 0.25, "failed": 0.13},
            "ESCALATE": {"success": 0.52, "pending": 0.30, "failed": 0.18},
            "STOP": {"success": 0.0, "pending": 0.0, "failed": 1.0},
        }

    def execute(self, action: str, amount: float, risk_score: float = 0.0) -> Dict:
        if action not in self.outcomes:
            raise ValueError(f"Unsupported action: {action}")

        base = self.outcomes[action]
        adjusted = dict(base)

        if risk_score > 0.8 and action in {"RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD"}:
            adjusted["success"] *= 0.7
            adjusted["failed"] += 0.15

        success_state = "SUCCESS" if action != "STOP" else "STOPPED"
        if action == "STOP":
            return {
                "status": "STOPPED",
                "action": action,
                "recovered_amount": 0.0,
                "simulated": True,
                "reason": "Action explicitly halted by policy or workflow",
            }

        if adjusted["success"] > 0.7:
            recovered_amount = amount * 0.9
            status = success_state
        elif adjusted["success"] > 0.45:
            recovered_amount = amount * 0.55
            status = "PENDING"
        else:
            recovered_amount = 0.0
            status = "FAILED"

        return {
            "status": status,
            "action": action,
            "recovered_amount": round(recovered_amount, 2),
            "simulated": True,
            "reason": "Deterministic simulator response generated for demo and evaluation purposes.",
        }


if __name__ == "__main__":
    sim = PaymentSimulator()
    print(sim.execute("RETRY_PAYMENT", 5000, risk_score=0.4))
