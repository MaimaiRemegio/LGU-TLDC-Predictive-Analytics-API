"""
Generate synthetic dataset with STRONG course-specific barangay patterns.

KEY DESIGN: Each course has 1-3 barangays that are SIGNIFICANTLY better than others
for that specific course. This ensures different courses have different top barangays.

CRITICAL: Course × Barangay interaction is the PRIMARY completion driver, not a
secondary adjustment.
"""

import random
import json
from pathlib import Path

import pandas as pd

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load forecasting course list
MODEL_REGISTRY_PATH = PROJECT_ROOT / "trained_models" / "forecasting" / "metadata" / "model_registry.json"
with open(MODEL_REGISTRY_PATH, 'r') as f:
    registry = json.load(f)
    COURSES = sorted(registry['models'].keys())

OUTPUT_PATH = PROJECT_ROOT / "datasets" / "historical_training_course_specific.csv"

# Target: 600 records per barangay × 22 barangays = 13,200 total
RECORDS_PER_BARANGAY = 600
TOTAL_RECORDS = RECORDS_PER_BARANGAY * 22

print("=" * 70)
print("COURSE-SPECIFIC SYNTHETIC DATASET GENERATOR")
print("=" * 70)
print(f"\nTarget: {RECORDS_PER_BARANGAY} records per barangay")
print(f"Total target: {TOTAL_RECORDS} records")
print(f"Courses: {len(COURSES)}")

# ---------------------------------------------------------------------------
# COURSE-SPECIFIC BARANGAY EXCELLENCE
# ---------------------------------------------------------------------------

# Each course has 1-3 barangays that are EXCELLENT for that course
# These barangays get +0.35 to +0.45 completion probability (HUGE boost)
# This ensures the model learns strong course-specific patterns

COURSE_BARANGAY_EXCELLENCE = {
    "Bookkeeping NC II": {
        "Poblacion": 0.42,      # Urban, business center
        "Lag-asan": 0.38,       # Urban, educated population
        "Taloc": 0.35,          # Peri-urban, commerce
    },
    
    "Bread and Pastry NC II": {
        "Atipuluan": 0.45,      # Hospitality tradition
        "Napoles": 0.40,        # Food culture
        "Alianza": 0.36,        # Market access
    },
    
    "Carpentry NC II": {
        "Abuanan": 0.43,        # Construction industry presence
        "Calumangan": 0.39,     # Woodworking tradition
        "Pacol": 0.36,          # Trade skills
    },
    
    "Computer Systems Servicing NC II": {
        "Poblacion": 0.44,      # IT infrastructure
        "Alianza": 0.40,        # Tech access
        "Bacong": 0.37,         # Electronics industry
    },
    
    "Construction Painting NC II": {
        "Pacol": 0.43,          # Construction workers
        "Atipuluan": 0.39,      # Urban development
        "Napoles": 0.35,        # Building projects
    },
    
    "Cookery NC II": {
        "Atipuluan": 0.46,      # Restaurant culture
        "Taloc": 0.41,          # Food traditions
        "Napoles": 0.38,        # Culinary heritage
    },
    
    "Driving NC II": {
        "Ilijan": 0.47,         # Transportation hub
        "Dulao": 0.42,          # Logistics center
        "Lag-asan": 0.38,       # Vehicle access
    },
    
    "Electrical Installation and Maintenance NC II": {
        "Abuanan": 0.44,        # Industrial area
        "Bacong": 0.40,         # Manufacturing
        "Poblacion": 0.36,      # Infrastructure
    },
    
    "Electronic Products Assembly and Servicing NC II": {
        "Bacong": 0.45,         # Electronics industry
        "Alianza": 0.41,        # Tech manufacturing
        "Balingasag": 0.37,     # Industrial zone
    },
    
    "HEO (Bulldozer) NC II": {
        "Tabunan": 0.48,        # Mining/quarrying area
        "Sagasa": 0.43,         # Heavy equipment operations
        "Busay": 0.38,          # Construction projects
    },
    
    "HEO (Forklift) NC II": {
        "Dulao": 0.46,          # Warehousing hub
        "Sagasa": 0.41,         # Logistics operations
        "Poblacion": 0.36,      # Commercial district
    },
    
    "HEO (Hydraulic Excavator) NC II": {
        "Tabunan": 0.47,        # Excavation projects
        "Mailum": 0.42,         # Mining operations
        "Bagroy": 0.37,         # Infrastructure work
    },
    
    "HEO (Wheel Loader) NC II": {
        "Sagasa": 0.48,         # Quarry operations
        "Dulao": 0.43,          # Material handling
        "Tabunan": 0.38,        # Construction sites
    },
    
    "Landscape Installation and Maintenance (Softscape)": {
        "Caridad": 0.46,        # Agricultural tradition
        "Mailum": 0.42,         # Green spaces
        "Ma-ao": 0.38,          # Rural landscaping
    },
    
    "Machining NC I": {
        "Malingin": 0.45,       # Manufacturing industry
        "Balingasag": 0.40,     # Machine shops
        "Busay": 0.36,          # Metalworking
    },
    
    "Machining NC II": {
        "Malingin": 0.47,       # Advanced manufacturing
        "Balingasag": 0.42,     # Precision machining
        "Alianza": 0.37,        # Industrial skills
    },
    
    "Masonry NC I": {
        "Calumangan": 0.44,     # Construction tradition
        "Binubuhan": 0.40,      # Building skills
        "Mailum": 0.36,         # Rural construction
    },
    
    "Masonry NC II": {
        "Binubuhan": 0.46,      # Masonry heritage
        "Calumangan": 0.41,     # Construction expertise
        "Tabunan": 0.37,        # Building trades
    },
    
    "Organic Agriculture Production NC II": {
        "Ma-ao": 0.49,          # Agricultural heartland
        "Bagroy": 0.44,         # Farming community
        "Taloc": 0.40,          # Organic farming
    },
    
    "Shielded Metal Arc Welding NC I": {
        "Busay": 0.45,          # Welding shops
        "Balingasag": 0.41,     # Metal fabrication
        "Calumangan": 0.37,     # Construction welding
    },
    
    "Shielded Metal Arc Welding NC II": {
        "Balingasag": 0.48,     # Advanced welding
        "Busay": 0.43,          # Fabrication industry
        "Malingin": 0.38,       # Manufacturing welding
    },
    
    "Trainers Methodology Level I": {
        "Poblacion": 0.47,      # Education center
        "Abuanan": 0.42,        # Training institutions
        "Lag-asan": 0.38,       # Educational facilities
    },
}

