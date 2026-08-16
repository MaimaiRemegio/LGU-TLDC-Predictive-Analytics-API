"""
Generate a balanced synthetic dataset for Barangay Recommendation training.

OBJECTIVE:
Create a synthetic development dataset where barangay representation is balanced,
preventing the model from learning record-frequency bias instead of meaningful
patterns.

KEY DESIGN PRINCIPLES:
1. Equal barangay representation (each barangay gets similar number of records)
2. Course-specific barangay strengths (different barangays excel at different courses)
3. Realistic feature relationships maintained
4. Meaningful completion probability patterns
5. No single barangay dominates purely by record count
"""

import random
import json
from pathlib import Path

import pandas as pd

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load forecasting course list from model registry
MODEL_REGISTRY_PATH = PROJECT_ROOT / "trained_models" / "forecasting" / "metadata" / "model_registry.json"
with open(MODEL_REGISTRY_PATH, 'r') as f:
    registry = json.load(f)
    COURSES = sorted(registry['models'].keys())

OUTPUT_PATH = PROJECT_ROOT / "datasets" / "historical_training_balanced.csv"

# Target: 600 records per barangay × 22 barangays = 13,200 total (same as before)
RECORDS_PER_BARANGAY = 600
TOTAL_RECORDS = RECORDS_PER_BARANGAY * 22

print("=" * 70)
print("BALANCED SYNTHETIC DATASET GENERATOR")
print("=" * 70)
print(f"\nTarget: {RECORDS_PER_BARANGAY} records per barangay")
print(f"Total target: {TOTAL_RECORDS} records")
print(f"Courses: {len(COURSES)}")

# ---------------------------------------------------------------------------
# BARANGAY PROFILES WITH COURSE-SPECIFIC STRENGTHS
# ---------------------------------------------------------------------------

# Each barangay now has course-specific completion modifiers
# This creates meaningful variation where different barangays rank differently
# for different courses, instead of one barangay dominating everything.

