"""
Generate a supervised learning dataset for the LGU-TLDC course recommendation system.

Features (X): applicant profile and context used to predict the training course.
Target (Y):   applied_course determined by weighted business rules — never random.
"""

import random
from collections import defaultdict
from pathlib import Path

import pandas as pd

random.seed(42)

RECORD_COUNT = 5000
MONTHS = list(range(1, 13))
PROFILE_NOISE_RATE = 0.10
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "datasets" / "training_data.csv"

# Supervised learning schema
FEATURE_COLUMNS = [
    "month",
    "barangay",
    "age",
    "gender",
    "employment_status",
    "educational_attainment",
    "current_skill",
    "work_experience",
    "desired_career",
]
TARGET_COLUMN = "applied_course"

BARANGAYS = [
    "Abuanan", "Alianza", "Atipuluan", "Bacong", "Bagroy", "Balingasag",
    "Binubuhan", "Busay", "Calumangan", "Caridad", "Dulao", "Ilijan",
    "Lag-asan", "Ma-ao", "Mailum", "Malingin", "Napoles", "Pacol",
    "Poblacion", "Sagasa", "Tabunan", "Taloc",
]

HIGH_DEMAND_BARANGAYS = {"Poblacion", "Busay", "Ma-ao", "Taloc"}
MEDIUM_DEMAND_BARANGAYS = {"Bagroy", "Bacong", "Mailum", "Caridad", "Dulao"}

GENDERS = ["Male", "Female"]
EMPLOYMENT_STATUSES = ["Unemployed", "Self-employed", "Wage Employed", "Underemployed"]
EDUCATIONAL_ATTAINMENTS = [
    "Elementary Graduate", "Junior High", "Senior High",
    "College Undergraduate", "College Graduate",
]

CURRENT_SKILLS = [
    "Cooking", "Baking", "Computer Literacy", "Carpentry", "Masonry",
    "Welding", "Electrical Repair", "Driving",
]

WORK_EXPERIENCES = [
    "Hospitality", "Construction", "ICT", "Transportation", "Agriculture",
    "Business", "Retail", "Manufacturing", "Government", "None",
]

DESIRED_CAREERS = [
    "Hospitality", "Construction", "ICT", "Agriculture", "Transportation", "Business",
]

COURSES = [
    "Cookery NC II",
    "Bread and Pastry NC II",
    "Computer Systems Servicing NC II",
    "Carpentry NC II",
    "Masonry NC II",
    "Shielded Metal Arc Welding NC I",
    "Driving NC II",
    "Electrical Installation and Maintenance NC II",
]

WORK_EXPERIENCE_WEIGHTS = [
    ("Hospitality", 0.16), ("Construction", 0.15), ("Agriculture", 0.13),
    ("Transportation", 0.11), ("Retail", 0.10), ("Business", 0.09),
    ("ICT", 0.08), ("Manufacturing", 0.07), ("Government", 0.06), ("None", 0.05),
]

EXPERIENCE_TO_SKILL = {
    "Hospitality": [("Cooking", 0.46), ("Baking", 0.42), ("Driving", 0.06), ("Computer Literacy", 0.06)],
    "Construction": [
        ("Carpentry", 0.28), ("Masonry", 0.26), ("Welding", 0.24), ("Electrical Repair", 0.22),
    ],
    "ICT": [("Computer Literacy", 0.88), ("Electrical Repair", 0.07), ("Driving", 0.05)],
    "Transportation": [("Driving", 0.86), ("Cooking", 0.05), ("Computer Literacy", 0.09)],
    "Agriculture": [("Driving", 0.30), ("Carpentry", 0.24), ("Masonry", 0.22), ("Cooking", 0.24)],
    "Business": [
        ("Cooking", 0.22), ("Baking", 0.18), ("Computer Literacy", 0.22),
        ("Driving", 0.20), ("Carpentry", 0.18),
    ],
    "Retail": [
        ("Cooking", 0.24), ("Baking", 0.22), ("Computer Literacy", 0.20),
        ("Driving", 0.18), ("Carpentry", 0.16),
    ],
    "Manufacturing": [
        ("Welding", 0.28), ("Electrical Repair", 0.26), ("Carpentry", 0.22),
        ("Masonry", 0.16), ("Computer Literacy", 0.08),
    ],
    "Government": [("Computer Literacy", 0.52), ("Driving", 0.28), ("Cooking", 0.12), ("Carpentry", 0.08)],
    "None": [
        ("Cooking", 0.16), ("Baking", 0.14), ("Computer Literacy", 0.14), ("Carpentry", 0.14),
        ("Masonry", 0.12), ("Welding", 0.10), ("Electrical Repair", 0.10), ("Driving", 0.10),
    ],
}

