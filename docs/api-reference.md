# VeriAI — API Reference
## docs/api-reference.md

Base URL: https://veriai-eyxl.onrender.com

---

## Authentication

Protected endpoints require:
```
Authorization: Bearer <access_token>
```

Get a token:
```
POST /api/auth/login
Body: {"email": "...", "password": "..."}
Response: {"access_token": "...", "refresh_token": "..."}
```

---

## Public Endpoints (No Auth — Jury Can Access These)

### GET /api/demo/datasets
List all pre-loaded demo datasets.
```json
Response: [
  {
    "id": "hiring_bias_demo",
    "name": "Hiring Bias Demo",
    "description": "Synthetic hiring dataset showing 38% gender gap",
    "use_case": "HR / Hiring",
    "rows": 1000
  }
]
```

### POST /api/demo/{dataset_key}/run-audit
Run full 8-step pipeline on a demo dataset. Returns live results.
```json
Request:  {}
Response: { "trust_score": 51, "bias": {...}, "truth": {...}, ... }
```

### POST /api/audit
Run audit on provided data or dataset_id.
```json
Request:
{
  "dataset_id": "uuid",   // optional: if using uploaded dataset
  "text": "string",       // optional: if checking LLM output text
  "use_case": "hiring",   // hiring|healthcare|finance|general
  "depth": "standard"     // fast|standard|thorough
}
Response:
{
  "success": true,
  "data": {
    "audit_id": "uuid",
    "trust_score": 89,
    "trust_level": "acceptable",
    "bias": {
      "score": 0.042,
      "metric": "demographic_parity_difference",
      "top_feature": "zip_code",
      "all_metrics": { "dpd": 0.042, "equalized_odds": 0.038, "disparate_impact": 0.91 },
      "corrected": true
    },
    "truth": {
      "score": 0.94,
      "hallucinations_found": 0,
      "sources_cited": 2,
      "citations": [...]
    },
    "correction": {
      "applied": true,
      "changes_count": 3,
      "changes": [
        { "type": "feature_removed", "feature": "zip_code", "reason": "ECOA §1691" },
        { "type": "claim_replaced", "original": "...", "corrected": "...", "source": "WHO" }
      ]
    },
    "explanation": {
      "top_features": [
        { "feature": "zip_code", "contribution": 0.31, "direction": "positive_bias" }
      ],
      "shap_chart_data": {...}
    },
    "review_required": false,
    "review_id": null
  }
}
```

### GET /api/reports/demo
Get audit history for demo datasets.

### GET /api/review/queue
Get current human review queue (demo items).

### POST /api/review/{review_id}/decide
Submit a review decision.
```json
Request: { "decision": "approved|rejected|escalated", "notes": "..." }
```

---

## Protected Endpoints (JWT Required)

### POST /api/datasets/upload
Upload a private dataset for auditing.
```
Headers: Authorization: Bearer <token>
Body: multipart/form-data, field name: "file"
Allowed: .csv, .xlsx, .xls, .json (max 50MB)
```
```json
Response:
{
  "dataset_id": "uuid",
  "original_filename": "hiring_data.csv",
  "size_bytes": 245760,
  "sha256": "abc123...",
  "row_count": 1000,
  "column_count": 12,
  "uploaded_at": "2026-04-28T12:00:00Z",
  "retention_until": "2026-05-28T12:00:00Z"
}
```

### GET /api/datasets
List your uploaded datasets.
```
Headers: Authorization: Bearer <token>
Response: [ DatasetRecord, ... ]
```

### DELETE /api/datasets/{dataset_id}
Securely delete your dataset (4-pass overwrite).
```
Headers: Authorization: Bearer <token>
Response: { "deleted": true, "dataset_id": "uuid" }
```

### GET /api/datasets/{dataset_id}/audit-log
View tamper-evident audit log for your dataset.
```json
Response:
{
  "dataset_id": "uuid",
  "chain_integrity_verified": true,
  "entry_count": 5,
  "entries": [
    {
      "event_id": "uuid",
      "timestamp": "2026-04-28T12:00:00Z",
      "action": "upload",
      "result": "success",
      "ip_hash": "a3f2...",
      "entry_hash": "sha256..."
    }
  ]
}
```

---

## Error Responses

All errors follow this format:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "File type not allowed: application/x-executable",
    "detail": null
  }
}
```

HTTP status codes used:
- 200 — Success
- 400 — Bad request (invalid file content, injection detected)
- 401 — Unauthorized (missing or invalid JWT)
- 403 — Forbidden (not used — 404 returned instead for security)
- 404 — Not found (also used for unauthorized access to prevent enumeration)
- 410 — Gone (dataset expired per retention policy)
- 413 — Payload too large (file > 50MB)
- 415 — Unsupported media type (wrong file type)
- 429 — Too many requests (rate limit exceeded)
- 500 — Internal server error