BARANGAY_PROFILES = {
    # Urban barangays - generally higher completion, but vary by course type
    "Poblacion": {
        "tier": "urban",
        "base_completion": 0.12,
        "course_strengths": {
            "Computer Systems Servicing NC II": 0.10,
            "Bookkeeping NC II": 0.08,
            "Trainers Methodology Level I": 0.06,
            "Electronic Products Assembly and Servicing NC II": 0.05,
        },
        "course_weaknesses": {
            "HEO (Bulldozer) NC II": -0.08,
            "Organic Agriculture Production NC II": -0.05,
        },
    },
    
    "Abuanan": {
        "tier": "urban",
        "base_completion": 0.11,
        "course_strengths": {
            "Electrical Installation and Maintenance NC II": 0.08,
            "Carpentry NC II": 0.06,
            "Masonry NC II": 0.06,
            "Construction Painting NC II": 0.05,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.04,
            "Bookkeeping NC II": -0.03,
        },
    },
    
    "Atipuluan": {
        "tier": "urban",
        "base_completion": 0.10,
        "course_strengths": {
            "Cookery NC II": 0.09,
            "Bread and Pastry NC II": 0.08,
            "Driving NC II": 0.06,
        },
        "course_weaknesses": {
            "Machining NC I": -0.05,
            "Machining NC II": -0.05,
        },
    },
    
    "Lag-asan": {
        "tier": "urban",
        "base_completion": 0.10,
        "course_strengths": {
            "Driving NC II": 0.09,
            "Computer Systems Servicing NC II": 0.07,
            "Bookkeeping NC II": 0.06,
        },
        "course_weaknesses": {
            "Landscape Installation and Maintenance (Softscape)": -0.06,
        },
    },
    
    "Balingasag": {
        "tier": "urban",
        "base_completion": 0.09,
        "course_strengths": {
            "Shielded Metal Arc Welding NC II": 0.08,
            "Shielded Metal Arc Welding NC I": 0.07,
            "Machining NC II": 0.06,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.05,
        },
    },
    
    # Peri-urban barangays - moderate completion, specialized strengths
    "Taloc": {
        "tier": "peri-urban",
        "base_completion": 0.04,
        "course_strengths": {
            "Organic Agriculture Production NC II": 0.10,
            "Landscape Installation and Maintenance (Softscape)": 0.08,
            "Cookery NC II": 0.05,
        },
        "course_weaknesses": {
            "Electronic Products Assembly and Servicing NC II": -0.06,
        },
    },
    
    "Calumangan": {
        "tier": "peri-urban",
        "base_completion": 0.03,
        "course_strengths": {
            "Masonry NC I": 0.08,
            "Masonry NC II": 0.08,
            "Carpentry NC II": 0.06,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.05,
        },
    },
    
    "Dulao": {
        "tier": "peri-urban",
        "base_completion": 0.05,
        "course_strengths": {
            "HEO (Forklift) NC II": 0.09,
            "HEO (Wheel Loader) NC II": 0.08,
            "Driving NC II": 0.06,
        },
        "course_weaknesses": {
            "Bookkeeping NC II": -0.06,
        },
    },
    
    "Napoles": {
        "tier": "peri-urban",
        "base_completion": 0.02,
        "course_strengths": {
            "Bread and Pastry NC II": 0.09,
            "Cookery NC II": 0.07,
        },
        "course_weaknesses": {
            "HEO (Bulldozer) NC II": -0.05,
        },
    },
    
    "Bacong": {
        "tier": "peri-urban",
        "base_completion": 0.01,
        "course_strengths": {
            "Electrical Installation and Maintenance NC II": 0.08,
            "Electronic Products Assembly and Servicing NC II": 0.07,
        },
        "course_weaknesses": {
            "Organic Agriculture Production NC II": -0.04,
        },
    },
    
    "Alianza": {
        "tier": "peri-urban",
        "base_completion": 0.01,
        "course_strengths": {
            "Computer Systems Servicing NC II": 0.08,
            "Electronic Products Assembly and Servicing NC II": 0.06,
        },
        "course_weaknesses": {
            "Organic Agriculture Production NC II": -0.05,
        },
    },
    
    "Caridad": {
        "tier": "peri-urban",
        "base_completion": 0.00,
        "course_strengths": {
            "Landscape Installation and Maintenance (Softscape)": 0.10,
            "Organic Agriculture Production NC II": 0.08,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.06,
        },
    },
    
    "Pacol": {
        "tier": "peri-urban",
        "base_completion": -0.01,
        "course_strengths": {
            "Construction Painting NC II": 0.09,
            "Carpentry NC II": 0.07,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.05,
        },
    },
    
    "Malingin": {
        "tier": "peri-urban",
        "base_completion": -0.03,
        "course_strengths": {
            "Machining NC I": 0.10,
            "Machining NC II": 0.09,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.05,
        },
    },
    
    # Rural barangays - generally lower completion, but strong in specific courses
    "Ma-ao": {
        "tier": "rural",
        "base_completion": -0.11,
        "course_strengths": {
            "Organic Agriculture Production NC II": 0.12,
            "Landscape Installation and Maintenance (Softscape)": 0.10,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.08,
            "Bookkeeping NC II": -0.06,
        },
    },
    
    "Bagroy": {
        "tier": "rural",
        "base_completion": -0.13,
        "course_strengths": {
            "Organic Agriculture Production NC II": 0.11,
            "Carpentry NC II": 0.08,
        },
        "course_weaknesses": {
            "Computer Systems Servicing NC II": -0.07,
        },
    },
    
    "Tabunan": {
        "tier": "rural",
        "base_completion": -0.15,
        "course_strengths": {
            "HEO (Bulldozer) NC II": 0.12,
            "HEO (Hydraulic Excavator) NC II": 0.10,
        },
        "course_weaknesses": {
            "Bookkeeping NC II": -0.08,
        },
    },
    
    "Busay": {
        "tier": "rural",
        "base_completion": -0.17,
        "course_strengths": {
            "Shielded Metal Arc Welding NC I": 0.11,
            "Shielded Metal Arc Welding NC II": 0.10,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.08,
        },
    },
    
    "Binubuhan": {
        "tier": "rural",
        "base_completion": -0.18,
        "course_strengths": {
            "Masonry NC I": 0.12,
            "Masonry NC II": 0.11,
        },
        "course_weaknesses": {
            "Computer Systems Servicing NC II": -0.08,
        },
    },
    
    "Sagasa": {
        "tier": "rural",
        "base_completion": -0.19,
        "course_strengths": {
            "HEO (Wheel Loader) NC II": 0.13,
            "HEO (Forklift) NC II": 0.11,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.09,
        },
    },
    
    "Ilijan": {
        "tier": "rural",
        "base_completion": -0.21,
        "course_strengths": {
            "Driving NC II": 0.14,
        },
        "course_weaknesses": {
            "Trainers Methodology Level I": -0.10,
            "Bookkeeping NC II": -0.08,
        },
    },
    
    "Mailum": {
        "tier": "rural",
        "base_completion": -0.23,
        "course_strengths": {
            "Landscape Installation and Maintenance (Softscape)": 0.15,
            "Organic Agriculture Production NC II": 0.13,
        },
        "course_weaknesses": {
            "Computer Systems Servicing NC II": -0.10,
            "Trainers Methodology Level I": -0.08,
        },
    },
}

