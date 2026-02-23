def communication_score(answers):
    """
    answers: list of 5 integers each in {0,5,10,15,20}
    returns total (0-100)
    """
    if not isinstance(answers, (list, tuple)):
        return 0
    return max(0, min(100, sum(int(x) for x in answers)))


def coding_questionnaire_score(answers):
    """
    Compute questionnaire score (max 90) from 5 inputs with different maxima:
    1. Preferred language: up to 20
    2. DSA familiarity: up to 15
    3. Practice frequency: up to 20
    4. Competitive participation: up to 20
    5. Debugging confidence: up to 15

    We expect answers to be numeric in the appropriate ranges (0..max).
    """
    if not isinstance(answers, (list, tuple)):
        return 0
    maxes = [20, 15, 20, 20, 15]  # Total max = 90
    score = 0
    for i, a in enumerate(answers[:5]):
        try:
            v = float(a)
        except Exception:
            v = 0
        # clamp
        v = max(0, min(maxes[i], v))
        score += v
    return int(round(score))


def coding_score_from_questionnaire(q_score, projects, skills):
    """
    Apply resume-based boost and cap to 100.
    boost = min(10, (projects_count * 3) + skills_count)
    final_coding_score = min(100, questionnaire_score + resume_boost)
    """
    try:
        boost = min(10, int(projects) * 3 + int(skills))
    except Exception:
        boost = 0
    final = min(100, int(round(float(q_score))) + int(round(boost)))
    return final


def resume_score(features):
    """
    Compute resume score from parsed features using weighted logic.
    Updated weights:
      skills -> 2 pts each
      projects -> 3 pts each
      internships -> 2 pts each
      certifications -> 4 pts each
      hackathons/events/workshops -> 2 pts each
      ats_score -> bonus points based on score (>60: +5, >40: +3)
      experience_index -> 2 pts each

    The raw total is normalized to a 0-100 scale.
    """
    weights = {
        "number_of_skills": 2,
        "num_projects": 3,
        "num_internships": 2,
        "num_certifications": 4,
        "hackathons": 2,
        "workshops": 2,
        "events": 2,
        "experience_index": 2,
    }
    total = 0
    for k, w in weights.items():
        total += features.get(k, 0) * w

    # Add ATS score bonus
    ats_score = features.get('ats_score', 0)
    if ats_score > 60:
        total += 5
    elif ats_score > 40:
        total += 3

    # Return raw score (0-100 scale, capped at 100)
    score = min(100, total)
    return score
