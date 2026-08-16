"""
Generate synthetic historical trainee records for the completion prediction model.

EXPANDED VERSION: Includes all 21 courses supported by the forecasting system,
plus "Bread and Pastry NC II" (22 courses total).

Each record reflects realistic relationships between applicant profiles
and training outcomes (Graduate vs Dropout).
"""

import random
from pathlib import Path

import pandas as pd

random.seed(42)

RECORD_COUNT = 13200  # ~600 records per course (22 courses)
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "datasets" / "historical_training_expanded.csv"

# Per-barangay attributes that drive realistic, learnable relationships:
#   tier          -> workforce/education skew (urban areas skew to higher education)
#   participation -> relative applicant volume (weighted sampling, non-uniform)
#   completion    -> additive graduation-probability modifier (accessibility, support,
#                    proximity to the training center). Higher = more completions,
#                    lower = more dropouts.
BARANGAY_PROFILES = {
    "Poblacion":   {"tier": "urban",      "participation": 2.0, "completion": 0.14},
    "Abuanan":     {"tier": "urban",      "participation": 2.3, "completion": 0.13},
    "Atipuluan":   {"tier": "urban",      "participation": 2.2, "completion": 0.12},
    "Lag-asan":    {"tier": "urban",      "participation": 1.4, "completion": 0.12},
    "Balingasag":  {"tier": "urban",      "participation": 1.3, "completion": 0.11},
    "Taloc":       {"tier": "peri-urban", "participation": 1.8, "completion": 0.05},
    "Calumangan":  {"tier": "peri-urban", "participation": 1.4, "completion": 0.04},
    "Dulao":       {"tier": "peri-urban", "participation": 1.3, "completion": 0.06},
    "Napoles":     {"tier": "peri-urban", "participation": 1.0, "completion": 0.03},
    "Bacong":      {"tier": "peri-urban", "participation": 1.1, "completion": 0.02},
    "Alianza":     {"tier": "peri-urban", "participation": 1.1, "completion": 0.02},
    "Caridad":     {"tier": "peri-urban", "participation": 1.0, "completion": 0.00},
    "Pacol":       {"tier": "peri-urban", "participation": 0.9, "completion": -0.02},
    "Malingin":    {"tier": "peri-urban", "participation": 0.9, "completion": -0.04},
    "Ma-ao":       {"tier": "rural",      "participation": 1.2, "completion": -0.12},
    "Bagroy":      {"tier": "rural",      "participation": 0.7, "completion": -0.14},
    "Tabunan":     {"tier": "rural",      "participation": 0.6, "completion": -0.16},
    "Busay":       {"tier": "rural",      "participation": 0.6, "completion": -0.18},
    "Binubuhan":   {"tier": "rural",      "participation": 0.5, "completion": -0.19},
    "Sagasa":      {"tier": "rural",      "participation": 0.5, "completion": -0.20},
    "Ilijan":      {"tier": "rural",      "participation": 0.5, "completion": -0.22},
    "Mailum":      {"tier": "rural",      "participation": 0.6, "completion": -0.24},
}

BARANGAYS = list(BARANGAY_PROFILES)

# Education distribution multipliers by barangay tier. Urban barangays skew toward
# higher educational attainment; rural barangays skew lower. Applied on top of the
# career-driven base distribution, then renormalized by weighted_choice.
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

# EXPANDED: Added skills for new courses
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

# EXPANDED: All 21 forecasting courses + Bread and Pastry NC II (22 total)
COURSES = [
    "Bookkeeping NC II",
    "Bread and Pastry NC II",
    "Carpentry NC II",
    "Computer Systems Servicing NC II",
    "Construction Painting NC II",
    "Cookery NC II",
    "Driving NC II",
    "Electrical Installation and Maintenance NC II",
    "Electronic Products Assembly and Servicing NC II",
    "HEO (Bulldozer) NC II",
    "HEO (Forklift) NC II",
    "HEO (Hydraulic Excavator) NC II",
    "HEO (Wheel Loader) NC II",
    "Landscape Installation and Maintenance (Softscape)",
    "Machining NC I",
    "Machining NC II",
    "Masonry NC I",
    "Masonry NC II",
    "Organic Agriculture Production NC II",
    "Shielded Metal Arc Welding NC I",
    "Shielded Metal Arc Welding NC II",
    "Trainers Methodology Level I",
]

