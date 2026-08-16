"""Test the course-specific model to verify diverse barangay recommendations."""

import json
import joblib
from collections import Counter

print("=" * 70)
print("COURSE-SPECIFIC MODEL TEST")
print("=" * 70)

# Load course-specific model
model = joblib.load('trained_models/completion_model_v3_course_specific.pkl')
encoders = joblib.load('trained_models/completion_encoders_v3_course_specific.pkl')
with open('trained_models/completion_model_metrics_v3_course_specific.json', 'r') as f:
    metrics = json.load(f)

print("\n✅ Model loaded successfully")
print(f"   Version: v3_course_specific")
print(f"   Accuracy: {metrics['accuracy']:.4f}")
print(f"   ROC-AUC: {metrics['roc_auc']:.4f}")

# Test standard applicant profile across all courses
test_applicant = {
    'course_applied': None,
    'age': 25,
    'sex': 'Male',
    'educational_attainment': 'College Undergraduate',
    'employment_status': 'Unemployed',
    'current_skill': 'Computer Literacy',
    'desired_career': 'ICT',
    'learner_classification': 'New Entrant',
}

courses = sorted(encoders['course_applied'].classes_)
barangays = sorted(encoders['barangay'].classes_)

feature_columns = [
    'barangay', 'course_applied', 'age', 'sex', 'educational_attainment',
    'employment_status', 'current_skill', 'desired_career', 'learner_classification'
]

print(f"\n📊 Testing {len(courses)} courses with standard applicant profile")
print(f"   Barangays: {len(barangays)}")

top_recommendations = []

print(f"\n{'Course':<55s} {'Top Barangay':>15s} {'Prob':>8s}")
print("-" * 70)

for course in courses:
    test_applicant['course_applied'] = course
    
    # Test all barangays
    probs = []
    for barangay in barangays:
        test_profile = {**test_applicant, 'barangay': barangay}
        
        # Encode features
        encoded = []
        for col in feature_columns:
            if col == 'age':
                encoded.append(test_profile[col])
            else:
                encoded.append(encoders[col].transform([test_profile[col]])[0])
        
        prob = model.predict_proba([encoded])[0]
        graduate_index = list(encoders['training_outcome'].classes_).index('Graduate')
        prob_graduate = prob[list(model.classes_).index(graduate_index)]
        probs.append((barangay, prob_graduate))
    
    # Get top recommendation
    top = max(probs, key=lambda x: x[1])
    top_recommendations.append(top[0])
    
    print(f"{course:<55s} {top[0]:>15s} {top[1]*100:>7.1f}%")

# Analyze diversity
print("\n" + "=" * 70)
print("DIVERSITY ANALYSIS")
print("=" * 70)

top_counts = Counter(top_recommendations)

print(f"\nTop barangay distribution:")
for barangay, count in top_counts.most_common(10):
    percentage = (count / len(courses)) * 100
    print(f"  {barangay:20s}: {count:2d}/{len(courses)} courses ({percentage:5.1f}%)")

unique_top = len(top_counts)
print(f"\n✅ Unique barangays ranked #1: {unique_top}/{len(barangays)} ({unique_top/len(barangays)*100:.1f}%)")

if unique_top >= len(courses) * 0.5:
    print(f"✅ SUCCESS: {unique_top} different barangays rank #1 for {len(courses)} courses")
    print(f"   HIGH DIVERSITY achieved!")
elif unique_top >= len(courses) * 0.3:
    print(f"✅ GOOD: {unique_top} different barangays rank #1")
    print(f"   MODERATE DIVERSITY achieved")
else:
    print(f"⚠️  LIMITED DIVERSITY: Only {unique_top} different barangays rank #1")

# Check if Abuanan/Atipuluan still dominate
abuanan_count = top_counts.get('Abuanan', 0)
atipuluan_count = top_counts.get('Atipuluan', 0)

print(f"\n📍 High-frequency barangay check:")
print(f"   Atipuluan: {atipuluan_count}/{len(courses)} courses ({atipuluan_count/len(courses)*100:.1f}%)")
print(f"   Abuanan:   {abuanan_count}/{len(courses)} courses ({abuanan_count/len(courses)*100:.1f}%)")

if abuanan_count < len(courses) * 0.3 and atipuluan_count < len(courses) * 0.3:
    print(f"   ✅ No single barangay dominates (< 30% threshold)")
else:
    print(f"   ⚠️  One or more barangays still dominate")

# Gini coefficient
def gini_coefficient(counts):
    sorted_counts = sorted(counts.values())
    n = len(sorted_counts)
    index = range(1, n + 1)
    return (2 * sum(i * c for i, c in zip(index, sorted_counts))) / (n * sum(sorted_counts)) - (n + 1) / n

gini = gini_coefficient(top_counts)
print(f"\nGini Coefficient: {gini:.4f} (0=perfectly equal, 1=concentrated)")

print("\n" + "=" * 70)
print("FINAL VERDICT")
print("=" * 70)

if unique_top >= 10 and gini < 0.5:
    print("\n🎉 EXCELLENT: Model shows high diversity in recommendations")
    print(f"   - {unique_top} different barangays rank #1")
    print(f"   - Low concentration (Gini: {gini:.4f})")
    print(f"   - SUCCESS: Different courses have different top barangays!")
elif unique_top >= 5:
    print("\n✅ GOOD: Model shows reasonable diversity")
    print(f"   - {unique_top} different barangays rank #1")
    print(f"   - Gini: {gini:.4f}")
else:
    print("\n⚠️  LIMITED: Model diversity could be improved")
    print(f"   - Only {unique_top} different barangays rank #1")

print("\n" + "=" * 70)
