# VeriAI – AI Trust Auditor Platform

## 🚀 Overview

VeriAI is an end-to-end AI trust auditing platform that evaluates model outputs and datasets for fairness risk and factual reliability before they reach end users. It combines bias detection, hallucination/truth verification, explainability, and a composite trust score to make AI behavior measurable, transparent, and actionable.

Built for high-impact domains like hiring, healthcare, finance, and public services, VeriAI helps teams detect issues early, explain root causes, apply corrective actions, and escalate low-trust cases for human review.

## ✨ Key Features

- **Bias Detection**: Fairness checks including Demographic Parity and Equalized Odds/Opportunity metrics across protected groups.
- **Truth Verification**: RAG-style similarity validation using a local knowledge base with TF-IDF + FAISS retrieval.
- **Explainability**: SHAP-first explanations with robust fallback feature-importance paths.
- **Trust Scoring System**: Weighted composite score from truth, bias, confidence, and stability signals.
- **Dashboard & Visualization**: Interactive UI for audit metrics, trends, review queues, and model insights.
- **LLM Output Auditing**: Prompt/response auditing endpoint with claim-level hallucination checks and trust delta tracking.
- **Compliance Export**: Export audit reports/artifacts (JSON/PDF) for governance and compliance workflows.

## 🏗 Architecture

VeriAI follows a modular full-stack architecture:

- **Backend (FastAPI, Python)**: API orchestration, audit pipeline execution, scoring, correction, review workflows, and report endpoints.
- **Frontend (HTML/CSS/JavaScript SPA)**: Dashboard, audit submission, report views, settings, and review actions.
- **Database (SQLite + aiosqlite)**: Persistent storage for audits, knowledge base records, feedback, and settings.
- **ML Components**: scikit-learn-based fairness analysis, clustering (KMeans), distribution analysis, and explainability integrations.

## ⚙️ Tech Stack

- FastAPI
- Python
- scikit-learn
- pandas / numpy
- FAISS
- JavaScript frontend (HTML/CSS/Vanilla JS SPA)
- SQLite / aiosqlite
- SHAP

## 🧠 How It Works

1. **Input data**: Accepts text, prompt/LLM output pairs, or structured dataset payloads.
2. **Bias analysis**: Computes fairness metrics and subgroup bias patterns.
3. **Truth verification**: Retrieves supporting evidence from a local knowledge base and scores groundedness.
4. **Scoring**: Combines fairness, truth, confidence, and stability into a single Trust Score.
5. **Dashboard output**: Publishes results to visual dashboards, report views, and human-review queues.

## 🖥️ Local Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
python -m http.server 3000
```

Backend API docs are available at `http://127.0.0.1:8000/docs` when the server is running.

## 🌐 Live Demo

https://veriai-eyxl.onrender.com

## 📂 Project Structure

```text
veriai/
|-- backend/               # FastAPI app, routes, services, models, DB logic
|-- frontend/              # Static SPA (HTML/CSS/JS), pages, client logic
|-- docker-compose.yml     # Local multi-service container setup
|-- Dockerfile             # App container definition
`-- README.md
```