LEARNER_CLASSIFICATIONS = [
    "New Entrant",
    "Returning Learner",
    "Experienced Worker",
    "Career Shifter",
]

# EXPANDED: Skill-to-course mapping for all courses
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
    "Heavy Equipment Operation": "HEO (Forklift) NC II",  # Default HEO mapping
    "Landscaping": "Landscape Installation and Maintenance (Softscape)",
    "Machining": "Machining NC II",  # Default to NC II
    "Masonry": "Masonry NC II",  # Default to NC II
    "Organic Farming": "Organic Agriculture Production NC II",
    "Welding": "Shielded Metal Arc Welding NC II",  # Default to NC II
    "Training Delivery": "Trainers Methodology Level I",
}

# EXPANDED: Skill-to-career mapping
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

# EXPANDED: Base completion rates for all 22 courses
# Base completion rates are kept in a mid range (not near 1.0) so that the
# barangay completion modifier is not lost to the [0.15, 0.95] clamp.
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


def weighted_choice(options: list[tuple[str, float]]) -> str:
    labels, weights = zip(*options)
    return random.choices(labels, weights=weights, k=1)[0]


def generate_current_skill() -> str:
    return weighted_choice([(skill, 1.0) for skill in CURRENT_SKILLS])


def generate_course_applied(current_skill: str) -> str:
    """
    Generate the applied course, with preference for skill-aligned courses.
    For skills that could map to multiple courses (HEO, Welding, Machining, Masonry),
    randomly select between NC I and NC II variants.
    """
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
    
    # Exact match
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


def generate_barangay() -> str:
    weights = [BARANGAY_PROFILES[barangay]["participation"] for barangay in BARANGAYS]
    return random.choices(BARANGAYS, weights=weights, k=1)[0]


def compute_graduation_probability(
    course_applied: str,
    age: int,
    educational_attainment: str,
    employment_status: str,
    current_skill: str,
    learner_classification: str,
    barangay: str,
) -> float:
    probability = COURSE_COMPLETION_BASE[course_applied]
    probability += EDUCATION_COMPLETION_ADJUSTMENT[educational_attainment]
    probability += LEARNER_COMPLETION_ADJUSTMENT[learner_classification]
    probability += EMPLOYMENT_COMPLETION_ADJUSTMENT[employment_status]
    probability += BARANGAY_PROFILES[barangay]["completion"]

    if is_skill_aligned(current_skill, course_applied):
        probability += 0.10

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


def generate_record() -> dict:
    barangay = generate_barangay()
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


def build_dataset() -> pd.DataFrame:
    records = [generate_record() for _ in range(RECORD_COUNT)]
    columns = [
        "barangay", "course_applied", "age", "sex", "educational_attainment",
        "employment_status", "current_skill", "desired_career",
        "learner_classification", "training_outcome",
    ]
    return pd.DataFrame(records)[columns]


def main() -> None:
    print("=" * 70)
    print("EXPANDED HISTORICAL TRAINING DATASET GENERATOR")
    print("=" * 70)
    print(f"\nTarget records: {RECORD_COUNT}")
    print(f"Courses: {len(COURSES)}")
    print(f"Barangays: {len(BARANGAYS)}")
    print("\nGenerating records...")
    
    dataset = build_dataset()
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUTPUT_PATH, index=False)
    
    print(f"\nDataset generated: {OUTPUT_PATH}")
    print(f"Total records: {len(dataset)}")
    print(f"\nTraining outcome distribution:")
    outcome_dist = dataset["training_outcome"].value_counts()
    for outcome, count in outcome_dist.items():
        percentage = (count / len(dataset)) * 100
        print(f"  {outcome}: {count} ({percentage:.1f}%)")
    
    print(f"\nCourse distribution:")
    course_dist = dataset["course_applied"].value_counts().sort_values(ascending=False)
    for course, count in course_dist.head(10).items():
        print(f"  {course}: {count}")
    print(f"  ... ({len(course_dist)} courses total)")
    
    print(f"\nBarangay distribution:")
    barangay_dist = dataset["barangay"].value_counts().sort_values(ascending=False)
    for barangay, count in barangay_dist.head(5).items():
        print(f"  {barangay}: {count}")
    print(f"  ... ({len(barangay_dist)} barangays total)")
    
    print("\n" + "=" * 70)
    print("SUCCESS: Expanded training dataset generated")
    print("=" * 70)


if __name__ == "__main__":
    main()