BARANGAYS = list(BARANGAY_PROFILES.keys())

# Education tier bias (same as before)
TIER_EDUCATION_BIAS = {
    "urban": {
        "Elementary Graduate": 0.6, "Junior High": 0.8, "Senior High": 1.0,
        "College Undergraduate": 1.3, "College Graduate": 1.5,
    },
    "peri-urban": {
        "Elementary Graduate": 1.0, "Junior High": 1.0, "Senior High": 1.0,
        "College Undergraduate": 1.0, "College Graduate": 1.0,
    },
    "rural": {
        "Elementary Graduate": 1.5, "Junior High": 1.3, "Senior High": 1.0,
        "College Undergraduate": 0.7, "College Graduate": 0.5,
    },
}

SEXES = ["Male", "Female"]
EMPLOYMENT_STATUSES = ["Unemployed", "Self-employed", "Wage Employed", "Underemployed"]
EDUCATIONAL_ATTAINMENTS = [
    "Elementary Graduate", "Junior High", "Senior High",
    "College Undergraduate", "College Graduate",
]

CURRENT_SKILLS = [
    "Cooking", "Baking", "Computer Literacy", "Carpentry", "Masonry",
    "Welding", "Electrical Repair", "Driving", "Bookkeeping", "Painting",
    "Electronics", "Heavy Equipment Operation", "Landscaping", "Machining",
    "Organic Farming", "Training Delivery",
]

DESIRED_CAREERS = [
    "Hospitality", "Construction", "ICT", "Agriculture", "Transportation", "Business",
    "Manufacturing", "Education",
]

LEARNER_CLASSIFICATIONS = [
    "New Entrant",
    "Returning Learner",
    "Experienced Worker",
    "Career Shifter",
]

# Skill to course mapping
SKILL_TO_COURSE = {
    "Bookkeeping": "Bookkeeping NC II",
    "Baking": "Bread and Pastry NC II",
    "Carpentry": "Carpentry NC II",
    "Computer Literacy": "Computer Systems Servicing NC II",
    "Painting": "Construction Painting NC II",
    "Cooking": "Cookery NC II",
    "Driving": "Driving NC II",
    "Electrical Repair": "Electrical Installation and Maintenance NC II",
    "Electronics": "Electronic Products Assembly and Servicing NC II",
    "Heavy Equipment Operation": "HEO (Forklift) NC II",
    "Landscaping": "Landscape Installation and Maintenance (Softscape)",
    "Machining": "Machining NC II",
    "Masonry": "Masonry NC II",
    "Organic Farming": "Organic Agriculture Production NC II",
    "Welding": "Shielded Metal Arc Welding NC II",
    "Training Delivery": "Trainers Methodology Level I",
}

SKILL_TO_CAREER = {
    "Bookkeeping": "Business",
    "Baking": "Hospitality",
    "Carpentry": "Construction",
    "Computer Literacy": "ICT",
    "Painting": "Construction",
    "Cooking": "Hospitality",
    "Driving": "Transportation",
    "Electrical Repair": "Construction",
    "Electronics": "Manufacturing",
    "Heavy Equipment Operation": "Construction",
    "Landscaping": "Agriculture",
    "Machining": "Manufacturing",
    "Masonry": "Construction",
    "Organic Farming": "Agriculture",
    "Welding": "Construction",
    "Training Delivery": "Education",
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
    "Manufacturing": [
        ("Senior High", 0.36), ("Junior High", 0.26), ("College Undergraduate", 0.16),
        ("Elementary Graduate", 0.14), ("College Graduate", 0.08),
    ],
    "Education": [
        ("College Graduate", 0.42), ("College Undergraduate", 0.34), ("Senior High", 0.16),
        ("Junior High", 0.06), ("Elementary Graduate", 0.02),
    ],
}