SKILL_TO_CAREER = {
    "Cooking": [("Hospitality", 0.86), ("Business", 0.08), ("Agriculture", 0.06)],
    "Baking": [("Hospitality", 0.86), ("Business", 0.09), ("Agriculture", 0.05)],
    "Computer Literacy": [("ICT", 0.88), ("Business", 0.12)],
    "Carpentry": [("Construction", 0.88), ("Agriculture", 0.07), ("Business", 0.05)],
    "Masonry": [("Construction", 0.88), ("Agriculture", 0.07), ("Business", 0.05)],
    "Welding": [("Construction", 0.90), ("Agriculture", 0.05), ("Business", 0.05)],
    "Electrical Repair": [("Construction", 0.86), ("ICT", 0.08), ("Business", 0.06)],
    "Driving": [("Transportation", 0.86), ("Agriculture", 0.08), ("Business", 0.06)],
}

CAREER_TO_EDUCATION = {
    "Hospitality": [
        ("Senior High", 0.38), ("Junior High", 0.32), ("College Undergraduate", 0.15),
        ("Elementary Graduate", 0.10), ("College Graduate", 0.05),
    ],
    "Construction": [
        ("Senior High", 0.34), ("Junior High", 0.30), ("Elementary Graduate", 0.18),
        ("College Undergraduate", 0.12), ("College Graduate", 0.06),
    ],
    "ICT": [
        ("College Undergraduate", 0.36), ("College Graduate", 0.30), ("Senior High", 0.22),
        ("Junior High", 0.08), ("Elementary Graduate", 0.04),
    ],
    "Agriculture": [
        ("Junior High", 0.30), ("Senior High", 0.28), ("Elementary Graduate", 0.22),
        ("College Undergraduate", 0.12), ("College Graduate", 0.08),
    ],
    "Transportation": [
        ("Senior High", 0.36), ("Junior High", 0.28), ("College Undergraduate", 0.18),
        ("Elementary Graduate", 0.12), ("College Graduate", 0.06),
    ],
    "Business": [
        ("Senior High", 0.28), ("College Undergraduate", 0.26), ("College Graduate", 0.18),
        ("Junior High", 0.18), ("Elementary Graduate", 0.10),
    ],
}

EDUCATION_TO_EMPLOYMENT = {
    "Elementary Graduate": [
        ("Unemployed", 0.46), ("Underemployed", 0.36), ("Self-employed", 0.12), ("Wage Employed", 0.06),
    ],
    "Junior High": [
        ("Unemployed", 0.40), ("Underemployed", 0.34), ("Self-employed", 0.16), ("Wage Employed", 0.10),
    ],
    "Senior High": [
        ("Underemployed", 0.32), ("Unemployed", 0.28), ("Self-employed", 0.22), ("Wage Employed", 0.18),
    ],
    "College Undergraduate": [
        ("Self-employed", 0.28), ("Underemployed", 0.26), ("Wage Employed", 0.26), ("Unemployed", 0.20),
    ],
    "College Graduate": [
        ("Wage Employed", 0.38), ("Self-employed", 0.30), ("Underemployed", 0.20), ("Unemployed", 0.12),
    ],
}

EDUCATION_AGE_RANGES = {
    "Elementary Graduate": (18, 40),
    "Junior High": (18, 42),
    "Senior High": (18, 45),
    "College Undergraduate": (19, 48),
    "College Graduate": (22, 55),
}

SKILL_GENDER_WEIGHTS = {
    "Carpentry": [("Male", 0.86), ("Female", 0.14)],
    "Masonry": [("Male", 0.88), ("Female", 0.12)],
    "Welding": [("Male", 0.90), ("Female", 0.10)],
    "Electrical Repair": [("Male", 0.82), ("Female", 0.18)],
    "Driving": [("Male", 0.78), ("Female", 0.22)],
    "Baking": [("Female", 0.62), ("Male", 0.38)],
    "Cooking": [("Female", 0.55), ("Male", 0.45)],
}

BARANGAY_WEIGHTS = [
    (
        barangay,
        3.0 if barangay in HIGH_DEMAND_BARANGAYS
        else 2.0 if barangay in MEDIUM_DEMAND_BARANGAYS
        else 1.0,
    )
    for barangay in BARANGAYS
]

# Business rules used exclusively to derive the target (Y)
SKILL_TO_COURSE_WEIGHTS = {
    "Cooking": {"Cookery NC II": 0.80, "Bread and Pastry NC II": 0.20},
    "Baking": {"Bread and Pastry NC II": 0.80, "Cookery NC II": 0.20},
    "Computer Literacy": {"Computer Systems Servicing NC II": 0.95, "Electrical Installation and Maintenance NC II": 0.05},
    "Carpentry": {"Carpentry NC II": 0.95, "Masonry NC II": 0.05},
    "Masonry": {"Masonry NC II": 0.95, "Carpentry NC II": 0.05},
    "Welding": {"Shielded Metal Arc Welding NC I": 0.95, "Carpentry NC II": 0.05},
    "Electrical Repair": {"Electrical Installation and Maintenance NC II": 0.95, "Computer Systems Servicing NC II": 0.05},
    "Driving": {"Driving NC II": 0.95, "Cookery NC II": 0.05},
}

