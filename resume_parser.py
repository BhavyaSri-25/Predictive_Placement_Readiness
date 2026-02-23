import pdfplumber
from docx import Document
import re
from skills import SKILLS, SKILL_HIERARCHIES
from sklearn.feature_extraction.text import TfidfVectorizer
import math

# Soft skills to ignore when counting technical skills
SOFT_SKILLS = set([
    'communication', 'teamwork', 'leadership', 'management', 'organisational', 'presentation', 'presentation skills', 'collaboration'
])

ISSUERS = ['coursera', 'nptel', 'aws', 'google', 'microsoft', 'edx', 'udemy', 'ibm', 'oracle', 'citrix']

# Common compact variants mapping -> normalized spaced forms
COMPACT_MAP = {
    r'(?i)\bvscode\b': 'vs code',
    r'(?i)\bvisualstudiocode\b': 'visual studio code',
    r'(?i)\bpowerbi\b': 'power bi',
    r'(?i)\bmsoffice\b': 'ms office',
    r'(?i)\bmicrosoftoffice\b': 'microsoft office'
}


def extract_text(file_path):
    text = ""
    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += "\n" + page_text
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        text = "\n".join(p.text for p in doc.paragraphs)
    # Only convert to lowercase, preserve ALL original spacing
    return text.lower()


# Stop sections that indicate end of skills section
STOP_SECTIONS = {
    "projects",
    "experience", 
    "work experience",
    "education",
    "internship",
    "internships",
    "certifications",
    "achievements",
    "summary",
    "profile",
    "objective"
}

def normalize_text(text):
    """Normalize text for consistent skill matching - preserves spaces between words"""
    if not text:
        return ""
    # Convert to lowercase
    normalized = text.lower()
    # Replace punctuation with spaces (NOT empty strings) to preserve word boundaries
    normalized = re.sub(r'[,./;:()\[\]{}"\'-]+', ' ', normalized)
    # Collapse multiple spaces into single space
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def extract_skills_from_section(text):
    """
    ATS-style skills extraction that stops at non-skill sections.
    Counts skills only until reaching Projects, Experience, Education, etc.
    """
    if not text:
        return {'skills_found': [], 'count': 0}
    
    # Split text into lines for line-by-line processing
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    skills_found = set()
    skills_text = ""
    
    # Process lines until stop heading is found
    for line in lines:
        line_lower = line.lower().strip()
        
        # Check if line is a stop heading - must be exact match or start of line
        is_stop_heading = False
        for heading in STOP_SECTIONS:
            # Only match if it's the exact heading or starts the line followed by colon
            if (line_lower == heading or 
                line_lower == heading + ':' or
                (line_lower.startswith(heading + ':') and len(line_lower.split()) <= 2)):
                is_stop_heading = True
                break
        
        if is_stop_heading:
            break
            
        # Accumulate text for skill extraction
        skills_text += " " + line
    
    # Remove parenthetical/bracketed content (ignore skills listed inside brackets)
    skills_text = re.sub(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}', ' ', skills_text)

    # Expand common compact variants to spaced forms so matching catches them
    for pat, repl in COMPACT_MAP.items():
        skills_text = re.sub(pat, repl, skills_text)

    # Extract skills from accumulated text using existing logic
    text_normalized = normalize_text(skills_text)
    
    # Debug: print the skills section text
    print(f"DEBUG: Skills section text: '{text_normalized}'")
    print(f"DEBUG: Looking for these multi-word skills: oracle database, ms office, vs code, power bi, rest apis, unit testing, version control workflows")
    
    # Sort skills by length (longest first) to match longer phrases before shorter ones
    sorted_skills = sorted(SKILLS, key=len, reverse=True)
    
    # Check each skill in the database
    for skill in sorted_skills:
        skill_normalized = normalize_text(skill)
        
        # Simple substring matching with space padding for word boundaries
        padded_text = ' ' + text_normalized + ' '
        padded_skill = ' ' + skill_normalized + ' '
        
        if padded_skill in padded_text:
            skills_found.add(skill)
            print(f"DEBUG: Found skill: {skill}")
        elif skill_normalized in ['oracle database', 'ms office', 'vs code', 'power bi', 'rest apis', 'unit testing', 'version control workflows']:
            print(f"DEBUG: MISSED skill '{skill}' - looking for '{padded_skill}' in '{padded_text[:100]}...'")
    
    # Apply skill hierarchy rules to avoid double counting
    final_skills = set(skills_found)
    
    for parent_skill, child_skills in SKILL_HIERARCHIES.items():
        if any(s.lower() == parent_skill.lower() for s in skills_found):
            # Remove child skills if parent is present
            for child in child_skills:
                final_skills = {s for s in final_skills if s.lower() != child.lower()}
    
    # Filter out soft skills but keep technical ones
    technical_skills = {s for s in final_skills if s.lower() not in SOFT_SKILLS}
    
    # Debug: print found skills
    print(f"DEBUG: Found {len(technical_skills)} skills: {sorted(list(technical_skills))}")
    
    return {
        'skills_found': sorted(list(technical_skills)),
        'count': len(technical_skills)
    }