EDUCATION_TO_EMPLOYMENT = {
    "Elementary Graduate": [("Unemployed", 0.46), ("Underemployed", 0.36), ("Self-employed", 0.12), ("Wage Employed", 0.06)],
    "Junior High": [("Unemployed", 0.40), ("Underemployed", 0.34), ("Self-employed", 0.16), ("Wage Employed", 0.10)],
    "Senior High": [("Underemployed", 0.32), ("Unemployed", 0.28), ("Self-employed", 0.22), ("Wage Employed", 0.18)],
    "College Undergraduate": [("Self-employed", 0.28), ("Underemployed", 0.26), ("Wage Employed", 0.26), ("Unemployed", 0.20)],
    "College Graduate": [("Wage Employed", 0.38), ("Self-employed", 0.30), ("Underemployed", 0.20), ("Unemployed", 0.12)],
}

EDUCATION_AGE_RANGES = {
    "Elementary Graduate": (18, 40),
    "Junior High": (18, 42),
    "Senior High": (18, 45),
    "College Undergraduate": (19, 48),
    "College Graduate": (22, 55),
}

# Base course completion rates
COURSE_COMPLETION_BASE = {
    "Trainers Methodology Level I": 0.75,
    "Cookery NC II": 0.70,
    "Bookkeeping NC II": 0.69,
    "Bread and Pastry NC II": 0.68,
    "Computer Systems Servicing NC II": 0.66,
    "Driving NC II": 0.64,
    "Organic Agriculture Production NC II": 0.62,
    "Carpentry NC II": 0.60,
    "Landscape Installation and Maintenance (Softscape)": 0.59,
    "Masonry NC II": 0.57,
    "Masonry NC I": 0.56,
    "Construction Painting NC II": 0.55,
    "Electronic Products Assembly and Servicing NC II": 0.54,
    "Shielded Metal Arc Welding NC II": 0.53,
    "Shielded Metal Arc Welding NC I": 0.52,
    "Machining NC II": 0.51,
    "Electrical Installation and Maintenance NC II": 0.50,
    "Machining NC I": 0.49,
    "HEO (Forklift) NC II": 0.48,
    "HEO (Wheel Loader) NC II": 0.47,
    "HEO (Bulldozer) NC II": 0.46,
    "HEO (Hydraulic Excavator) NC II": 0.45,
}

EDUCATION_COMPLETION_ADJUSTMENT = {
    "Elementary Graduate": -0.12,
    "Junior High": -0.08,
    "Senior High": 0.00,
    "College Undergraduate": 0.08,
    "College Graduate": 0.12,
}

LEARNER_COMPLETION_ADJUSTMENT = {
    "Experienced Worker": 0.15,
    "Returning Learner": 0.08,
    "New Entrant": -0.05,
    "Career Shifter": -0.10,
}

EMPLOYMENT_COMPLETION_ADJUSTMENT = {
    "Wage Employed": 0.06,
    "Self-employed": 0.04,
    "Underemployed": 0.00,
    "Unemployed": -0.06,
}


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def weighted_choice(options: list[tuple[str, float]]) -> str:
    labels, weights = zip(*options)
    return random.choices(labels, weights=weights, k=1)[0]


def generate_current_skill() -> str:
    return weighted_choice([(skill, 1.0) for skill in CURRENT_SKILLS])


def generate_course_applied(current_skill: str) -> str:
    """Generate course with slight randomness to create variation."""
    if random.random() < 0.12:
        return random.choice(COURSES)
    
    base_course = SKILL_TO_COURSE[current_skill]
    
    # Handle courses with NC I/NC II variants
    if "Heavy Equipment Operation" in current_skill:
        heo_courses = ["HEO (Bulldozer) NC II", "HEO (Forklift) NC II", 
                       "HEO (Hydraulic Excavator) NC II", "HEO (Wheel Loader) NC II"]
        return random.choice(heo_courses)
    elif "Welding" in base_course:
        return random.choice(["Shielded Metal Arc Welding NC I", "Shielded Metal Arc Welding NC II"])
    elif "Machining" in base_course:
        return random.choice(["Machining NC I", "Machining NC II"])
    elif "Masonry" in base_course:
        return random.choice(["Masonry NC I", "Masonry NC II"])
    
    return base_course


