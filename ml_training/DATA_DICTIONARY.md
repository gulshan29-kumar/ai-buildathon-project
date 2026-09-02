# Synthetic Fintech Dataset Data Dictionary

> **Disclaimer**: This dataset is entirely synthetic and generated for simulation, benchmark modeling, and hackathon prototyping purposes. **These distributions and statistics do not represent real Razorpay production metrics, volumes, decline rates, or internal operational data.**

---

## 1. Overview & Generation Principles

The dataset generator in `ml_training/generate_data.py` models interdependent behavioral relationships across fintech payment entities rather than generating independent random columns.

Key causal modeling dynamics:
1. **Customer Loyalty & Experience**: Returning customers exhibit established transaction histories, higher baseline authorization rates (80–95%), lower risk scores, and lower churn rates.
2. **Prior Declines**: Customers with consecutive previous failures face lower immediate automated recovery rates.
3. **Transient Infrastructure vs. Hard Failures**:
   - `GATEWAY_TIMEOUT` and `BANK_UNAVAILABLE` represent transient upstream congestion that can succeed on automated retry or delayed scheduling.
   - `INSUFFICIENT_FUNDS` requires customer notification/top-up and will not immediately succeed on retry.
   - `CARD_EXPIRED` is a permanent failure where retrying the same card is guaranteed to fail; recovery requires switching the payment method.
   - `HIGH_RISK` transactions trigger safety blocks and must never be recovered via automated retries.
4. **Checkout Abandonment**: Checkout sessions model user funnel drop-offs, price sensitivity, and authentication friction.
5. **Diurnal Time Patterns**: Transaction frequency follows realistic peak hours (10:00 AM – 10:00 PM IST) and low overnight volumes (01:00 AM – 06:00 AM IST).
6. **Ticket Sizing**: Bounded log-normal distributions tailored to payment instruments (UPI micro-tickets, Card subscriptions/e-commerce, Netbanking commercial payments).

---

## 2. Table Specifications

### 2.1 `merchants.csv`
| Field | Type | Description |
| :--- | :--- | :--- |
| `merchant_id` | String (`merch_XXXX`) | Unique identifier for merchant. |
| `name` | String | Synthetic merchant trading name. |
| `business_type` | String | Industry category (`E-commerce`, `SaaS / Subscriptions`, `Food & Delivery`, `Travel & Hospitality`, `Utilities & Bills`). |
| `risk_score` | Float (`0.000` - `1.000`) | Merchant baseline compliance/chargeback risk rating. |
| `created_at` | ISO-8601 Timestamp | Onboarding date. |
| `updated_at` | ISO-8601 Timestamp | Last profile update timestamp. |

### 2.2 `customers.csv`
| Field | Type | Description |
| :--- | :--- | :--- |
| `customer_id` | String (`cust_XXXXXX`) | Unique identifier for customer. |
| `total_transactions` | Integer | Total lifetime attempted transactions. |
| `successful_transactions` | Integer | Total successful transactions settled. |
| `failed_transactions` | Integer | Total failed transactions recorded. |
| `success_rate` | Float (`0.000` - `1.000`) | Historical authorization success ratio. |
| `average_transaction_amount` | Float | Historical average spend in INR. |
| `preferred_payment_method` | String | Preferred instrument (`UPI`, `CARD`, `NETBANKING`, `WALLET`). |
| `customer_since` | ISO-8601 Timestamp | Account registration timestamp. |
| `risk_score` | Float (`0.000` - `1.000`) | Customer risk score derived from historical velocity and chargeback propensity. |
| `created_at` | ISO-8601 Timestamp | Creation timestamp. |
| `updated_at` | ISO-8601 Timestamp | Last modification timestamp. |

### 2.3 `transactions.csv`
| Field | Type | Description |
| :--- | :--- | :--- |
| `transaction_id` | String (`txn_XXXXXXX`) | Unique transaction identifier. |
| `customer_id` | String (`cust_XXXXXX`) | Foreign key referencing `customers.customer_id`. |
| `merchant_id` | String (`merch_XXXX`) | Foreign key referencing `merchants.merchant_id`. |
| `amount` | Float | Transaction amount in INR (strictly positive, non-zero). |
| `currency` | String | Default `INR`. |
| `payment_method` | String | Payment rail used (`UPI`, `CARD`, `NETBANKING`, `WALLET`). |
| `gateway` | String | Acquirer / gateway router (`GATEWAY_A`, `GATEWAY_B`, `GATEWAY_C`). |
| `status` | String | Final transaction state (`SUCCESS`, `FAILED`). |
| `failure_code` | String (Nullable) | Normalized failure reason if status is `FAILED`. |
| `failure_category` | String (Nullable) | High-level taxonomy category (see Taxonomy below). |
| `risk_score` | Float (`0.000` - `1.000`) | Transaction-level multi-factor risk score. |
| `attempt_number` | Integer | Total number of payment attempts executed. |
| `created_at` | ISO-8601 Timestamp | Initial transaction initiation timestamp. |
| `updated_at` | ISO-8601 Timestamp | Terminal transaction resolution timestamp. |

