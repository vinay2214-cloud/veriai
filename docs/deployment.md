# VeriAI — Deployment Guide
## docs/deployment.md

Platform: Render.com
Live URL: https://veriai-eyxl.onrender.com

---

## Environment Variables (set in Render Dashboard)

Navigate: Your Service → Environment → Add Environment Variable

### Required (must be set before first deploy)
```
VERIAI_MASTER_KEY    = [run: python scripts/generate_secrets.py]
JWT_SECRET           = [run: python scripts/generate_secrets.py]
DB_ENCRYPTION_KEY    = [run: python scripts/generate_secrets.py]
```

### Deployment config
```
ALLOWED_ORIGINS      = https://veriai-eyxl.onrender.com
DATASETS_DIR         = /data/datasets
RETENTION_DAYS       = 30
MAX_FILE_SIZE_MB     = 50
DEMO_MODE            = true
```

### Google Cloud (already configured)
```
GEMINI_API_KEY       = [existing value]
VERTEX_AI_PROJECT    = [existing value]
VERTEX_AI_LOCATION   = [existing value]
```

---

## Persistent Disk (Required)

Without this, encrypted datasets are lost on every deploy.

Render Dashboard → Your Service → Disks → Add Disk:
```
Name:        veriai-datasets
Mount Path:  /data
Size:        5 GB
```

This disk persists across deploys and restarts.

---

## Build & Start Commands

In Render Dashboard → Settings:
```
Build Command:  pip install -r requirements.txt
Start Command:  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

---

## Generating Secrets (one time only)

```bash
python scripts/generate_secrets.py
```

Copy the output and paste each value into Render environment variables.
WARNING: Running this again generates new keys. Existing encrypted
datasets become permanently unreadable. Only run on fresh setup.

---

## Post-Deploy Verification

After every deploy, verify:

```bash
# 1. Dashboard loads without login
curl -s -o /dev/null -w "%{http_code}" https://veriai-eyxl.onrender.com

# 2. Security headers present
curl -I https://veriai-eyxl.onrender.com | grep -E "X-Frame|HSTS|Content-Security"

# 3. Upload without auth → 401
curl -X POST https://veriai-eyxl.onrender.com/api/datasets/upload \
     -F "file=@test.csv" -w "%{http_code}"
# Expected: 401

# 4. Demo audit works publicly
curl -X POST https://veriai-eyxl.onrender.com/api/demo/hiring_bias_demo/run-audit \
     -w "%{http_code}"
# Expected: 200
```

---

## Troubleshooting

### App won't start
Check logs for: "VeriAI security configuration is invalid"
Solution: Set all required environment variables in Render dashboard.

### "Dataset not found" after redeploy
The persistent disk is not configured, or DATASETS_DIR is wrong.
Solution: Add the disk (Mount Path: /data) in Render dashboard.

### CORS errors in browser
ALLOWED_ORIGINS does not match the actual frontend URL.
Solution: Set ALLOWED_ORIGINS to exact URL with no trailing slash.

### Gemini API errors
GEMINI_API_KEY is not set or has expired.
Solution: Update the key in Render environment variables.