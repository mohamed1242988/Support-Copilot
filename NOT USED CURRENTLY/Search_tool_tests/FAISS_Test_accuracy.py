from knowledge.embeddings import create_embedding
from knowledge.vector_store import VectorStore

# ============================================================
# 1. DOCUMENTS (50 items)
# ============================================================

documents = [
    # QuickBooks sync related (high relevance)
    "QuickBooks payment sync issue",
    "QuickBooks data sync error",
    "QuickBooks ledger update delay",
    "QuickBooks API connection timeout",
    "QuickBooks transaction push failure",
    "QuickBooks customer record mismatch",
    "QuickBooks batch sync problem",
    "QuickBooks invoice sync failure",
    "QuickBooks reconciliation sync mismatch",
    "QuickBooks vendor sync conflict",

    # Accounting integration (medium relevance)
    "Accounting platform integration bug",
    "Financial system API failure",
    "Ledger data import issue",
    "Accounting workflow automation glitch",
    "Finance backend service crash",
    "Transaction pipeline mapping bug",
    "Reporting integration sync delay",
    "ERP accounting module failure",
    "Financial dataset merge problem",
    "Statement parsing accuracy issue",

    # Financial sync (medium relevance)
    "Financial data sync mismatch",
    "Bank feed import failure",
    "Ledger balance sync conflict",
    "Transaction record duplication error",
    "Reconciliation workflow mismatch",
    "Financial dataset merge issue",
    "Data pipeline validation error",
    "Statement parsing accuracy problem",
    "Balance sheet update delay",
    "Financial report export failure",

    # Soft negatives (loosely related)
    "Invoice template formatting issue",
    "Customer profile update error",
    "Vendor record import failure",
    "Payment gateway connection timeout",
    "Billing cycle configuration bug",
    "Subscription renewal processing glitch",
    "Tax calculation module failure",
    "Payroll schedule update problem",
    "Expense category mapping error",
    "Budget planning dashboard issue",

    # Hard negatives (similar wording, unrelated)
    "CRM contact import failure",
    "Inventory stock update delay",
    "Sales dashboard widget malfunction",
    "Marketing email template glitch",
    "Support ticket routing error",
    "Warehouse shipment tracking bug",
    "Product catalog sync mismatch",
    "Order fulfillment workflow issue",
    "Shipping label generation error",
    "Customer loyalty points glitch"
]

# ============================================================
# 2. QUERIES (10 items)
# ============================================================

queries = [
    "QuickBooks sync failure",
    "Accounting integration error",
    "Financial data mismatch",
    "Ledger import failure",
    "Transaction sync problem",
    "Bank feed sync issue",
    "Reconciliation workflow bug",
    "Financial reporting glitch",
    "API connection timeout",
    "Customer record mismatch"
]

# ============================================================
# 3. EXPECTED TOP-K RESULTS (ground truth)
# ============================================================

expected_results = {
    "QuickBooks sync failure": [
        "QuickBooks invoice sync failure",
        "QuickBooks payment sync issue",
        "QuickBooks data sync error",
        "QuickBooks batch sync problem",
        "QuickBooks transaction push failure"
    ],
    "Accounting integration error": [
        "Accounting platform integration bug",
        "ERP accounting module failure",
        "Financial system API failure",
        "Reporting integration sync delay",
        "Accounting workflow automation glitch"
    ],
    "Financial data mismatch": [
        "Financial data sync mismatch",
        "Financial dataset merge issue",
        "Ledger balance sync conflict",
        "Transaction record duplication error",
        "Reconciliation workflow mismatch"
    ],
    "Ledger import failure": [
        "Ledger data import issue",
        "Ledger balance sync conflict",
        "QuickBooks ledger update delay",
        "Financial dataset merge problem",
        "Statement parsing accuracy issue"
    ],
    "Transaction sync problem": [
        "QuickBooks transaction push failure",
        "QuickBooks data sync error",
        "QuickBooks batch sync problem",
        "Transaction pipeline mapping bug",
        "Transaction record duplication error"
    ],
    "Bank feed sync issue": [
        "Bank feed import failure",
        "Financial data sync mismatch",
        "Ledger balance sync conflict",
        "Reconciliation workflow mismatch",
        "Financial dataset merge issue"
    ],
    "Reconciliation workflow bug": [
        "Reconciliation workflow mismatch",
        "Financial data sync mismatch",
        "Financial dataset merge issue",
        "Ledger balance sync conflict",
        "Statement parsing accuracy problem"
    ],
    "Financial reporting glitch": [
        "Financial report export failure",
        "Reporting integration sync delay",
        "Statement parsing accuracy issue",
        "Balance sheet update delay",
        "Financial dataset merge problem"
    ],
    "API connection timeout": [
        "QuickBooks API connection timeout",
        "Payment gateway connection timeout",
        "Financial system API failure",
        "Transaction pipeline mapping bug",
        "Finance backend service crash"
    ],
    "Customer record mismatch": [
        "QuickBooks customer record mismatch",
        "Customer profile update error",
        "Vendor record import failure",
        "Expense category mapping error",
        "Invoice template formatting issue"
    ]
}

# ============================================================
# 4. BUILD VECTOR STORE
# ============================================================

embeddings = [create_embedding(doc) for doc in documents]

store = VectorStore(dimension=768)
store.add(embeddings, documents)

# ============================================================
# 5. EVALUATION METRICS
# ============================================================

def precision_at_k(results, expected):
    return len([r for r in results if r in expected]) / len(results)

def recall_at_k(results, expected):
    return len([r for r in results if r in expected]) / len(expected)

def mrr(results, expected):
    for idx, r in enumerate(results):
        if r in expected:
            return 1.0 / (idx + 1)
    return 0.0

def ndcg(results, expected):
    dcg = 0.0
    for i, r in enumerate(results):
        if r in expected:
            dcg += 1.0 / (i + 1)
    ideal_dcg = sum(1.0 / (i + 1) for i in range(len(expected)))
    return dcg / ideal_dcg

# ============================================================
# 6. RUN TESTS
# ============================================================

for query in queries:
    print("\n==============================")
    print("QUERY:", query)
    print("==============================")

    query_embedding = create_embedding(query, is_query=True)
    results = store.search(query_embedding, top_k=5)
    results = [r["document"] for r in results]  # extract document strings

    print("Results:", results)
    print("Expected:", expected_results[query])

    p = precision_at_k(results, expected_results[query])
    r = recall_at_k(results, expected_results[query])
    m = mrr(results, expected_results[query])
    n = ndcg(results, expected_results[query])

    print(f"Precision@5: {p:.3f}")
    print(f"Recall@5:    {r:.3f}")
    print(f"MRR:         {m:.3f}")
    print(f"nDCG:        {n:.3f}")