### 2.4 `payment_attempts.csv`
| Field | Type | Description |
| :--- | :--- | :--- |
| `attempt_id` | String (`att_XXXXXXXX`) | Unique attempt identifier. |
| `transaction_id` | String (`txn_XXXXXXX`) | Foreign key referencing `transactions.transaction_id`. |
| `attempt_number` | Integer | 1-indexed attempt sequence number (1, 2, 3...). |
| `payment_method` | String | Payment method used on this specific attempt. |
| `gateway` | String | Gateway dispatched for this attempt. |
| `status` | String | Attempt result (`SUCCESS`, `FAILED`). |
| `failure_code` | String (Nullable) | Failure reason for this attempt if failed. |
| `timestamp` | ISO-8601 Timestamp | Exact timestamp attempt was dispatched. |

### 2.5 `checkout_sessions.csv`
| Field | Type | Description |
| :--- | :--- | :--- |
| `session_id` | String (`chk_XXXXXXX`) | Unique checkout session identifier. |
| `transaction_id` | String (Nullable) | Linked transaction if checkout converted to payment. |
| `customer_id` | String (`cust_XXXXXX`) | Foreign key referencing `customers.customer_id`. |
| `status` | String | Checkout outcome (`COMPLETED`, `ABANDONED`). |
| `abandonment_reason` | String (Nullable) | Reason for drop-off (`PRICE_SHOCK`, `AUTH_FAILURE`, `DROPPED_OFF`, `CHECKOUT_TIMEOUT`, or failure code). |
| `total_amount` | Float | Cart value in INR. |
| `created_at` | ISO-8601 Timestamp | User checkout initialization timestamp. |
| `updated_at` | ISO-8601 Timestamp | Terminal session timestamp. |

### 2.6 `subscriptions.csv`
| Field | Type | Description |
| :--- | :--- | :--- |
| `subscription_id` | String (`sub_XXXXXX`) | Unique subscription identifier. |
| `customer_id` | String (`cust_XXXXXX`) | Foreign key referencing `customers.customer_id`. |
| `merchant_id` | String (`merch_XXXX`) | Foreign key referencing `merchants.merchant_id`. |
| `plan_name` | String | Subscription tier (`Basic`, `Pro`, `Enterprise`). |
| `status` | String | Mandate status (`ACTIVE`, `PAST_DUE`, `CANCELLED`). |
| `renewal_amount` | Float | Recurring billing charge in INR. |
| `created_at` | ISO-8601 Timestamp | Plan activation timestamp. |
| `updated_at` | ISO-8601 Timestamp | Last status change timestamp. |

---

## 3. Failure Taxonomy & Root Cause Mapping

| Failure Code | Category | Temporality | Recoverability | Default Recommended Action |
| :--- | :--- | :--- | :--- | :--- |
| `GATEWAY_TIMEOUT` | `TEMPORARY` | `TEMPORARY` | `HIGH` | `RETRY_PAYMENT` (Backoff) |
| `BANK_UNAVAILABLE` | `BANK` | `TEMPORARY` | `MEDIUM` | `SCHEDULE_RETRY` |
| `INSUFFICIENT_FUNDS`| `CUSTOMER` | `PERMANENT` | `LOW` | `SEND_RECOVERY_MESSAGE` |
| `CARD_DECLINED` | `PAYMENT_METHOD`| `PERMANENT` | `MEDIUM` | `SWITCH_PAYMENT_METHOD` |
| `CARD_EXPIRED` | `PAYMENT_METHOD`| `PERMANENT` | `LOW` | `SWITCH_PAYMENT_METHOD` |
| `OTP_FAILURE` | `AUTHENTICATION`| `TEMPORARY` | `HIGH` | `SEND_RECOVERY_MESSAGE` |
| `AUTH_TIMEOUT` | `AUTHENTICATION`| `TEMPORARY` | `HIGH` | `SEND_RECOVERY_MESSAGE` |
| `HIGH_RISK` | `RISK` | `PERMANENT` | `NONE` | `ESCALATE` (No Auto-retry) |
| `CUSTOMER_ABANDONED`| `ABANDONMENT` | `TEMPORARY` | `MEDIUM` | `SEND_RECOVERY_MESSAGE` |
| `PAYMENT_PENDING` | `PENDING` | `TEMPORARY` | `HIGH` | `WAIT_AND_POLL` |
| `DUPLICATE_PAYMENT` | `DUPLICATE` | `PERMANENT` | `NONE` | `STOP` (Halt Billing) |
| `ORDER_CREATION_FAILED`| `MERCHANT` | `PERMANENT` | `LOW` | `ESCALATE` |