def extract_resume_features(text):
    # normalize text and split into non-empty lines - PRESERVE ORIGINAL SPACING
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Extract skills from dedicated Skills section
    skills_found = set()
    skills_text = ""
    in_skills_section = False
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # Check if we're entering skills section - strict heading detection
        if not in_skills_section:
            # Remove extra spaces and check for exact skills headings
            clean_line = re.sub(r'\s+', ' ', line_lower).strip()
            
            # Valid skills headings (exact match or with colon)
            valid_headings = [
                'skills', 'technical skills', 'key skills', 'core skills', 
                'skill set', 'technologies', 'technical expertise'
            ]
            
            # Check if line is exactly a skills heading or ends with colon
            is_skills_heading = (
                clean_line in valid_headings or
                any(clean_line == heading + ':' for heading in valid_headings)
            )
            
            if is_skills_heading:
                in_skills_section = True
                print(f"DEBUG: Found skills section start: '{line}'")
                continue
            
        # Check if we're leaving skills section
        if in_skills_section and any(stop in line_lower for stop in ['project', 'experience', 'education', 'internship', 'certification', 'achievement']):
            print(f"DEBUG: Skills section ended at: '{line}'")
            break
            
        # Collect skills section text - USE ORIGINAL LINE, NOT LOWERCASED
        if in_skills_section:
            skills_text += " " + line
    
    # Normalize and search for skills using a punctuation-tolerant matcher
    if skills_text:
        # Remove parenthetical/bracketed content from the skills section
        skills_text = re.sub(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}', ' ', skills_text)

        # Normalize the accumulated skills section to replace punctuation
        # with spaces and collapse multiple spaces. This increases robustness
        # for inputs like "VS-Code", "VS.Code", "Power-BI" etc.
        text_for_matching = normalize_text(skills_text)
        print(f"DEBUG: Skills section text (normalized): '{text_for_matching}'")
        
        sorted_skills = sorted(SKILLS, key=len, reverse=True)
        
        for skill in sorted_skills:
            # Normalize the skill phrase the same way as the text
            skill_normalized = normalize_text(skill)
            if not skill_normalized:
                continue

            # Use word boundary matching on normalized text for accuracy
            if re.search(r'\b' + re.escape(skill_normalized) + r'\b', text_for_matching):
                if skill.lower() not in SOFT_SKILLS:
                    skills_found.add(skill)
                    print(f"DEBUG: Found skill: {skill}")
    
    # Project detection - count only actual project titles
    projects = set()
    in_project_section = False
    
    print(f"DEBUG: Starting project detection for resume with {len(lines)} lines")
    
    for i, ln in enumerate(lines):
        ln_clean = ln.strip().lower()
        
        # Check if we're entering a project section
        if re.match(r'^(projects?|academic projects?|project experience|personal projects?)\s*:?\s*$', ln_clean):
            in_project_section = True
            print(f"DEBUG: Found project section at line {i}: '{ln}'")
            continue
            
        # Check if we're leaving project section (new heading)
        if in_project_section and re.match(r'^(experience|work experience|education|skills?|certifications?|achievements?|internships?)\s*:?\s*$', ln_clean):
            in_project_section = False
            print(f"DEBUG: Left project section at line {i}: '{ln}'")
            continue
            
        # If in project section, look for project titles only
        if in_project_section:
            print(f"DEBUG: Processing line {i} in project section: '{ln}'")
            
            # Skip empty lines, bullet points, descriptions, and tech stacks
            if (ln.strip() and 
                not re.match(r'^[\u2022\-\*•]\s*', ln) and 
                not re.search(r'\b(built|developed|created|implemented|designed|integrated|enhanced|improved|added|strengthened|using|with|technologies)\b', ln_clean) and
                not re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter|js|ts|express|django)\b', ln_clean) and
                len(ln.strip()) > 5 and len(ln.strip()) < 80):
                
                # Clean project title - remove any tech stack or description after dash/colon
                project_name = re.sub(r'[\u2014\-:]+.*$', '', ln).strip()
                project_name = re.sub(r'\s*[,;].*$', '', project_name).strip()
                
                # Only count if it looks like a proper project title
                if (len(project_name) > 5 and 
                    not re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter)\b', project_name.lower()) and
                    not re.search(r'\b(built|developed|created|implemented|designed)\b', project_name.lower())):
                    projects.add(project_name)
                    print(f"DEBUG: Added project: '{project_name}'")
                else:
                    print(f"DEBUG: Rejected project candidate: '{project_name}' (failed validation)")
            else:
                print(f"DEBUG: Skipped line: '{ln}' (failed filters)")
    
    # If no projects found in dedicated section, try pattern-based detection
    if not projects:
        print("DEBUG: No projects found in dedicated section, trying pattern-based detection")
        for i, ln in enumerate(lines):
            ln_clean = ln.strip()
            
            # Skip if line is too short or too long for a project title
            if len(ln_clean) < 6 or len(ln_clean) > 60:
                continue
                
            # Skip bullet points and descriptions
            if (re.match(r'^[\u2022\-\*•]\s*', ln_clean) or 
                re.search(r'\b(built|developed|created|implemented|designed|integrated|enhanced|improved|added|strengthened|using|with|technologies)\b', ln_clean.lower())):
                continue
                
            # Skip tech stack lines
            if re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter|js|ts|express|django)\b', ln_clean.lower()):
                continue
                
            # Look for lines that could be project titles (followed by tech description)
            next_line = lines[i+1] if i+1 < len(lines) else ""
            
            # If next line contains tech stack or description keywords, current line might be a title
            if (next_line and 
                (re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter)\b', next_line.lower()) or
                 re.search(r'\b(built|developed|created|implemented|designed|using|with|technologies)\b', next_line.lower()))):
                
                # Clean project title
                project_name = re.sub(r'[\u2014\-:]+.*$', '', ln_clean).strip()
                project_name = re.sub(r'\s*[,;].*$', '', project_name).strip()
                
                if (len(project_name) > 5 and 
                    not re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter)\b', project_name.lower())):
                    projects.add(project_name)
                    print(f"DEBUG: Pattern-based project added: '{project_name}'")
    
    num_projects = len(projects)
    print(f"DEBUG: Final project count: {num_projects}")
    print(f"DEBUG: Projects found: {list(projects)}")

    # Add skills found in projects (as fallback)
    project_text = " ".join(projects)
    for skill in SKILLS:
        if re.search(r'\b' + re.escape(skill.lower()) + r'\b', project_text.lower()):
            if skill.lower() not in SOFT_SKILLS:
                skills_found.add(skill)
    
    # Also scan the entire resume text for additional skills not caught by section parsing
        # Remove parenthetical/bracketed content from the full resume when scanning
    full_text_no_paren = re.sub(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}', ' ', text)
    # Expand compact variants in full text as well
    for pat, repl in COMPACT_MAP.items():
        full_text_no_paren = re.sub(pat, repl, full_text_no_paren)
    full_text_normalized = normalize_text(full_text_no_paren)
    sorted_skills = sorted(SKILLS, key=len, reverse=True)
    
    for skill in sorted_skills:
        skill_normalized = normalize_text(skill)
        
        # Simple substring matching with space padding for word boundaries
        padded_text = ' ' + full_text_normalized + ' '
        padded_skill = ' ' + skill_normalized + ' '
        
        if padded_skill in padded_text:
            if skill.lower() not in SOFT_SKILLS:
                skills_found.add(skill)

    # Experience/Internship section detection (similar to projects)
    experiences = set()
    in_experience_section = False
    
    print(f"DEBUG: Starting experience detection for resume with {len(lines)} lines")
    
    for i, ln in enumerate(lines):
        ln_clean = ln.strip().lower()
        
        # Check if entering experience section
        if re.match(r'^(experience|work experience|internships?|professional experience)\s*:?\s*$', ln_clean):
            in_experience_section = True
            print(f"DEBUG: Found experience section at line {i}: '{ln}'")
            continue
            
        # Check if leaving experience section
        if in_experience_section and re.match(r'^(projects?|education|skills?|certifications?|achievements?)\s*:?\s*$', ln_clean):
            in_experience_section = False
            print(f"DEBUG: Left experience section at line {i}: '{ln}'")
            continue
            
        # Extract experience entries
        if in_experience_section:
            # Look for lines with company/role indicators
            if re.search(r'\b(intern|trainee|engineer|developer|analyst)\b', ln_clean):
                experiences.add(ln.strip())
                print(f"DEBUG: Added experience: '{ln.strip()}'")
    
    # Internship detection - section-based approach for dedicated internship sections
    internships = set()
    in_internship_section = False
    
    print(f"DEBUG: Starting internship section detection")
    
    for i, ln in enumerate(lines):
        ln_clean = ln.strip().lower()
        
        # Check if entering internship section
        if re.match(r'^(internships?|interns?)\s*:?\s*$', ln_clean):
            in_internship_section = True
            print(f"DEBUG: Found internship section at line {i}: '{ln}'")
            continue
            
        # Check if leaving internship section
        if in_internship_section and re.match(r'^(projects?|education|skills?|certifications?|achievements?|experience|work experience)\s*:?\s*$', ln_clean):
            in_internship_section = False
            print(f"DEBUG: Left internship section at line {i}: '{ln}'")
            continue
            
        # Extract internship entries
        if in_internship_section:
            if (ln.strip() and 
                not re.match(r'^[\u2022\-\*•]\s*', ln) and
                len(ln.strip()) > 10 and len(ln.strip()) < 100):
                internships.add(ln.strip())
                print(f"DEBUG: Added internship from section: '{ln.strip()}'")
    
    # Separate work experience from internships
    num_experience = len(experiences)
    num_internships = len(internships)
    print(f"DEBUG: Final experience count: {num_experience}")
    print(f"DEBUG: Experiences found: {list(experiences)}")
    print(f"DEBUG: Final internship count: {num_internships}")
    print(f"DEBUG: Internships found: {list(internships)}")

    # Certifications with issuer check
    cert_lines = [l for l in lines if re.search(r'\b(certif(icate|ied)|certificate|certified)\b', l)]
    certs = set()
    for l in cert_lines:
        if any(iss in l for iss in ISSUERS) or re.search(r'issued by|by\s+[a-z]', l):
            if not re.search(r'workshop|fdp|bootcamp|training', l):
                certs.add(l)
    num_certifications = len(certs)

    # Workshops / FDP / Bootcamps - Count individual mentions, not just lines
    num_workshops = 0
    for l in lines:
        # Skip certification lines to avoid double counting
        if re.search(r'\b(certif(icate|ied)|certificate)\b', l, flags=re.IGNORECASE):
            continue
        # Count all workshop/fdp/bootcamp/training mentions in each line
        matches = re.findall(r'\b(workshop|fdp|bootcamp|training)\b', l, flags=re.IGNORECASE)
        num_workshops += len(matches)

    # Hackathons / Competitions
    hack_lines = [l for l in lines if re.search(r'\b(hackathon|contest|competition|tech fest|coding contest|event)\b', l)]
    hackathons = len(set(hack_lines))
    competitions = len([l for l in hack_lines if re.search(r'contest|competition', l)])

    participation_score = hackathons + num_workshops + competitions

    # finalize skills list (unique, cap 20)
    skills_list = sorted(list(set(s.lower() for s in skills_found)))
    if len(skills_list) > 20:
        skills_list = skills_list[:20]

    # Experience index normalization
    raw_exp = (num_projects * 1) + (num_internships * 2) + (hackathons * 2) + (num_certifications * 1)
    cap_raw = 30.0
    experience_index = round(min(10.0, (raw_exp / cap_raw) * 10.0), 2)

    return {
        "number_of_skills": len(skills_list),
        "skills_list": skills_list,
        "num_projects": int(num_projects),
        "num_internships": int(num_internships),
        "num_certifications": int(num_certifications),
        "hackathons": int(hackathons),
        "workshops": int(num_workshops),
        "competitions": int(competitions),
        "participation_score": int(participation_score),
        "experience_index": experience_index,
        "resume_text": text
    }