EXPERIENCE_TO_COURSE_WEIGHTS = {
    "Hospitality": {"Cookery NC II": 0.55, "Bread and Pastry NC II": 0.45},
    "Construction": {
        "Carpentry NC II": 0.28, "Masonry NC II": 0.26,
        "Shielded Metal Arc Welding NC I": 0.24, "Electrical Installation and Maintenance NC II": 0.22,
    },
    "ICT": {"Computer Systems Servicing NC II": 1.0},
    "Transportation": {"Driving NC II": 1.0},
    "Agriculture": {"Driving NC II": 0.35, "Carpentry NC II": 0.25, "Masonry NC II": 0.20, "Cookery NC II": 0.20},
    "Manufacturing": {
        "Shielded Metal Arc Welding NC I": 0.30, "Electrical Installation and Maintenance NC II": 0.28,
        "Carpentry NC II": 0.22, "Masonry NC II": 0.20,
    },
}

CAREER_TO_COURSE_WEIGHTS = {
    "Hospitality": {"Cookery NC II": 0.55, "Bread and Pastry NC II": 0.45},
    "Construction": {
        "Carpentry NC II": 0.28, "Masonry NC II": 0.26,
        "Shielded Metal Arc Welding NC I": 0.24, "Electrical Installation and Maintenance NC II": 0.22,
    },
    "ICT": {"Computer Systems Servicing NC II": 1.0},
    "Transportation": {"Driving NC II": 1.0},
    "Agriculture": {"Driving NC II": 0.35, "Carpentry NC II": 0.25, "Masonry NC II": 0.20, "Cookery NC II": 0.20},
    "Business": {
        "Cookery NC II": 0.25, "Bread and Pastry NC II": 0.20,
        "Computer Systems Servicing NC II": 0.20, "Driving NC II": 0.20, "Carpentry NC II": 0.15,
    },
}

EDUCATION_TO_COURSE_WEIGHTS = {
    "Elementary Graduate": {
        "Cookery NC II": 0.25, "Carpentry NC II": 0.25, "Masonry NC II": 0.20,
        "Driving NC II": 0.15, "Shielded Metal Arc Welding NC I": 0.15,
    },
    "Junior High": {
        "Cookery NC II": 0.22, "Carpentry NC II": 0.22, "Masonry NC II": 0.20,
        "Driving NC II": 0.18, "Bread and Pastry NC II": 0.18,
    },
    "Senior High": {
        "Cookery NC II": 0.20, "Bread and Pastry NC II": 0.18, "Driving NC II": 0.18,
        "Carpentry NC II": 0.16, "Computer Systems Servicing NC II": 0.14, "Masonry NC II": 0.14,
    },
    "College Undergraduate": {
        "Computer Systems Servicing NC II": 0.40, "Electrical Installation and Maintenance NC II": 0.20,
        "Cookery NC II": 0.15, "Driving NC II": 0.15, "Bread and Pastry NC II": 0.10,
    },
    "College Graduate": {
        "Computer Systems Servicing NC II": 0.45, "Electrical Installation and Maintenance NC II": 0.25,
        "Driving NC II": 0.15, "Cookery NC II": 0.15,
    },
}

SKILL_NOISE_POOL = [(skill, 1.0) for skill in CURRENT_SKILLS]
CAREER_NOISE_POOL = [(career, 1.0) for career in DESIRED_CAREERS]
EDUCATION_NOISE_POOL = [(education, 1.0) for education in EDUCATIONAL_ATTAINMENTS]
EMPLOYMENT_NOISE_POOL = [(status, 1.0) for status in EMPLOYMENT_STATUSES]


def weighted_choice(options: list[tuple[str, float]]) -> str:
    labels, weights = zip(*options)
    return random.choices(labels, weights=weights, k=1)[0]


def choose_with_profile_noise(
    primary_options: list[tuple[str, float]],
    noise_options: list[tuple[str, float]],
) -> str:
    """Introduce limited variation in profile features only — never in the target."""
    if random.random() < PROFILE_NOISE_RATE:
        return weighted_choice(noise_options)
    return weighted_choice(primary_options)


def generate_work_experience() -> str:
    return weighted_choice(WORK_EXPERIENCE_WEIGHTS)


def generate_current_skill(work_experience: str) -> str:
    return choose_with_profile_noise(EXPERIENCE_TO_SKILL[work_experience], SKILL_NOISE_POOL)