# Base course difficulty (used when barangay has NO excellence for this course)
COURSE_BASE_DIFFICULTY = {
    "Trainers Methodology Level I": 0.50,
    "Cookery NC II": 0.48,
    "Bookkeeping NC II": 0.47,
    "Bread and Pastry NC II": 0.46,
    "Computer Systems Servicing NC II": 0.45,
    "Driving NC II": 0.44,
    "Organic Agriculture Production NC II": 0.43,
    "Carpentry NC II": 0.42,
    "Landscape Installation and Maintenance (Softscape)": 0.41,
    "Masonry NC II": 0.40,
    "Masonry NC I": 0.39,
    "Construction Painting NC II": 0.38,
    "Electronic Products Assembly and Servicing NC II": 0.37,
    "Shielded Metal Arc Welding NC II": 0.36,
    "Shielded Metal Arc Welding NC I": 0.35,
    "Machining NC II": 0.34,
    "Electrical Installation and Maintenance NC II": 0.33,
    "Machining NC I": 0.32,
    "HEO (Forklift) NC II": 0.31,
    "HEO (Wheel Loader) NC II": 0.30,
    "HEO (Bulldozer) NC II": 0.29,
    "HEO (Hydraulic Excavator) NC II": 0.28,
}

BARANGAYS = [
    "Poblacion", "Abuanan", "Atipuluan", "Lag-asan", "Balingasag",
    "Taloc", "Calumangan", "Dulao", "Napoles", "Bacong", "Alianza", "Caridad",
    "Pacol", "Malingin", "Ma-ao", "Bagroy", "Tabunan", "Busay", "Binubuhan",
    "Sagasa", "Ilijan", "Mailum",
]

BARANGAY_TIER = {
    "Poblacion": "urban", "Abuanan": "urban", "Atipuluan": "urban",
    "Lag-asan": "urban", "Balingasag": "urban",
    "Taloc": "peri-urban", "Calumangan": "peri-urban", "Dulao": "peri-urban",
    "Napoles": "peri-urban", "Bacong": "peri-urban", "Alianza": "peri-urban",
    "Caridad": "peri-urban", "Pacol": "peri-urban", "Malingin": "peri-urban",
    "Ma-ao": "rural", "Bagroy": "rural", "Tabunan": "rural", "Busay": "rural",
    "Binubuhan": "rural", "Sagasa": "rural", "Ilijan": "rural", "Mailum": "rural",
}

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

