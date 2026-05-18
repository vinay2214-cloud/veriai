"""
Real synthetic datasets for demonstrating bias detection.
These produce measurable, real bias metrics (not mocked numbers).
"""
import pandas as pd
import numpy as np


def generate_hiring_bias_dataset(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic hiring dataset with controlled gender bias.
    Typical outcome rates are around 65% (male) vs 42% (female).
    Use for: bias detection demo, Trust Score demo.
    """
    rng = np.random.default_rng(seed)

    gender = rng.choice(["male", "female"], size=n)
    age = rng.integers(22, 60, size=n)
    education = rng.choice(
        ["bachelor", "master", "phd", "associate"],
        size=n,
        p=[0.45, 0.30, 0.15, 0.10],
    )
    experience = rng.integers(0, 20, size=n)
    zip_code = rng.choice(["90210", "10001", "30301", "60601", "77001"], size=n)

    base_prob = 0.5
    gender_penalty = np.where(gender == "female", -0.22, 0)
    edu_bonus = np.where(education == "phd", 0.15, np.where(education == "master", 0.08, 0))
    exp_bonus = experience * 0.009

    hire_prob = np.clip(base_prob + gender_penalty + edu_bonus + exp_bonus, 0, 1)
    hired = rng.random(size=n) < hire_prob

    return pd.DataFrame(
        {
            "gender": gender,
            "age": age,
            "education": education,
            "years_experience": experience,
            "zip_code": zip_code,
            "hired": hired.astype(int),
        }
    )


def generate_lending_bias_dataset(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic lending dataset with racial/income proxy bias.
    Neighborhood score correlates with race proxy.
    """
    rng = np.random.default_rng(seed)

    race = rng.choice(["white", "black", "hispanic", "asian"], size=n, p=[0.60, 0.15, 0.15, 0.10])
    income = rng.normal(60000, 25000, size=n).clip(15000, 300000)
    credit_score = rng.normal(680, 80, size=n).clip(300, 850)

    neighborhood_score = np.where(
        race == "white",
        rng.normal(7.2, 1.0, size=n),
        np.where(
            race == "asian",
            rng.normal(6.8, 1.0, size=n),
            np.where(race == "hispanic", rng.normal(5.4, 1.2, size=n), rng.normal(4.9, 1.3, size=n)),
        ),
    ).clip(1, 10)

    approve_prob = (
        (credit_score - 300) / 550 * 0.35
        + (income - 15000) / 285000 * 0.25
        + neighborhood_score / 10 * 0.40
    ).clip(0, 1)
    approved = rng.random(size=n) < approve_prob

    return pd.DataFrame(
        {
            "race": race,
            "income": income.astype(int),
            "credit_score": credit_score.astype(int),
            "neighborhood_score": neighborhood_score.round(1),
            "loan_approved": approved.astype(int),
        }
    )


def save_demo_csvs(output_dir: str = "data/demo") -> None:
    """Save demo CSVs for uploading to the app."""
    import os

    os.makedirs(output_dir, exist_ok=True)

    hiring = generate_hiring_bias_dataset()
    hiring.to_csv(f"{output_dir}/hiring_bias_demo.csv", index=False)

    lending = generate_lending_bias_dataset()
    lending.to_csv(f"{output_dir}/lending_bias_demo.csv", index=False)


if __name__ == "__main__":
    save_demo_csvs()