def generate_desired_career(current_skill: str) -> str:
    if random.random() < 0.10:
        return random.choice(DESIRED_CAREERS)
    return SKILL_TO_CAREER[current_skill]


def generate_educational_attainment(desired_career: str, tier: str) -> str:
    base_distribution = CAREER_TO_EDUCATION[desired_career]
    tier_bias = TIER_EDUCATION_BIAS[tier]
    biased = [
        (level, weight * tier_bias[level]) for level, weight in base_distribution
    ]
    return weighted_choice(biased)


def generate_employment_status(educational_attainment: str) -> str:
    return weighted_choice(EDUCATION_TO_EMPLOYMENT[educational_attainment])


def generate_age(educational_attainment: str) -> int:
    low, high = EDUCATION_AGE_RANGES[educational_attainment]
    return random.randint(low, high)


def generate_sex(current_skill: str) -> str:
    trade_skills = {"Carpentry", "Masonry", "Welding", "Electrical Repair", "Driving", 
                    "Heavy Equipment Operation", "Machining", "Painting"}
    if current_skill in trade_skills:
        return weighted_choice([("Male", 0.84), ("Female", 0.16)])
    if current_skill in {"Cooking", "Baking"}:
        return weighted_choice([("Female", 0.58), ("Male", 0.42)])
    if current_skill in {"Bookkeeping", "Training Delivery"}:
        return weighted_choice([("Female", 0.52), ("Male", 0.48)])
    return random.choice(SEXES)


def is_skill_aligned(current_skill: str, course_applied: str) -> bool:
    """Check if the current skill aligns with the applied course."""
    base_course = SKILL_TO_COURSE.get(current_skill)
    if not base_course:
        return False
    
    if base_course == course_applied:
        return True
    
    # Check for NC I/NC II variants
    if "HEO" in course_applied and "Heavy Equipment Operation" in current_skill:
        return True
    if "Welding" in course_applied and "Welding" in current_skill:
        return True
    if "Machining" in course_applied and "Machining" in current_skill:
        return True
    if "Masonry" in course_applied and "Masonry" in current_skill:
        return True
    
    return False


def generate_learner_classification(
    current_skill: str,
    course_applied: str,
    educational_attainment: str,
    employment_status: str,
) -> str:
    skill_aligned = is_skill_aligned(current_skill, course_applied)

    if skill_aligned and employment_status in {"Wage Employed", "Self-employed"}:
        return weighted_choice([
            ("Experienced Worker", 0.55), ("Returning Learner", 0.25),
            ("New Entrant", 0.12), ("Career Shifter", 0.08),
        ])

    if not skill_aligned:
        return weighted_choice([
            ("Career Shifter", 0.50), ("New Entrant", 0.30),
            ("Returning Learner", 0.12), ("Experienced Worker", 0.08),
        ])

    if educational_attainment in {"Elementary Graduate", "Junior High"}:
        return weighted_choice([
            ("New Entrant", 0.52), ("Returning Learner", 0.22),
            ("Career Shifter", 0.16), ("Experienced Worker", 0.10),
        ])

    return weighted_choice([
        ("New Entrant", 0.40), ("Returning Learner", 0.28),
        ("Experienced Worker", 0.20), ("Career Shifter", 0.12),
    ])


def compute_graduation_probability(
    course_applied: str,
    age: int,
    educational_attainment: str,
    employment_status: str,
    current_skill: str,
    learner_classification: str,
    barangay: str,
) -> float:
    """
    Compute graduation probability using base course rate + feature adjustments
    + COURSE-SPECIFIC barangay modifier.
    
    This is the KEY change: barangays now have course-specific strengths/weaknesses,
    not just a global completion modifier.
    """
    probability = COURSE_COMPLETION_BASE[course_applied]
    probability += EDUCATION_COMPLETION_ADJUSTMENT[educational_attainment]
    probability += LEARNER_COMPLETION_ADJUSTMENT[learner_classification]
    probability += EMPLOYMENT_COMPLETION_ADJUSTMENT[employment_status]
    
    # Add base barangay completion modifier
    profile = BARANGAY_PROFILES[barangay]
    probability += profile["base_completion"]
    
    # Add course-specific barangay modifier (KEY CHANGE!)
    if course_applied in profile.get("course_strengths", {}):
        probability += profile["course_strengths"][course_applied]
    elif course_applied in profile.get("course_weaknesses", {}):
        probability += profile["course_weaknesses"][course_applied]
    
    # Skill alignment bonus
    if is_skill_aligned(current_skill, course_applied):
        probability += 0.10
    
    # Age adjustment
    if 22 <= age <= 40:
        probability += 0.05
    elif age <= 21:
        probability -= 0.05
    elif age >= 51:
        probability -= 0.08
    
    return max(0.15, min(0.95, probability))


