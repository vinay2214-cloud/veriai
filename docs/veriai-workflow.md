# VeriAI — End-to-End Workflow
## docs/veriai-workflow.md

---

## User Journey 1: Jury / Demo Visitor (No Login)

```
1. Visitor opens https://veriai-eyxl.onrender.com
   → #/dashboard loads immediately (no login prompt)
   → Shows: Trust Score gauge, system status, recent demo audits

2. Visitor clicks "Run Audit" on a demo dataset
   → POST /api/demo/hiring_bias_demo/run-audit (public endpoint)
   → 8-step pipeline runs on synthetic hiring dataset
   → Results appear: Trust Score 51 (red), Bias 38%, Truth 62%

3. Visitor clicks "Auto-Correct"
   → POST /api/audit/{id}/correct (public for demo)
   → Bias drops to 4.2%, Truth rises to 94%, Score jumps to 89
   → Change log shows: 3 changes, each with reason + regulation

4. Visitor navigates to #/audit → SHAP waterfall chart visible
   Visitor navigates to #/reports → Score history visible
   Visitor navigates to #/review → Review queue visible
   ALL without login.
```

## User Journey 2: Uploading Your Own Dataset (Login Required)

```
1. User clicks "Upload Your Dataset" button
   → If not logged in: login modal appears
   → User logs in → receives JWT (stored in memory, NOT localStorage)

2. User selects CSV file
   → Client-side validation: type, size, filename (UX only)
   → File sent to POST /api/datasets/upload with Bearer token

3. Server security pipeline:
   a. JWT verified → get user_id
   b. validate_upload(): MIME type checked with libmagic (not Content-Type)
   c. File streamed for size check + SHA-256 hash
   d. If CSV/XLSX: pandas reads into DataFrame
   e. scan_for_injection(): dangerous patterns checked
   f. sanitize_dataframe(): formula chars prefixed with \t
   g. AES-256-GCM encryption: plaintext never touches disk
   h. Encrypted file written to /data/datasets/{user_id}/{dataset_id}/data.enc
   i. Metadata written to metadata.json (no file content)
   j. Audit event logged with chain hash
   k. Plaintext bytes wiped from memory (finally block)

4. User sees: dataset_id, filename, row count, upload timestamp
   (never sees file content again via API)

5. User runs audit on their uploaded dataset
   → POST /api/audit with dataset_id
   → Pipeline runs → results displayed
   → Results saved to audits table

6. User can delete their dataset
   → DELETE /api/datasets/{dataset_id}
   → 4-pass overwrite (DoD 5220.22-M) before unlink
   → Audit log archived (not deleted)
```

---

## Pipeline Step Detail

### Step 1: Bias Detection (~500ms)

```
Input:  pandas DataFrame with demographic columns
Process:
  - User defines protected_attr (e.g., "gender")
  - User defines privileged_group (e.g., "male")
  - AIF360 BinaryLabelDatasetMetric computes:
    · DPD = P(Ŷ=1|privileged) - P(Ŷ=1|unprivileged)
    · Equalized Odds Difference
    · Disparate Impact Ratio
    · Individual Fairness score
  - Proxy audit: flag features with correlation > 0.6 to protected_attr
  - SHAP coefficient method: explain which features drive bias
Output: BiasResult(dpd, equalized_odds, top_feature, shap_values)
```

### Step 2: Truth Verification (~1500ms with Gemini)

```
Input:  text content / LLM output to verify
Process:
  - Extract factual claims from text
  - FAISS retrieves top-k relevant chunks from knowledge base
  - Gemini 1.5 Pro evaluates (SEPARATE call from generator):
    · Context Relevance: does retrieved chunk address the claim?
    · Groundedness: is the claim supported by the chunk?
    · Answer Relevance: is the response helpful?
  - Truth Score = average of three component scores
Output: TruthResult(score, hallucinations, citations, sources)
```

### Step 5: Trust Scoring (instant)

```
Input:  BiasResult, TruthResult, use_case
Process:
  weights = INDUSTRY_PRESETS[use_case]  # from settings
  trust = weights.alpha * truth.score
        + weights.beta * (1 - bias.dpd)
        + weights.gamma * confidence
Output: TrustScore(value, level, components)
```

### Step 6: Auto-Correction (if score < 70)

```
For bias:
  - AIF360 Reweighing: adjust sample weights to reduce DPD
  - Reject Option Classification: adjust threshold for unprivileged group
  - Flag correlated proxy features for removal

For hallucinations:
  - Re-generate flagged sentence using Gemini with retrieved fact
  - Append source citation
  - Keep rest of response intact

Log every change:
  {feature_removed, reason, correlation, regulation}
  {claim_replaced, original, corrected, source_document, chunk_id}
```

---

## Knowledge Base Construction

The FAISS vector index is built from:

```
data/knowledge_base/
  who_essential_medicines.pdf    → WHO drug dosages, clinical guidelines
  ecoa_1691.pdf                  → Equal Credit Opportunity Act §1691
  eu_ai_act_articles.pdf         → EU AI Act Articles 5, 10, 13
  pubmed_reviews/                → PubMed systematic reviews
  india_it_rules_2021.pdf        → India IT Rules 2021
  dpdp_act_2023.pdf              → India DPDP Act 2023
```

Chunking strategy:
- Semantic chunking (not fixed-size character splits)
- Max 512 tokens per chunk, 50-token overlap
- Each chunk tagged: {source, page, section, date, domain}
- Gemini text-embedding-004 for embeddings
- Staleness alert: chunks older than 180 days flagged in UI

---

## Error Handling Pattern

```python
# All pipeline errors are caught and returned in standard format
# Pipeline never crashes the entire request — partial results allowed

try:
    bias_result = await detect_bias(df)
except BiasDetectionError as e:
    bias_result = BiasResult(error=str(e), score=None)
    logger.error("Bias detection failed: %s", e)

# Return partial results with error flags
return AuditResult(
    bias=bias_result,
    truth=truth_result,
    # ... other results
    warnings=["Bias detection failed — results may be incomplete"]
)
```