# Other factors (MUCH smaller adjustments than course-barangay excellence)
EDUCATION_COMPLETION_ADJUSTMENT = {
    "Elementary Graduate": -0.06,
    "Junior High": -0.04,
    "Senior High": 0.00,
    "College Undergraduate": 0.04,
    "College Graduate": 0.06,
}

LEARNER_COMPLETION_ADJUSTMENT = {
    "Experienced Worker": 0.08,
    "Returning Learner": 0.04,
    "New Entrant": -0.03,
    "Career Shifter": -0.05,
}

EMPLOYMENT_COMPLETION_ADJUSTMENT = {
    "Wage Employed": 0.03,
    "Self-employed": 0.02,
    "Underemployed": 0.00,
    "Unemployed": -0.03,
}


def weighted_choice(options: list[tuple[str, float]]) -> str:
    labels, weights = zip(*options)
    return random.choices(labels, weights=weights, k=1)[0]


def generate_current_skill() -> str:
    return weighted_choice([(skill, 1.0) for skill in CURRENT_SKILLS])


def generate_course_applied(current_skill: str) -> str:
    if random.random() < 0.12:
        return random.choice(COURSES)
    
    base_course = SKILL_TO_COURSE[current_skill]
    
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
    base_course = SKILL_TO_COURSE.get(current_skill)
    if not base_course:
        return False
    
    if base_course == course_applied:
        return True
    
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
    CRITICAL: Course × Barangay excellence is the PRIMARY driver.
    
    If barangay has excellence for this course: base = course_base + excellence (0.35-0.49)
    If barangay has NO excellence: base = course_base (0.28-0.50)
    
    Other factors are small adjustments (±0.03 to ±0.08).
    """
    
    # Start with course base difficulty
    probability = COURSE_BASE_DIFFICULTY[course_applied]
    
    # Add HUGE boost if this barangay excels at this course
    if barangay in COURSE_BARANGAY_EXCELLENCE[course_applied]:
        probability += COURSE_BARANGAY_EXCELLENCE[course_applied][barangay]
    
    # Small adjustments from other factors
    probability += EDUCATION_COMPLETION_ADJUSTMENT[educational_attainment]
    probability += LEARNER_COMPLETION_ADJUSTMENT[learner_classification]
    probability += EMPLOYMENT_COMPLETION_ADJUSTMENT[employment_status]
    
    # Skill alignment bonus
    if is_skill_aligned(current_skill, course_applied):
        probability += 0.05
    
    # Age adjustment
    if 22 <= age <= 40:
        probability += 0.03
    elif age <= 21:
        probability -= 0.03
    elif age >= 51:
        probability -= 0.04
    
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
    tier = BARANGAY_TIER[barangay]
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
    records = []
    
    for barangay in BARANGAYS:
        for _ in range(RECORDS_PER_BARANGAY):
            records.append(generate_record(barangay))
    
    random.shuffle(records)
    
    columns = [
        "barangay", "course_applied", "age", "sex", "educational_attainment",
        "employment_status", "current_skill", "desired_career",
        "learner_classification", "training_outcome",
    ]
    return pd.DataFrame(records)[columns]


def main() -> None:
    print("\nGenerating course-specific synthetic dataset...")
    print("Each course has 1-3 barangays with STRONG excellence (+0.35 to +0.49)")
    
    dataset = build_balanced_dataset()
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUTPUT_PATH, index=False)
    
    print(f"\n✅ Dataset generated: {OUTPUT_PATH}")
    print(f"   Total records: {len(dataset)}")
    
    # Validation
    barangay_counts = dataset["barangay"].value_counts()
    print(f"\n   All barangays have {RECORDS_PER_BARANGAY} records: {all(c == RECORDS_PER_BARANGAY for c in barangay_counts)}")
    
    course_counts = dataset["course_applied"].value_counts()
    print(f"   Total courses: {len(course_counts)}")
    
    outcome_dist = dataset["training_outcome"].value_counts()
    print(f"\n   Training outcome distribution:")
    for outcome, count in outcome_dist.items():
        percentage = (count / len(dataset)) * 100
        print(f"     {outcome}: {count} ({percentage:.1f}%)")
    
    print("\n" + "=" * 70)
    print("SUCCESS: Course-specific dataset generated")
    print("=" * 70)
    print("\n📌 KEY DESIGN: Course × Barangay excellence is PRIMARY completion driver")
    print("   Example: Poblacion excels at Bookkeeping (+0.42 boost)")
    print("           Atipuluan excels at Cookery (+0.46 boost)")
    print("           Different courses will have different top barangays!")


if __name__ == "__main__":
    main()