def generate_training_outcome(
    course_applied: str,
    age: int,
    educational_attainment: str,
    employment_status: str,
    current_skill: str,
    learner_classification: str,
    barangay: str,
) -> str:
    graduate_probability = compute_graduation_probability(
        course_applied,
        age,
        educational_attainment,
        employment_status,
        current_skill,
        learner_classification,
        barangay,
    )
    return "Graduate" if random.random() < graduate_probability else "Dropout"


def generate_record(barangay: str) -> dict:
    """Generate a single training record for a specific barangay."""
    tier = BARANGAY_PROFILES[barangay]["tier"]
    current_skill = generate_current_skill()
    course_applied = generate_course_applied(current_skill)
    desired_career = generate_desired_career(current_skill)
    educational_attainment = generate_educational_attainment(desired_career, tier)
    employment_status = generate_employment_status(educational_attainment)
    age = generate_age(educational_attainment)
    sex = generate_sex(current_skill)
    learner_classification = generate_learner_classification(
        current_skill,
        course_applied,
        educational_attainment,
        employment_status,
    )
    training_outcome = generate_training_outcome(
        course_applied,
        age,
        educational_attainment,
        employment_status,
        current_skill,
        learner_classification,
        barangay,
    )

    return {
        "barangay": barangay,
        "course_applied": course_applied,
        "age": age,
        "sex": sex,
        "educational_attainment": educational_attainment,
        "employment_status": employment_status,
        "current_skill": current_skill,
        "desired_career": desired_career,
        "learner_classification": learner_classification,
        "training_outcome": training_outcome,
    }


def build_balanced_dataset() -> pd.DataFrame:
    """
    Build a balanced dataset where each barangay gets exactly the same
    number of records. This prevents frequency bias.
    """
    records = []
    
    for barangay in BARANGAYS:
        for _ in range(RECORDS_PER_BARANGAY):
            records.append(generate_record(barangay))
    
    # Shuffle to mix barangays
    random.shuffle(records)
    
    columns = [
        "barangay", "course_applied", "age", "sex", "educational_attainment",
        "employment_status", "current_skill", "desired_career",
        "learner_classification", "training_outcome",
    ]
    return pd.DataFrame(records)[columns]


def main() -> None:
    print("\nGenerating balanced synthetic dataset...")
    
    dataset = build_balanced_dataset()
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUTPUT_PATH, index=False)
    
    print(f"\n✅ Dataset generated: {OUTPUT_PATH}")
    print(f"   Total records: {len(dataset)}")
    print(f"   Records per barangay: {RECORDS_PER_BARANGAY}")
    
    # Quick validation
    print(f"\n📊 Quick Validation:")
    barangay_counts = dataset["barangay"].value_counts()
    print(f"   All barangays have {RECORDS_PER_BARANGAY} records: {all(c == RECORDS_PER_BARANGAY for c in barangay_counts)}")
    
    course_counts = dataset["course_applied"].value_counts()
    print(f"   Total courses: {len(course_counts)}")
    print(f"   All forecasting courses present: {len(course_counts) == len(COURSES)}")
    
    outcome_dist = dataset["training_outcome"].value_counts()
    print(f"\n   Training outcome distribution:")
    for outcome, count in outcome_dist.items():
        percentage = (count / len(dataset)) * 100
        print(f"     {outcome}: {count} ({percentage:.1f}%)")
    
    print("\n" + "=" * 70)
    print("SUCCESS: Balanced synthetic dataset generated")
    print("=" * 70)


if __name__ == "__main__":
    main()
