"""Seed data module.
Populates the SQLite knowledge_base and creates a sample audit so the
dashboard is not empty on first launch.
"""
import sqlite3
import uuid
from .config import DB_PATH

KNOWLEDGE_ARTICLES = [
    {
        "title": "Artificial Intelligence Overview",
        "content": "Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals and humans. AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals. The term artificial intelligence was coined in 1956 by John McCarthy.",
        "source": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    },
    {
        "title": "Machine Learning Fairness",
        "content": "Fairness in machine learning refers to the various attempts at correcting algorithmic bias in automated decision processes based on machine learning models. Bias can arise from many sources including biased training data, biased feature selection, or biased labeling. Common fairness metrics include demographic parity, equalized odds, and calibration. Demographic parity requires that the probability of a positive prediction is the same across all groups.",
        "source": "https://en.wikipedia.org/wiki/Fairness_(machine_learning)",
    },
    {
        "title": "Hiring Discrimination Laws",
        "content": "Employment discrimination refers to discriminatory employment practices such as bias in hiring, promotion, job assignment, termination, and compensation based on race, gender, religion, or nationality. In the United States, Title VII of the Civil Rights Act of 1964 prohibits employment discrimination based on race, color, religion, sex, or national origin. The Equal Employment Opportunity Commission (EEOC) enforces federal anti-discrimination laws.",
        "source": "https://www.eeoc.gov/laws/statutes",
    },
    {
        "title": "SHAP Values Explained",
        "content": "SHAP (SHapley Additive exPlanations) is a method to explain individual predictions. SHAP values are based on Shapley values from cooperative game theory. Each feature value of the instance is a player in a game, and the prediction is the payout. SHAP values tell you how much each feature contributed to the prediction compared to the average prediction. A positive SHAP value means the feature increased the prediction, while a negative value means it decreased it.",
        "source": "https://christophm.github.io/interpretable-ml-book/shap.html",
    },
    {
        "title": "Algorithmic Bias in Criminal Justice",
        "content": "Algorithmic bias in criminal justice systems has been widely studied. The COMPAS recidivism algorithm was found to have higher false positive rates for Black defendants compared to white defendants by ProPublica in 2016. This raised significant concerns about the use of automated tools in sentencing and bail decisions. The debate highlights the tension between predictive accuracy and fairness across demographic groups.",
        "source": "https://www.propublica.org/article/machine-bias-risk-assessments-in-criminal-sentencing",
    },
    {
        "title": "EU AI Act and Compliance",
        "content": "The European Union AI Act is a proposed regulation that classifies AI systems by risk level: unacceptable, high, limited, and minimal risk. High-risk AI systems, including those used in employment, credit scoring, and law enforcement, must meet strict requirements including transparency, human oversight, and data quality. Providers must conduct conformity assessments and maintain technical documentation. The regulation aims to ensure AI systems are safe, transparent, and respect fundamental rights.",
        "source": "https://artificialintelligenceact.eu/",
    },
    {
        "title": "RAG: Retrieval Augmented Generation",
        "content": "Retrieval-Augmented Generation (RAG) is a technique that combines information retrieval with text generation. Instead of relying solely on the parameters of a large language model, RAG first retrieves relevant documents from a knowledge base and then uses them as context for generating responses. This approach reduces hallucinations, improves factual accuracy, and allows the model to cite sources. Common implementations use vector databases like FAISS or Pinecone for efficient similarity search.",
        "source": "https://arxiv.org/abs/2005.11401",
    },
    {
        "title": "Gender Bias in AI Recruiting",
        "content": "Amazon scrapped an AI recruiting tool in 2018 after discovering it was biased against women. The system was trained on resumes submitted over a 10-year period, most of which came from men, reflecting the male dominance in the tech industry. The AI penalized resumes that included the word 'women' and downgraded graduates of all-women's colleges. This case demonstrates how historical data can perpetuate and amplify existing biases in automated systems.",
        "source": "https://www.reuters.com/article/us-amazon-com-jobs-automation-insight-idUSKCN1MK08G",
    },
    {
        "title": "Trust Score Methodology",
        "content": "Trust scoring in AI systems typically combines multiple dimensions: factual accuracy (truth), freedom from bias (fairness), model confidence (calibration), demographic consistency (cluster fairness), and statistical stability (distribution analysis). A weighted combination of these factors produces an overall trust score. Common weights prioritize truth and fairness as the most critical dimensions, with confidence and statistical measures as supporting factors.",
        "source": "https://arxiv.org/abs/2301.00001",
    },
    {
        "title": "Data Distribution and Model Fairness",
        "content": "The distribution of training data significantly impacts model fairness. Skewed distributions can lead to models that perform well on majority groups but poorly on minority groups. Key statistical measures include mean, standard deviation, skewness, and kurtosis. A distribution with high skewness may indicate overrepresentation of certain groups. Distribution drift between training and production data can also introduce bias over time.",
        "source": "https://proceedings.mlr.press/v81/buolamwini18a.html",
    },
]

import os
import json

SAMPLE_AUDIT = {
    "id": "demo-001",
    "input": "Evaluate hiring algorithm for gender bias in tech company recruitment pipeline",
    "bias_score": 0.38,
    "truth_score": 0.72,
    "trust_score": 0.68,
    "corrected": "Applied demographic parity correction. Adjusted gender feature weight from 0.45 to 0.15.",
    "report_json": json.dumps({
        "audit_id": "demo-001",
        "audit_type": "dataset",
        "input_text": "Evaluate hiring algorithm for gender bias in tech company recruitment pipeline",
        "bias": {
            "bias_score": 0.38,
            "demographic_parity": 0.38,
            "equal_opportunity": 0.38,
            "p_y_given_male": 0.72,
            "p_y_given_female": 0.34
        },
        "truth": {
            "truth_score": 0.72
        },
        "trust_score": 0.68,
        "elapsed_seconds": 2.85
    })
}


def seed_database():
    """Populate the knowledge base and insert a sample audit.
    Safe to call multiple times — uses INSERT OR IGNORE.
    Only run in local SQLite dev/test/demo mode, never on production PostgreSQL.
    """
    if os.getenv("DATABASE_URL"):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Seed knowledge base
    for article in KNOWLEDGE_ARTICLES:
        cursor.execute(
            "SELECT COUNT(*) FROM knowledge_base WHERE title = ?",
            (article["title"],),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO knowledge_base (title, content, source) VALUES (?, ?, ?)",
                (article["title"], article["content"], article["source"]),
            )

    # Seed sample audit
    cursor.execute("SELECT COUNT(*) FROM audits WHERE id = ?", (SAMPLE_AUDIT["id"],))
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO audits (id, input, bias_score, truth_score, trust_score, corrected, report_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (SAMPLE_AUDIT["id"], SAMPLE_AUDIT["input"], SAMPLE_AUDIT["bias_score"],
             SAMPLE_AUDIT["truth_score"], SAMPLE_AUDIT["trust_score"], SAMPLE_AUDIT["corrected"], SAMPLE_AUDIT["report_json"]),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")