def ats_grade_resume_analysis(resume_text, job_description=None):
    """
    ATS-grade resume analysis engine for predictive placement readiness system.
    Extracts structured metrics only - no hallucination, counts only explicit content.
    
    Returns JSON with exact structure:
    {
        "skills_count": number,
        "projects_count": number,
        "internships_count": number,
        "certifications_count": number,
        "events_count": number,
        "workshops_count": number,
        "ats_score": number | null
    }
    """
    if not resume_text:
        return {
            "skills_count": 0,
            "projects_count": 0,
            "internships_count": 0,
            "certifications_count": 0,
            "events_count": 0,
            "workshops_count": 0,
            "ats_score": None
        }
    
    text = resume_text.lower()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # 1️⃣ SKILLS EXTRACTION
    skills_found = set()
    
    # Sort skills by length (longest first) for better matching
    sorted_skills = sorted(SKILLS, key=len, reverse=True)
    
    for skill in sorted_skills:
        skill_lower = skill.lower()
        # Use word boundary matching for accurate detection
        if re.search(r'\b' + re.escape(skill_lower) + r'\b', text):
            if skill_lower not in SOFT_SKILLS:
                skills_found.add(skill_lower)
    
    skills_count = len(skills_found)
    
    # 2️⃣ PROJECTS EXTRACTION - More accurate project counting
    projects = set()
    in_project_section = False
    
    print(f"DEBUG ATS: Starting project detection for resume with {len(lines)} lines")
    
    for i, line in enumerate(lines):
        line_clean = line.strip()
        line_lower = line_clean.lower()
        
        # Check if entering projects section
        if re.match(r'^(projects?|academic projects?|project experience|personal projects?)\s*:?\s*$', line_lower):
            in_project_section = True
            print(f"DEBUG ATS: Found project section at line {i}: '{line_clean}'")
            continue
            
        # Check if leaving projects section
        if in_project_section and re.match(r'^(experience|education|skills?|certifications?|achievements?|internships?)\s*:?\s*$', line_lower):
            in_project_section = False
            print(f"DEBUG ATS: Left project section at line {i}: '{line_clean}'")
            continue
            
        # Extract project titles (ignore tech stack lines and descriptions)
        if in_project_section:
            print(f"DEBUG ATS: Processing line {i} in project section: '{line_clean}'")
            
            # Skip empty lines, bullet points, descriptions, and tech stacks
            if (line_clean and 
                not re.match(r'^[\u2022\-\*•]\s*', line_clean) and 
                not re.search(r'\b(built|developed|created|implemented|designed|integrated|enhanced|improved|added|strengthened|using|with|technologies)\b', line_lower) and
                not re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter|js|ts|express|django)\b', line_lower) and
                len(line_clean) > 5 and len(line_clean) < 80):
                
                # Clean project name - remove tech stack or description after dash/colon
                project_name = re.sub(r'[\u2014\-:]+.*$', '', line_clean).strip()
                project_name = re.sub(r'\s*[,;].*$', '', project_name).strip()
                
                # Only count if it looks like a proper project title
                if (len(project_name) > 5 and 
                    not re.search(r'\b(html|css|javascript|python|java|react|node|flask|mysql|api|mongodb|firebase|flutter)\b', project_name.lower()) and
                    not re.search(r'\b(built|developed|created|implemented|designed)\b', project_name.lower())):
                    projects.add(project_name)
                    print(f"DEBUG ATS: Added project: '{project_name}'")
                else:
                    print(f"DEBUG ATS: Rejected project candidate: '{project_name}' (failed validation)")
            else:
                print(f"DEBUG ATS: Skipped line: '{line_clean}' (failed filters)")
    
    projects_count = len(projects)
    print(f"DEBUG ATS: Final project count: {projects_count}")
    print(f"DEBUG ATS: Projects found: {list(projects)}")
    
    # 3️⃣ INTERNSHIPS EXTRACTION (improved)
    # Detect 'intern' mentions and consult surrounding lines (previous/next)
    # for company or date context so headings like "Webdevelopment Intern"
    # followed by a company line are counted as internships.
    internships = set()

    for i, line in enumerate(lines):
        if re.search(r'\b(intern(ship)?|trainee)\b', line, flags=re.IGNORECASE):
            prev_line = lines[i-1] if i-1 >= 0 else ""
            next_line = lines[i+1] if i+1 < len(lines) else ""

            # Check for explicit duration, month names, or common company tokens
            def has_context(s):
                return bool(
                    re.search(r'\b(\d{1,2})\s*(month|week)\b', s, flags=re.IGNORECASE) or
                    re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', s, flags=re.IGNORECASE) or
                    re.search(r'\b(pvt|ltd|inc|corp|company|technologies|systems|solutions)\b', s, flags=re.IGNORECASE)
                )

            counted = False
            if has_context(line) or has_context(prev_line) or has_context(next_line):
                # Use heading + nearest context line to form a unique key
                key = (line.strip() + ' | ' + (next_line.strip() if has_context(next_line) else prev_line.strip()))
                internships.add(key)
                counted = True

            if not counted:
                # Also consider next line as company if it looks like a company/title
                if next_line and re.match(r'^[A-Z][A-Za-z0-9&\-\s]{2,}$', next_line.strip()):
                    key = (line.strip() + ' | ' + next_line.strip())
                    internships.add(key)
                    counted = True

            if not counted:
                # Last resort: count the heading itself (user intent: 'intern' in heading)
                internships.add(line.strip())

    internships_count = len(internships)
    
    # 4️⃣ CERTIFICATIONS EXTRACTION
    certifications = set()
    
    for line in lines:
        if re.search(r'\b(certif(icate|ied)|certificate|certified)\b', line):
            # Must have issuer or be explicit certification
            if (any(issuer in line.lower() for issuer in ISSUERS) or 
                re.search(r'\b(issued by|by\s+[a-z]|completion|course)\b', line)):
                # Exclude workshops/training unless explicitly certified
                if not re.search(r'\b(workshop|training|bootcamp)\b', line) or re.search(r'\bcertified\b', line):
                    certifications.add(line.strip())
    
    certifications_count = len(certifications)
    
    # 5️⃣ EVENTS/PARTICIPATIONS EXTRACTION
    events = set()
    
    for line in lines:
        if re.search(r'\b(hackathon|contest|competition|tech fest|coding contest|participated|participation)\b', line):
            # Must be explicit participation, not just mention
            if re.search(r'\b(participated|participation|winner|finalist|attended|competed)\b', line):
                events.add(line.strip())
    
    events_count = len(events)
    
    # 6️⃣ WORKSHOPS EXTRACTION - Count individual mentions, not just lines
    workshops_count = 0
    for line in lines:
        # Skip certification lines to avoid double counting
        if re.search(r'\b(certif(icate|ied)|certificate)\b', line, flags=re.IGNORECASE):
            continue
        # Count all workshop/fdp/bootcamp/training mentions in each line
        matches = re.findall(r'\b(workshop|fdp|bootcamp|training)\b', line, flags=re.IGNORECASE)
        workshops_count += len(matches)
    
    # 📊 ATS SCORE CALCULATION
    ats_score = None
    matched_keywords = []
    missing_keywords = []
    
    if job_description:
        jd_lower = job_description.lower()
        
        # Extract skills from job description
        jd_skills = set()
        for skill in sorted_skills:
            if re.search(r'\b' + re.escape(skill.lower()) + r'\b', jd_lower):
                jd_skills.add(skill.lower())
        
        # Calculate skill overlap
        matched_skills = skills_found.intersection(jd_skills)
        missing_skills = jd_skills.difference(skills_found)
        
        matched_keywords = sorted(list(matched_skills))
        missing_keywords = sorted(list(missing_skills))
        
        # Calculate ATS score based on skill match and resume completeness
        skill_match_pct = (len(matched_skills) / max(1, len(jd_skills))) * 100 if jd_skills else 0
        
        # TF-IDF similarity for semantic matching
        try:
            vec = TfidfVectorizer(stop_words='english').fit([jd_lower, text])
            tf = vec.transform([jd_lower, text])
            num = tf[0].multiply(tf[1]).sum()
            denom = (math.sqrt(tf[0].power(2).sum()) * math.sqrt(tf[1].power(2).sum()))
            semantic_sim = float(num / denom) if denom != 0 else 0.0
        except:
            semantic_sim = 0.0
        
        # Resume completeness score
        completeness = min(1.0, (skills_count + projects_count + internships_count) / 10.0)
        
        # Weighted ATS score
        ats_raw = (0.5 * (skill_match_pct / 100.0) + 0.3 * semantic_sim + 0.2 * completeness)
        ats_score = max(0, min(100, round(ats_raw * 100)))
    
    return {
        "skills_count": skills_count,
        "projects_count": projects_count,
        "internships_count": internships_count,
        "certifications_count": certifications_count,
        "events_count": events_count,
        "workshops_count": workshops_count,
        "ats_score": ats_score
    }


def ats_score(job_description, resume_text, resume_feats=None):
    """
    Legacy function - kept for backward compatibility.
    Use ats_grade_resume_analysis for new implementations.
    """
    result = ats_grade_resume_analysis(resume_text, job_description)
    
    return {
        'ats_score': result.get('ats_score', 0) or 0,
        'skill_match_pct': 0,  # Not calculated in new version
        'missing_keywords': [],
        'section_coverage': 0.8,  # Default value
        'experience_relevance': min(1.0, (result.get('projects_count', 0) + result.get('internships_count', 0)) / 3.0),
        'strength_level': 'Good' if result.get('ats_score', 0) > 60 else 'Average'
    }