def generate_desired_career(current_skill: str) -> str:
    return choose_with_profile_noise(SKILL_TO_CAREER[current_skill], CAREER_NOISE_POOL)


def generate_educational_attainment(desired_career: str) -> str:
    return choose_with_profile_noise(CAREER_TO_EDUCATION[desired_career], EDUCATION_NOISE_POOL)


def generate_employment_status(educational_attainment: str) -> str:
    return choose_with_profile_noise(
        EDUCATION_TO_EMPLOYMENT[educational_attainment],
        EMPLOYMENT_NOISE_POOL,
    )


def generate_age(educational_attainment: str, employment_status: str) -> int:
    low, high = EDUCATION_AGE_RANGES[educational_attainment]
    age = random.randint(low, high)

    if employment_status == "Unemployed" and educational_attainment in {"Senior High", "Junior High"}:
        age = max(18, age - random.randint(0, 4))

    if employment_status == "Wage Employed" and educational_attainment == "College Graduate":
        age = min(55, age + random.randint(0, 3))

    return age


def generate_gender(current_skill: str) -> str:
    if current_skill in SKILL_GENDER_WEIGHTS:
        return weighted_choice(SKILL_GENDER_WEIGHTS[current_skill])
    return weighted_choice([("Male", 0.50), ("Female", 0.50)])


def generate_barangay() -> str:
    if random.random() < PROFILE_NOISE_RATE:
        return random.choice(BARANGAYS)
    return weighted_choice(BARANGAY_WEIGHTS)


def generate_month() -> int:
    return random.choice(MONTHS)


def compute_course_weights(
    current_skill: str,
    work_experience: str,
    desired_career: str,
    educational_attainment: str,
) -> dict[str, float]:
    """
    Combine weighted business rules to score each TESDA course.
    Skill carries the strongest signal; experience, career, and education refine it.
    """
    weights: dict[str, float] = defaultdict(float)

    for course, weight in SKILL_TO_COURSE_WEIGHTS[current_skill].items():
        weights[course] += weight * 5.0

    for course, weight in EXPERIENCE_TO_COURSE_WEIGHTS.get(work_experience, {}).items():
        weights[course] += weight * 2.5

    for course, weight in CAREER_TO_COURSE_WEIGHTS.get(desired_career, {}).items():
        weights[course] += weight * 2.0

    for course, weight in EDUCATION_TO_COURSE_WEIGHTS.get(educational_attainment, {}).items():
        weights[course] += weight * 1.5

    return dict(weights)


def determine_applied_course(
    current_skill: str,
    work_experience: str,
    desired_career: str,
    educational_attainment: str,
) -> str:
    """
    Derive the target (Y) from applicant features using business rules.
    The highest-scoring course wins — no random course assignment.
    """
    course_weights = compute_course_weights(
        current_skill,
        work_experience,
        desired_career,
        educational_attainment,
    )
    return max(course_weights.items(), key=lambda item: item[1])[0]


def generate_features() -> dict:
    """Build the feature vector (X) through a logical applicant profile chain."""
    work_experience = generate_work_experience()
    current_skill = generate_current_skill(work_experience)
    desired_career = generate_desired_career(current_skill)
    educational_attainment = generate_educational_attainment(desired_career)
    employment_status = generate_employment_status(educational_attainment)
    age = generate_age(educational_attainment, employment_status)
    gender = generate_gender(current_skill)
    barangay = generate_barangay()
    month = generate_month()

    return {
        "month": month,
        "barangay": barangay,
        "age": age,
        "gender": gender,
        "employment_status": employment_status,
        "educational_attainment": educational_attainment,
        "current_skill": current_skill,
        "work_experience": work_experience,
        "desired_career": desired_career,
    }


def generate_record() -> dict:
    """Generate one supervised learning row: features (X) + target (Y)."""
    features = generate_features()

    applied_course = determine_applied_course(
        current_skill=features["current_skill"],
        work_experience=features["work_experience"],
        desired_career=features["desired_career"],
        educational_attainment=features["educational_attainment"],
    )

    return {**features, TARGET_COLUMN: applied_course}


def build_dataset() -> pd.DataFrame:
    """Assemble the full dataset with explicit X/Y column ordering."""
    records = [generate_record() for _ in range(RECORD_COUNT)]
    return pd.DataFrame(records)[FEATURE_COLUMNS + [TARGET_COLUMN]]


def save_dataset(dataset: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)


def main() -> None:
    dataset = build_dataset()
    save_dataset(dataset, OUTPUT_PATH)
    print("Dataset generated successfully.")
    print(f"Features (X): {FEATURE_COLUMNS}")
    print(f"Target   (Y): {TARGET_COLUMN}")
    print(f"Records: {len(dataset)}")


if __name__ == "__main__":
    main()
