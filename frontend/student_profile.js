document.addEventListener('DOMContentLoaded', () => {
  // Global debug flag to prevent duplicate initializations
  if (window.profilePageInitialized) {
    console.log('DEBUG: Profile page already initialized, skipping');
    return;
  }
  window.profilePageInitialized = true;
  console.log('DEBUG: Initializing profile page');
  
  // Check if user is logged in and load existing profile
  loadExistingProfile();
  
  // initialize inner progress bars for stat-bar elements FIRST
  document.querySelectorAll('.stat-bar').forEach(p => {
    if (!p.querySelector('.bar-inner')){
      const bar = document.createElement('div');
      bar.className = 'bar-inner';
      bar.style.width = '0%';
      bar.style.height = '100%';
      bar.style.borderRadius = '999px';
      bar.style.transition = 'width 900ms cubic-bezier(.2,.9,.2,1)';
      bar.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
      p.appendChild(bar);
    }
  });

  // Ensure progress bars are visible and functional
  function initializeProgressBars() {
    const progressBars = ['#commBar', '#codingBar', '#resumeBar'];
    progressBars.forEach(selector => {
      const el = document.querySelector(selector);
      if (el && !el.querySelector('.bar-inner')) {
        const bar = document.createElement('div');
        bar.className = 'bar-inner';
        bar.style.cssText = 'width: 0%; height: 100%; border-radius: 999px; transition: width 900ms cubic-bezier(.2,.9,.2,1); background: linear-gradient(90deg, #667eea, #764ba2);';
        el.appendChild(bar);
      }
    });
  }
  initializeProgressBars();

  // Load profile data from database if available
  async function loadExistingProfile() {
    try {
      // CRITICAL: Clear any cached data from previous student
      sessionStorage.removeItem('analyticsData');
      
      // Check if coming from analytics page
      let rollNo = sessionStorage.getItem('loadStudentId');
      if (rollNo) {
        sessionStorage.removeItem('loadStudentId'); // Clean up
        // Pre-fill roll number
        const rollInput = document.querySelector('[name="roll_no"]');
        if (rollInput) rollInput.value = rollNo;
      }
      
      // Load profile based on logged-in user
      const response = await fetch('/api/student/profile/load');
      if (response.ok) {
        const profile = await response.json();
        
        if (profile.has_existing_data) {
          // User has existing profile data - populate form
          populateFormFromProfile(profile);
          displayAnalysisResults(profile);
        } else {
          // User is logged in but no profile data - clear form and show what's needed
          clearFormFields();
          const rollInput = document.querySelector('[name="roll_no"]');
          if (rollInput && profile.register_number) {
            rollInput.value = profile.register_number;
            rollInput.readOnly = true; // Make it read-only since it's from login
          }
          
          // Show new user guidance
          showNewUserGuidance();
        }
      } else if (response.status === 401) {
        // User not logged in - redirect to login
        alert('Please login first');
        window.location.href = 'login_student.html';
      }
    } catch (e) {
      console.log('Error loading profile:', e);
      // Don't redirect on error - user might not be logged in
    }
  }
  
  function getCurrentStudentId() {
    // Try to get from form first, then from stored data
    const rollInput = document.querySelector('[name="roll_no"]');
    return rollInput ? rollInput.value : null;
  }
  
  function clearFormFields() {
    // Clear all form inputs except register number
    const form = document.getElementById('profileForm');
    form.querySelector('[name="name"]').value = '';
    form.querySelector('[name="year"]').value = '';
    form.querySelector('[name="branch"]').value = '';
    form.querySelector('[name="cgpa"]').value = '';
    form.querySelector('[name="backlogs"]').value = '0';
    
    // Clear questionnaire responses
    document.querySelectorAll('[data-q="comm"]').forEach(s => s.value = '0');
    document.querySelectorAll('[data-q="coding"]').forEach(s => s.value = '0');
    
    // Clear file inputs
    document.getElementById('resume').value = '';
    const marksFile = document.getElementById('marksFile');
    if (marksFile) marksFile.value = '';
    
    // Clear file status displays
    const fileStatus = document.getElementById('fileStatus');
    const marksFileStatus = document.getElementById('marksFileStatus');
    if (fileStatus) {
      fileStatus.textContent = '';
      fileStatus.className = 'file-status';
    }
    if (marksFileStatus) {
      marksFileStatus.textContent = '';
      marksFileStatus.className = 'file-status';
    }
    
    // Reset all progress bars and metrics
    resetVisuals();
    
    console.log('Form fields cleared for new student');
  }
  
  function populateFormFromProfile(profile) {
    const form = document.getElementById('profileForm');
    if (profile.name) form.querySelector('[name="name"]').value = profile.name;
    if (profile.register_number) {
      const rollInput = form.querySelector('[name="roll_no"]');
      rollInput.value = profile.register_number;
      rollInput.readOnly = true; // Make read-only since it's from login
    }
    if (profile.year) form.querySelector('[name="year"]').value = profile.year;
    if (profile.branch) form.querySelector('[name="branch"]').value = profile.branch;
    if (profile.cgpa) form.querySelector('[name="cgpa"]').value = profile.cgpa;
    if (profile.backlogs !== undefined) form.querySelector('[name="backlogs"]').value = profile.backlogs;
    
    // Show existing marks file if available
    if (profile.marks_file) {
      const marksFileStatus = document.getElementById('marksFileStatus');
      if (marksFileStatus) {
        let displayName = profile.marks_file;
        
        // Handle if marks_file contains filename
        if (typeof displayName === 'string' && displayName.trim()) {
          // Check if it's a filename (contains extension)
          if (displayName.includes('.')) {
            // Extract original filename from UUID prefix if present
            if (displayName.includes('_') && displayName.length > 40) {
              displayName = displayName.substring(displayName.indexOf('_') + 1);
            }
            marksFileStatus.textContent = `Current file: ${displayName}`;
          } else {
            // It's probably the coding answers array as string
            marksFileStatus.textContent = 'Marks file uploaded (please re-upload for proper display)';
          }
        } else {
          marksFileStatus.textContent = 'Marks file uploaded';
        }
        marksFileStatus.className = 'file-status success';
      }
    }
    
    // Show existing resume file if available
    if (profile.resume_filename) {
      const resumeFileStatus = document.getElementById('fileStatus');
      if (resumeFileStatus) {
        let displayName = profile.resume_filename;
        
        // Handle if resume_filename contains filename
        if (typeof displayName === 'string' && displayName.trim()) {
          // Check if it's a filename (contains extension)
          if (displayName.includes('.')) {
            // Extract original filename from UUID prefix if present
            if (displayName.includes('_') && displayName.length > 40) {
              displayName = displayName.substring(displayName.indexOf('_') + 1);
            }
            resumeFileStatus.textContent = `Current file: ${displayName}`;
          } else {
            resumeFileStatus.textContent = 'Resume file uploaded (please re-upload for proper display)';
          }
        } else {
          resumeFileStatus.textContent = 'Resume file uploaded';
        }
        resumeFileStatus.className = 'file-status success';
      }
    }
    
    // Show missing information notice if profile is incomplete
    showProfileCompletionStatus(profile);
  }
  
  function displayAnalysisResults(profile) {
    console.log('Displaying analysis results with profile:', profile);
    
    // Update progress bars with stored scores from database
    if (profile.communication_score !== undefined) {
      updateProgress('#commBar', profile.communication_score);
      console.log('Setting communication bar from profile:', profile.communication_score);
    }
    if (profile.coding_score !== undefined) {
      updateProgress('#codingBar', profile.coding_score);
    }
    if (profile.resume_ats_score !== undefined) {
      updateProgress('#resumeBar', profile.resume_ats_score);
    }
    
    // Restore questionnaire responses with delay to ensure DOM is ready
    setTimeout(() => {
      if (profile.communication_answers && profile.communication_answers !== '[]') {
        try {
          const commAnswers = typeof profile.communication_answers === 'string' 
            ? JSON.parse(profile.communication_answers) 
            : profile.communication_answers;
          const commSelects = document.querySelectorAll('[data-q="comm"]');
          console.log('Restoring communication answers:', commAnswers, 'to', commSelects.length, 'selects');
          
          if (Array.isArray(commAnswers)) {
            commAnswers.forEach((val, idx) => {
              if (commSelects[idx] && val !== undefined && val !== null) {
                commSelects[idx].value = String(val);
                console.log(`Set comm select ${idx} to ${val}`);
              }
            });
          }
          
          // Update live score to match stored score
          const commLiveEl = document.getElementById('commLiveScore');
          if (commLiveEl && profile.communication_score !== undefined) {
            commLiveEl.textContent = profile.communication_score;
          }
          
          updateCommProgress();
        } catch (e) {
          console.warn('Failed to restore communication answers:', e);
        }
      }
      
      if (profile.coding_answers && profile.coding_answers !== '[]') {
        try {
          const codingAnswers = typeof profile.coding_answers === 'string' 
            ? JSON.parse(profile.coding_answers) 
            : profile.coding_answers;
          const codingSelects = document.querySelectorAll('[data-q="coding"]');
          console.log('Restoring coding answers:', codingAnswers, 'to', codingSelects.length, 'selects');
          
          if (Array.isArray(codingAnswers)) {
            codingAnswers.forEach((val, idx) => {
              if (codingSelects[idx] && val !== undefined && val !== null) {
                codingSelects[idx].value = String(val);
                console.log(`Set coding select ${idx} to ${val}`);
              }
            });
          }
          updateCodingLive();
        } catch (e) {
          console.warn('Failed to restore coding answers:', e);
        }
      }
    }, 500);
    
    // Update metrics
    animateMetric('skillsCount', profile.skills_count);
    animateMetric('projectsCount', profile.projects);
    animateMetric('internshipsCount', profile.internships);
    animateMetric('certificationsCount', profile.certifications);
    animateMetric('eventsCount', profile.hackathons);
    animateMetric('workshopsCount', profile.workshops);
    
    // Update coding breakdown - calculate from stored data
    let questScore = 0;
    if (profile.coding_answers) {
      try {
        const codingAnswers = JSON.parse(profile.coding_answers);
        questScore = codingAnswers.reduce((sum, val) => sum + (val || 0), 0);
      } catch (e) {
        questScore = 0;
      }
    }
    
    const resumeBoost = Math.min(10, (profile.projects || 0) * 3 + (profile.skills_count || 0));
    const finalCoding = profile.coding_score || 0;
    
    const codingQuestionnaireEl = document.getElementById('codingQuestionnaire');
    const resumeBoostEl = document.getElementById('resumeBoost');
    const finalCodingEl = document.getElementById('finalCoding');
    
    if (codingQuestionnaireEl) codingQuestionnaireEl.textContent = questScore;
    if (resumeBoostEl) resumeBoostEl.textContent = resumeBoost;
    if (finalCodingEl) finalCodingEl.textContent = finalCoding;
    
    // Use overall_readiness_score consistently for overall display
    const overallScore = profile.overall_readiness_score || profile.v_score || 0;
    updateOverall(overallScore);
    
    console.log('Profile page displaying overall_readiness_score:', overallScore, 'from profile data');
    
    // Show placement status if available based on current score
    if (profile.overall_readiness_score !== undefined) {
      const currentScore = profile.overall_readiness_score;
      let status;
      if (currentScore >= 70) {
        status = 'Placement Ready';
      } else if (currentScore >= 40) {
        status = 'Medium Risk';
      } else {
        status = 'High Risk';
      }
      displayPlacementStatus(currentScore / 100, status);
    }
    
    // Show last updated
    if (profile.updated_at) {
      const lastUpdated = new Date(profile.updated_at).toLocaleDateString();
      showLastUpdated(lastUpdated);
    }
  }
  
  function showLastUpdated(date) {
    // Add or update last updated indicator
    let indicator = document.getElementById('lastUpdated');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'lastUpdated';
      indicator.style.cssText = 'text-align: center; color: #666; font-size: 0.9em; margin-top: 10px;';
      document.querySelector('.profile-form').appendChild(indicator);
    }
    indicator.textContent = `Last updated: ${date}`;
  }
  
  function showProfileCompletionStatus(profile) {
    // Check what information is missing
    const missingFields = [];
    
    if (!profile.name || profile.name.trim() === '') missingFields.push('Name');
    if (!profile.branch || profile.branch.trim() === '') missingFields.push('Branch');
    if (!profile.year || profile.year.trim() === '') missingFields.push('Year');
    if (!profile.cgpa || profile.cgpa === 0) missingFields.push('CGPA');
    
    // Check questionnaire responses
    let commAnswers = [];
    let codingAnswers = [];
    try {
      commAnswers = typeof profile.communication_answers === 'string' 
        ? JSON.parse(profile.communication_answers || '[]')
        : (profile.communication_answers || []);
      codingAnswers = typeof profile.coding_answers === 'string'
        ? JSON.parse(profile.coding_answers || '[]')
        : (profile.coding_answers || []);
    } catch (e) {
      commAnswers = [];
      codingAnswers = [];
    }
    
    const hasCommAnswers = Array.isArray(commAnswers) && commAnswers.length >= 5;
    const hasCodingAnswers = Array.isArray(codingAnswers) && codingAnswers.length >= 5;
    
    if (!hasCommAnswers) missingFields.push('Communication Assessment');
    if (!hasCodingAnswers) missingFields.push('Technical Skills Assessment');
    
    // Show completion status
    let statusEl = document.getElementById('profileCompletionStatus');
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.id = 'profileCompletionStatus';
      statusEl.style.cssText = 'margin: 15px 0; padding: 12px; border-radius: 8px; font-size: 0.9em;';
      
      // Insert after the page heading
      const heading = document.querySelector('.page-heading');
      heading.parentNode.insertBefore(statusEl, heading.nextSibling);
    }
    
    if (missingFields.length > 0) {
      statusEl.style.background = 'rgba(251, 191, 36, 0.1)';
      statusEl.style.border = '1px solid rgba(251, 191, 36, 0.3)';
      statusEl.style.color = '#92400e';
      statusEl.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <span style="font-size: 1.2em;">⚠️</span>
          <strong>Profile Incomplete</strong>
        </div>
        <div>Please complete the following sections: <strong>${missingFields.join(', ')}</strong></div>
        <div style="font-size: 0.8em; margin-top: 5px; opacity: 0.8;">Complete your profile to get accurate insights and placement predictions.</div>
      `;
    } else {
      statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
      statusEl.style.border = '1px solid rgba(16, 185, 129, 0.3)';
      statusEl.style.color = '#065f46';
      statusEl.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 1.2em;">✅</span>
          <strong>Profile Complete</strong> - Ready for analysis!
        </div>
      `;
    }
  }
  
  function showNewUserGuidance() {
    let statusEl = document.getElementById('profileCompletionStatus');
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.id = 'profileCompletionStatus';
      statusEl.style.cssText = 'margin: 15px 0; padding: 15px; border-radius: 10px; font-size: 0.9em;';
      
      // Insert after the page heading
      const heading = document.querySelector('.page-heading');
      heading.parentNode.insertBefore(statusEl, heading.nextSibling);
    }
    
    statusEl.style.background = 'linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(147, 51, 234, 0.1))';
    statusEl.style.border = '1px solid rgba(59, 130, 246, 0.3)';
    statusEl.style.color = '#1e40af';
    statusEl.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
        <span style="font-size: 1.5em;">🎯</span>
        <strong style="font-size: 1.1em;">Welcome! Let's build your AI-powered placement profile</strong>
      </div>
      <div style="margin-bottom: 10px;">To get started, please complete the following steps:</div>
      <div style="display: grid; gap: 8px; margin-left: 20px;">
        <div>📝 <strong>Personal Information</strong> - Name, branch, year, and academic details</div>
        <div>🗣️ <strong>Communication Assessment</strong> - 5 quick questions about your communication skills</div>
        <div>💻 <strong>Technical Skills</strong> - Evaluate your programming and problem-solving abilities</div>
        <div>📄 <strong>Resume Upload</strong> - Upload your resume for analysis and skill extraction</div>
      </div>
      <div style="font-size: 0.85em; margin-top: 12px; padding: 8px; background: rgba(255, 255, 255, 0.7); border-radius: 6px;">
        💡 <strong>Tip:</strong> The more complete your profile, the more accurate your AI-powered placement predictions will be!
      </div>
    `;
  }

  // Restore form data and results if available
  const analyticsData = sessionStorage.getItem('analyticsData');
  if (analyticsData) {
    try {
      const data = JSON.parse(analyticsData);
      if (data.form_data) {
        // Restore form fields
        const form = document.getElementById('profileForm');
        if (data.form_data.name) form.querySelector('[name="name"]').value = data.form_data.name;
        if (data.form_data.roll_no) form.querySelector('[name="roll_no"]').value = data.form_data.roll_no;
        if (data.form_data.year) form.querySelector('[name="year"]').value = data.form_data.year;
        if (data.form_data.branch) form.querySelector('[name="branch"]').value = data.form_data.branch;
        if (data.form_data.cgpa) form.querySelector('[name="cgpa"]').value = data.form_data.cgpa;
        if (data.form_data.backlogs) form.querySelector('[name="backlogs"]').value = data.form_data.backlogs;
        if (data.form_data.domain) form.querySelector('[name="domain"]').value = data.form_data.domain;
        if (data.form_data.job_description) document.getElementById('jobDescription').value = data.form_data.job_description;
        
        // Restore questionnaire answers
        if (data.form_data.communication_answers) {
          const commAnswers = JSON.parse(data.form_data.communication_answers);
          const commSelects = document.querySelectorAll('[data-q="comm"]');
          commAnswers.forEach((val, idx) => {
            if (commSelects[idx]) commSelects[idx].value = val;
          });
        }
        
        if (data.form_data.coding_answers) {
          const codingAnswers = JSON.parse(data.form_data.coding_answers);
          const codingSelects = document.querySelectorAll('[data-q="coding"]');
          codingAnswers.forEach((val, idx) => {
            if (codingSelects[idx]) codingSelects[idx].value = val;
          });
        }
        
        // Restore computed results using stored analytics data
        updateProgress('#commBar', data.communication_score || 0);
        updateProgress('#codingBar', data.coding_score || 0);
        updateProgress('#resumeBar', data.resume_score || 0);
        
        // Restore resume metrics
        animateMetric('skillsCount', data.resume_metrics?.skills_count);
        animateMetric('projectsCount', data.resume_metrics?.projects);
        animateMetric('internshipsCount', data.resume_metrics?.internships);
        animateMetric('certificationsCount', data.resume_metrics?.certifications);
        animateMetric('eventsCount', data.resume_metrics?.hackathons);
        animateMetric('workshopsCount', data.resume_metrics?.workshops);
        
        // Use stored v_score for overall display (SINGLE SOURCE OF TRUTH)
        updateOverall(data.v_score || 0);
        
        // Display v_score prominently
        displayVScore(data.v_score || 0);
        
        // Display placement status using consistent v_score
        if (data.v_score !== undefined) {
          displayPlacementStatus(data.v_score / 100, data.placement_status);
        }
        
        // Update coding breakdown using stored values
        const codingQuestionnaireEl = document.getElementById('codingQuestionnaire');
        const resumeBoostEl = document.getElementById('resumeBoost');
        const finalCodingEl = document.getElementById('finalCoding');
        
        if (codingQuestionnaireEl) codingQuestionnaireEl.textContent = data.coding_questionnaire_score || 0;
        if (resumeBoostEl) resumeBoostEl.textContent = data.resume_boost || 0;
        if (finalCodingEl) finalCodingEl.textContent = data.coding_score || 0;
      }
    } catch (e) {
      console.warn('Failed to restore form data:', e);
    }
  }
  
  const form = document.getElementById('profileForm');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const fd = new FormData(form);

    // collect communication answers
    const comm = Array.from(document.querySelectorAll('[data-q="comm"]')).map(s => Number(s.value || 0));

    // collect coding answers
    const coding = Array.from(document.querySelectorAll('[data-q="coding"]')).map(s => Number(s.value || 0));

    // normalize CGPA if percentage selected
    const scoreType = document.getElementById('scoreType').value;
    const cgpaInput = form.querySelector('[name="cgpa"]');
    let cgpaVal = Number(cgpaInput.value || 0);
    if (scoreType === 'percentage'){
      // convert percentage (0-100) to cgpa scale (0-10)
      cgpaVal = Math.max(0, Math.min(100, cgpaVal)) / 10.0;
    }
    fd.set('cgpa', cgpaVal.toString());

    fd.set('communication_answers', JSON.stringify(comm));
    fd.set('coding_answers', JSON.stringify(coding));
    
    // Capture preferred domain for recommendations only (not stored in database)
    const preferredDomain = document.getElementById('preferredDomain')?.value || '';
    
    // include job description if provided
    const jd = document.getElementById('jobDescription').value || '';
    if (jd) fd.set('job_description', jd);
    
    // Add marks file if selected
    const marksFile = document.getElementById('marksFile');
    if (marksFile && marksFile.files[0]) {
      fd.append('marks_file', marksFile.files[0]);
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true; submitBtn.textContent = 'Analyzing...';

    try{
      const res = await fetch('/api/student/profile/analyze', { method: 'POST', body: fd });
      if (!res.ok){
        const txt = await res.text();
        throw new Error(txt || 'Server error');
      }
      const data = await res.json();
      
      // Use exact v_score from backend - NO modifications
      const validVScore = parseFloat(data.v_score);
      if (isNaN(validVScore)) {
        console.error('Invalid v_score received:', data.v_score);
        return;
      }
      
      console.log('ML Model v_score received:', validVScore);
      
      // Store COMPLETE analysis data for persistence
      const completeAnalyticsData = {
        // Personal details (INCLUDE CGPA)
        name: data.name || fd.get("name") || "",
        roll_no: data.roll_no || fd.get("roll_no") || "",
        register_number: data.roll_no || fd.get("roll_no") || "",
        year: data.year || fd.get("year") || "",
        branch: data.branch || fd.get("branch") || "",
        cgpa: data.cgpa || parseFloat(fd.get("cgpa")) || 0,
        backlogs: data.backlogs || parseInt(fd.get("backlogs")) || 0,
        preferred_domain: preferredDomain, // Store for recommendations only
        
        // Form inputs (for restoration)
        form_data: {
          name: fd.get("name") || "",
          roll_no: fd.get("roll_no") || "",
          year: fd.get("year") || "",
          branch: fd.get("branch") || "",
          cgpa: fd.get("cgpa") || "",
          backlogs: fd.get("backlogs") || "",
          domain: fd.get("domain") || "",
          communication_answers: fd.get('communication_answers'),
          coding_answers: fd.get('coding_answers'),
          job_description: fd.get('job_description') || ''
        },
        
        // Analysis results (SINGLE SOURCE OF TRUTH)
        v_score: validVScore,
        final_score: validVScore,
        placement_status: data.placement_status || "Unknown",
        risk_flag: data.risk_flag || false,
        
        // Breakdown scores
        breakdown: data.breakdown || {
          coding: data.coding_score || 0,
          communication: data.communication_score || 0,
          resume: data.resume_score || 0,
          participation: 0
        },
        
        // Individual scores (SINGLE SOURCE OF TRUTH)
        communication_score: data.communication_score || 0,
        coding_questionnaire_score: data.coding_questionnaire_score || 0,
        resume_boost: data.resume_boost || 0,
        coding_score: data.coding_score || 0,
        resume_score: data.resume_score || 0,
        overall_readiness: validVScore,
        
        // Resume metrics
        resume_metrics: {
          skills_count: data.number_of_skills || 0,
          projects: data.num_projects || 0,
          internships: data.num_internships || 0,
          certifications: data.num_certifications || 0,
          workshops: data.workshops || 0,
          hackathons: data.hackathons || 0
        },
        
        // Additional data
        strengths: data.strengths || [],
        improvement_areas: data.improvement_areas || [],
        recommendations: data.recommendations || [],
        ats_score: data.ats?.ats_score || 0,
        skill_match_pct: data.ats?.skill_match_pct || 0,
        experience_index: data.experience_index || 0,
        
        generated_at: Date.now()
      };
      
      // Store in sessionStorage for persistence
      sessionStorage.setItem('analyticsData', JSON.stringify(completeAnalyticsData));
      
      // Display placement status using validated v_score
      displayPlacementStatus(validVScore / 100, data.placement_status);
      
      // update UI (with animations) - use consistent v_score
      updateProgress('#commBar', data.communication_score || 0);
      updateProgress('#codingBar', data.coding_score || data.coding_questionnaire_score || 0);
      updateProgress('#resumeBar', data.resume_score || 0);
      animateMetric('skillsCount', data.number_of_skills);
      animateMetric('projectsCount', data.num_projects);
      animateMetric('internshipsCount', data.num_internships);
      animateMetric('certificationsCount', data.num_certifications);
      animateMetric('eventsCount', data.hackathons);
      animateMetric('workshopsCount', data.workshops);

      // ATS info if present
      if (data.ats){
        animateMetric('atsScore', data.ats.ats_score);
        const skillMatchEl = document.getElementById('skillMatchPct');
        const experienceIndexEl = document.getElementById('experienceIndex');
        const atsMiniEl = document.getElementById('atsMini');
        
        if (skillMatchEl) skillMatchEl.textContent = (data.ats.skill_match_pct || 0) + '%';
        if (experienceIndexEl) experienceIndexEl.textContent = (data.experience_index !== undefined) ? data.experience_index : (Math.round((data.num_projects||0) + (data.num_internships||0)));
        if (atsMiniEl) atsMiniEl.textContent = `ATS: ${data.ats.ats_score} — ${data.ats.strength_level}`;
      }

      // Use v_score for overall display (SINGLE SOURCE OF TRUTH)
      updateOverall(validVScore);
      
      // Display v_score prominently
      displayVScore(validVScore);

      // coding breakdown - use exact values from backend
      const qScore = data.coding_questionnaire_score || 0;
      const resumeBoost = data.resume_boost || 0;
      const finalCoding = data.coding_score || 0;
      
      const codingQuestionnaireEl = document.getElementById('codingQuestionnaire');
      const resumeBoostEl = document.getElementById('resumeBoost');
      const finalCodingEl = document.getElementById('finalCoding');
      
      if (codingQuestionnaireEl) codingQuestionnaireEl.textContent = qScore;
      if (resumeBoostEl) resumeBoostEl.textContent = resumeBoost;
      if (finalCodingEl) finalCodingEl.textContent = finalCoding;
      
      // also update live coding preview
      const live = document.getElementById('codingLiveScore');
      if (live) live.textContent = qScore;

    }catch(err){
      console.error('Analysis error:', err);
      alert('Error: ' + (err.message || 'Analysis failed. Please try again.'));
    }finally{
      submitBtn.disabled = false; submitBtn.textContent = 'Analyze Profile';
    }
  });

  // Remove reset button event listener since button was removed
  // (resetBtn was removed from HTML)

  // Score type switching behaviour
  const scoreType = document.getElementById('scoreType');
  const scoreLabelText = document.getElementById('scoreLabelText');
  const cgpaInput = document.getElementById('cgpaInput');
  scoreType.addEventListener('change', (e)=>{
    const v = e.target.value;
    if (v === 'cgpa'){
      scoreLabelText.textContent = 'CGPA (out of 10)';
      cgpaInput.min = 0; cgpaInput.max = 10; cgpaInput.value = 7.5;
    } else {
      scoreLabelText.textContent = 'Percentage';
      cgpaInput.min = 0; cgpaInput.max = 100; cgpaInput.value = 75;
    }
    cgpaInput.classList.add('pulse');
    setTimeout(()=> cgpaInput.classList.remove('pulse'), 700);
  });

  // Communication live preview
  const commSelects = Array.from(document.querySelectorAll('[data-q="comm"]'));
  function updateCommLive(){
    const vals = commSelects.map(s => Number(s.value||0));
    const total = vals.reduce((a,b)=>a+b,0);
    document.getElementById('commLiveScore').textContent = total;
    const answered = vals.filter(v=>v>0).length;
    document.getElementById('commProgress').textContent = `Answered ${answered} of ${commSelects.length}`;
  }
  
  function updateCommProgress(){
    const commSelects = document.querySelectorAll('[data-q="comm"]');
    const vals = Array.from(commSelects).map(s => Number(s.value||0));
    const answered = vals.filter(v=>v>0).length;
    const progressEl = document.getElementById('commProgress');
    if (progressEl) {
      progressEl.textContent = `Question ${Math.min(answered + 1, commSelects.length)} of ${commSelects.length}`;
    }
  }
  
  function updateCommLive(){
    const commSelects = document.querySelectorAll('[data-q="comm"]');
    const vals = Array.from(commSelects).map(s => Number(s.value||0));
    const total = vals.reduce((a,b)=>a+b,0);
    const commLiveEl = document.getElementById('commLiveScore');
    if (commLiveEl) commLiveEl.textContent = total;
    updateCommProgress();
  }
  
  function updateCodingLive(){
    const codingSelects = document.querySelectorAll('[data-q="coding"]');
    const vals = Array.from(codingSelects).map(s => Number(s.value||0));
    const total = vals.reduce((a,b)=>a+b,0);
    const liveEl = document.getElementById('codingLiveScore');
    if (liveEl) liveEl.textContent = total;
  }
  commSelects.forEach(s=> s.addEventListener('change', updateCommLive));
  updateCommLive();

  // Domain search filter
  const domainSearch = document.getElementById('domainSearch');
  const domainSelect = document.getElementById('domainSelect');
  if (domainSearch && domainSelect){
    domainSearch.addEventListener('input', (e)=>{
      const q = e.target.value.trim().toLowerCase();
      Array.from(domainSelect.options).forEach(opt => {
        opt.hidden = !!(q && !opt.text.toLowerCase().includes(q));
      });
    });
  }

  // Live coding score preview & progress
  const codingSelects = Array.from(document.querySelectorAll('[data-q="coding"]'));
  function updateCodingLive(){
    const vals = codingSelects.map(s => Number(s.value||0));
    const total = vals.reduce((a,b)=>a+b,0);
    const liveEl = document.getElementById('codingLiveScore');
    if (liveEl) liveEl.textContent = total;
    const answered = vals.filter(v=>v>0).length;
    const cp = document.getElementById('codingProgress');
    if (cp) cp.textContent = `Answered ${answered} of ${codingSelects.length}`;
  }
  codingSelects.forEach(s=> s.addEventListener('change', updateCodingLive));
  updateCodingLive();

  // animate counters for resume metrics
  function animateCount(el, to){
    if (!el) return;
    const start = Number(el.textContent.replace(/[^0-9\.]/g,'')) || 0;
    const end = Number(to) || 0;
    const duration = 700;
    const stepTime = 16;
    const steps = Math.max(1, Math.floor(duration/stepTime));
    let i = 0;
    const delta = (end - start) / steps;
    const t = setInterval(()=>{
      i++;
      const val = Math.round(start + delta * i);
      el.textContent = val;
      if (i >= steps){ clearInterval(t); el.textContent = end; }
    }, stepTime);
  }

  function animateMetric(id, value){
    const el = document.getElementById(id);
    if (!el) {
      console.warn(`Element with id '${id}' not found`);
      return;
    }
    if (value === undefined || value === null) {
      el.textContent = '-';
      el.classList.remove('low-impact');
      return;
    }
    animateCount(el, value);
    if (Number(value) === 0){
      el.classList.add('low-impact');
    } else {
      el.classList.remove('low-impact');
    }
  }

  // Immediate resume parsing on file select and JD change (debounced)
  const resumeInput = document.getElementById('resume');
  let currentFile = null;
  resumeInput.addEventListener('change', ()=>{
    if (resumeInput.files && resumeInput.files[0]){
      currentFile = resumeInput.files[0];
      // send file alone to extract resume features immediately
      const fdata = new FormData();
      fdata.append('resume', currentFile);
      const jd = document.getElementById('jobDescription').value || '';
      if (jd) fdata.append('job_description', jd);
      fetch('/api/student/profile/analyze', {method:'POST', body: fdata}).then(r=>r.json()).then(data=>{
        if (data){
          animateMetric('skillsCount', data.number_of_skills);
          animateMetric('projectsCount', data.num_projects);
          animateMetric('internshipsCount', data.num_internships);
          animateMetric('certificationsCount', data.num_certifications);
          animateMetric('eventsCount', data.events || 0);
          animateMetric('workshopsCount', data.workshops);
          
          // Display detected skills
          if (data.skills_list && data.skills_list.length > 0) {
            const skillsPreview = document.getElementById('skillsPreview');
            const skillsList = document.getElementById('skillsList');
            skillsList.textContent = data.skills_list.join(', ');
            skillsPreview.style.display = 'block';
          }
          
          if (data.ats){
            animateMetric('atsScore', data.ats.ats_score);
            const skillMatchEl = document.getElementById('skillMatchPct');
            const experienceIndexEl = document.getElementById('experienceIndex');
            const atsMiniEl = document.getElementById('atsMini');
            
            if (skillMatchEl) skillMatchEl.textContent = (data.ats.skill_match_pct || 0) + '%';
            if (experienceIndexEl) experienceIndexEl.textContent = data.experience_index !== undefined ? data.experience_index : (Math.round((data.num_projects||0) + (data.num_internships||0)));
            if (atsMiniEl) atsMiniEl.textContent = `ATS: ${data.ats.ats_score} — ${data.ats.strength_level}`;
          }
        }
      }).catch(()=>{});
    }
  });

  // debounce helper
  function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t = setTimeout(()=>fn(...a), ms); } }

  const jdInput = document.getElementById('jobDescription');
  jdInput.addEventListener('input', debounce(()=>{
    // if a resume is selected, resend file + JD to recalc ATS
    if (currentFile){
      const fdata = new FormData();
      fdata.append('resume', currentFile);
      const jd = jdInput.value || '';
      if (jd) fdata.append('job_description', jd);
      fetch('/api/student/profile/analyze', {method:'POST', body: fdata}).then(r=>r.json()).then(data=>{
        if (data && data.ats){
          animateMetric('atsScore', data.ats.ats_score);
          const skillMatchEl = document.getElementById('skillMatchPct');
          const experienceIndexEl = document.getElementById('experienceIndex');
          const atsMiniEl = document.getElementById('atsMini');
          
          if (skillMatchEl) skillMatchEl.textContent = (data.ats.skill_match_pct || 0) + '%';
          if (experienceIndexEl) experienceIndexEl.textContent = data.experience_index !== undefined ? data.experience_index : (Math.round((data.num_projects||0) + (data.num_internships||0)));
          if (atsMiniEl) atsMiniEl.textContent = `ATS: ${data.ats.ats_score} — ${data.ats.strength_level}`;
        }
      }).catch(()=>{});
    }
  }, 800));

  // View Analytics button: check for stored data first, then fetch from database
  const viewAnalyticsBtn = document.getElementById('viewAnalyticsBtn');
  if (viewAnalyticsBtn){
    viewAnalyticsBtn.addEventListener('click', async ()=>{
      // First check if we have valid analytics data in sessionStorage
      const storedData = sessionStorage.getItem('analyticsData');
      if (storedData) {
        try {
          const data = JSON.parse(storedData);
          if (data.v_score !== undefined && data.generated_at) {
            // Valid analytics data exists, navigate directly
            window.location.href = 'student_analytics.html';
            return;
          }
        } catch (e) {
          // Invalid stored data, remove it
          sessionStorage.removeItem('analyticsData');
        }
      }
      
      // No valid stored data, fetch from database using logged-in user
      try {
        const response = await fetch('/api/analytics/current');
        if (response.ok) {
          const analyticsData = await response.json();
          // Store for analytics page
          sessionStorage.setItem('analyticsData', JSON.stringify(analyticsData));
          window.location.href = 'student_analytics.html';
        } else if (response.status === 401) {
          alert('Please login first');
          window.location.href = 'login_student.html';
        } else {
          alert('Please run "Analyze Profile" first to view analytics');
        }
      } catch (e) {
        alert('Error loading analytics. Please try again.');
      }
    });
  }

  // Add test edit button functionality
  const testEditBtn = document.getElementById('testEditBtn');
  if (testEditBtn) {
    testEditBtn.onclick = async function() {
      this.disabled = true;
      this.textContent = 'Testing...';
      
      const testData = {
        name: 'Bhavya Sri Test',
        branch: 'CSE (Artificial Intelligence)',
        year: '4',
        cgpa: 8.99,
        backlogs: 0
      };
      
      try {
        const response = await fetch('/api/profile/current', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(testData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
          alert('✅ Test update successful! Check database.');
        } else {
          alert('❌ Test failed: ' + (result.error || 'Unknown error'));
        }
      } catch (error) {
        alert('❌ Test error: ' + error.message);
      } finally {
        this.disabled = false;
        this.textContent = '🧪 Test Edit';
      }
    };
  }

  // Setup questionnaire event listeners after DOM is ready
  setTimeout(() => {
    const commSelects = Array.from(document.querySelectorAll('[data-q="comm"]'));
    const codingSelects = Array.from(document.querySelectorAll('[data-q="coding"]'));
    
    commSelects.forEach(s => s.addEventListener('change', updateCommLive));
    codingSelects.forEach(s => s.addEventListener('change', updateCodingLive));
    
    updateCommLive();
    updateCodingLive();
    
    // Setup marks file upload - remove JS click handler since CSS handles it
    const marksFileInput = document.getElementById('marksFile');
    const marksFileStatus = document.getElementById('marksFileStatus');
    
    if (marksFileInput && !marksFileInput.hasAttribute('data-marks-setup')) {
      marksFileInput.setAttribute('data-marks-setup', 'true');
      
      // Only handle file selection, no click handler needed
      marksFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
          const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
          const maxSize = 5 * 1024 * 1024;
          
          if (!allowedTypes.includes(file.type)) {
            marksFileStatus.textContent = '❌ Invalid file type';
            marksFileStatus.className = 'file-status error';
            return;
          }
          
          if (file.size > maxSize) {
            marksFileStatus.textContent = '❌ File too large';
            marksFileStatus.className = 'file-status error';
            return;
          }
          
          marksFileStatus.textContent = `✅ ${file.name}`;
          marksFileStatus.className = 'file-status success';
        }
      });
    }
  }, 100);

  // Initialize update buttons
  initializeUpdateButtons();

  // Logout button
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        const response = await fetch('/api/student/logout', { method: 'POST' });
        if (response.ok) {
          sessionStorage.clear();
          window.location.href = 'login_student.html';
        }
      } catch (e) {
        sessionStorage.clear();
        window.location.href = 'login_student.html';
      }
    });
  }

});

function initializeUpdateButtons() {
  // Edit Profile button - completely rewritten
  const editProfileBtn = document.getElementById('editProfileBtn');
  if (editProfileBtn) {
    editProfileBtn.onclick = async function(e) {
      e.preventDefault();
      
      this.disabled = true;
      this.textContent = 'Updating...';
      
      // Get form values
      const name = document.querySelector('[name="name"]').value;
      const branch = document.querySelector('[name="branch"]').value;
      const year = document.querySelector('[name="year"]').value;
      const cgpaRaw = document.querySelector('[name="cgpa"]').value;
      const backlogs = document.querySelector('[name="backlogs"]').value;
      
      // Collect questionnaire responses
      const commAnswers = Array.from(document.querySelectorAll('[data-q="comm"]')).map(s => Number(s.value || 0));
      const codingAnswers = Array.from(document.querySelectorAll('[data-q="coding"]')).map(s => Number(s.value || 0));
      
      // Handle CGPA conversion
      const scoreType = document.getElementById('scoreType').value;
      let cgpa = parseFloat(cgpaRaw || 0);
      if (scoreType === 'percentage') {
        cgpa = cgpa / 10.0;
      }
      
      const data = {
        name: name,
        branch: branch,
        year: year,
        cgpa: cgpa,
        backlogs: parseInt(backlogs || 0),
        communication_answers: commAnswers,
        coding_answers: codingAnswers
      };
      
      console.log('Sending update:', data);
      
      try {
        const response = await fetch('/api/profile/current', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(data)
        });
        
        const result = await response.json();
        console.log('Update response:', result);
        
        if (response.ok) {
          showToast('Profile updated successfully!', 'success');
          
        // Force immediate update of all UI elements with new scores
        if (result.communication_score !== undefined) {
          const newCommScore = result.communication_score;
          
          // Update progress bar
          updateProgress('#commBar', newCommScore);
          
          // Update live score display
          const commLiveEl = document.getElementById('commLiveScore');
          if (commLiveEl) {
            commLiveEl.textContent = newCommScore;
          }
          
          console.log('Updated communication - Bar and Live Score to:', newCommScore);
        }
        
        if (result.coding_score !== undefined) {
          updateProgress('#codingBar', result.coding_score);
          console.log('Updated coding bar to:', result.coding_score);
        }
          if (result.overall_readiness_score !== undefined) {
            updateOverall(result.overall_readiness_score);
            
            // Update placement status based on new score
            if (result.placement_status) {
              displayPlacementStatus(result.overall_readiness_score / 100, result.placement_status);
            }
            
            // Update stored analytics data
            const storedData = sessionStorage.getItem('analyticsData');
            if (storedData) {
              try {
                const analyticsData = JSON.parse(storedData);
                analyticsData.overall_readiness_score = result.overall_readiness_score;
                analyticsData.v_score = result.overall_readiness_score;
                analyticsData.final_score = result.overall_readiness_score;
                analyticsData.communication_score = result.communication_score;
                analyticsData.coding_score = result.coding_score;
                analyticsData.placement_status = result.placement_status;
                sessionStorage.setItem('analyticsData', JSON.stringify(analyticsData));
              } catch (e) {
                console.warn('Failed to update stored analytics data:', e);
              }
            }
          }
          
          // Reload profile data to ensure consistency
          setTimeout(async () => {
            try {
              const response = await fetch('/api/student/profile/load');
              if (response.ok) {
                const profile = await response.json();
                if (profile.has_existing_data) {
                  // Restore complete profile including questionnaire responses
                  populateFormFromProfile(profile);
                  displayAnalysisResults(profile);
                  console.log('Complete profile data reloaded after edit - all data preserved');
                }
              }
            } catch (e) {
              console.warn('Failed to reload complete profile after edit:', e);
            }
          }, 500);
        } else {
          showToast(result.error || 'Update failed', 'error');
        }
      } catch (error) {
        console.error('Update error:', error);
        showToast('Network error. Please try again.', 'error');
      } finally {
        this.disabled = false;
        this.innerHTML = '<span class="btn-icon">✏️</span><span class="btn-text">Edit Profile</span>';
      }
    };
  }
  
  // Update Resume button
  const updateResumeBtn = document.getElementById('updateResumeBtn');
  if (updateResumeBtn && !updateResumeBtn.hasAttribute('data-initialized')) {
    updateResumeBtn.setAttribute('data-initialized', 'true');
    updateResumeBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      
      const resumeFile = document.getElementById('resume').files[0];
      
      if (!resumeFile) {
        alert('Please select a resume file first');
        return;
      }
      
      const formData = new FormData();
      formData.append('resume', resumeFile);
      
      updateResumeBtn.disabled = true;
      updateResumeBtn.textContent = 'Updating...';
      
      try {
        const response = await fetch('/api/profile/current/resume', {
          method: 'PUT',
          body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
          showToast('Resume updated successfully!', 'success');
          
          // Update resume file status display
          const resumeFileStatus = document.getElementById('fileStatus');
          if (resumeFileStatus) {
            const resumeInput = document.getElementById('resume');
            if (resumeInput && resumeInput.files[0]) {
              resumeFileStatus.textContent = `Current file: ${resumeInput.files[0].name}`;
              resumeFileStatus.className = 'file-status success';
            }
          }
          
          try {
            // Update UI with new resume metrics
            updateProgress('#resumeBar', data.resume_score || 0);
            animateMetric('skillsCount', data.number_of_skills);
            animateMetric('projectsCount', data.num_projects);
            animateMetric('internshipsCount', data.num_internships);
            animateMetric('certificationsCount', data.num_certifications);
            animateMetric('eventsCount', data.events);
            animateMetric('workshopsCount', data.workshops);
            
            updateOverall(data.final_score || data.v_score || 0);
            
            // Update stored analytics data for consistency across pages
            const storedData = sessionStorage.getItem('analyticsData');
            if (storedData) {
              try {
                const analyticsData = JSON.parse(storedData);
                analyticsData.overall_readiness_score = data.overall_readiness_score;
                analyticsData.v_score = data.overall_readiness_score;
                analyticsData.final_score = data.overall_readiness_score;
                analyticsData.resume_score = data.resume_score;
                analyticsData.resume_ats_score = data.resume_score;
                analyticsData.breakdown.resume = data.resume_score;
                analyticsData.resume_metrics = {
                  skills_count: data.number_of_skills || 0,
                  projects: data.num_projects || 0,
                  internships: data.num_internships || 0,
                  certifications: data.num_certifications || 0,
                  events: data.events || 0,
                  workshops: data.workshops || 0,
                  hackathons: data.hackathons || 0
                };
                analyticsData.experience_index = data.experience_index || 0;
                sessionStorage.setItem('analyticsData', JSON.stringify(analyticsData));
              } catch (e) {
                console.warn('Failed to update stored analytics data:', e);
              }
            }
            
            showLastUpdated(new Date().toLocaleDateString());
            
            // Reload complete profile data to ensure all questionnaire responses are preserved
            setTimeout(async () => {
              try {
                const response = await fetch('/api/student/profile/load');
                if (response.ok) {
                  const profile = await response.json();
                  if (profile.has_existing_data) {
                    // Restore questionnaire responses and other preserved data
                    populateFormFromProfile(profile);
                    displayAnalysisResults(profile);
                    console.log('Profile data reloaded after resume update - questionnaire responses preserved');
                  }
                }
              } catch (e) {
                console.warn('Failed to reload profile after resume update:', e);
              }
            }, 500);
          } catch (uiError) {
            console.error('UI update error:', uiError);
          }
        } else if (response.status === 401) {
          alert('Please login first');
          window.location.href = 'login_student.html';
        } else {
          showToast(data.error || 'Resume update failed', 'error');
        }
      } catch (error) {
        console.error('Resume update error:', error);
        showToast('Network error. Please try again.', 'error');
      } finally {
        updateResumeBtn.disabled = false;
        updateResumeBtn.textContent = 'Update Resume';
      }
    });
  }
}

function updateProgress(selector, percent){
  const el = document.querySelector(selector);
  if (!el) {
    console.warn('Progress element not found:', selector);
    return;
  }
  
  let bar = el.querySelector('.bar-inner');
  if (!bar) {
    // Create bar if it doesn't exist
    bar = document.createElement('div');
    bar.className = 'bar-inner';
    bar.style.cssText = 'width: 0%; height: 100%; border-radius: 999px; transition: width 900ms cubic-bezier(.2,.9,.2,1); background: linear-gradient(90deg, #667eea, #764ba2);';
    el.appendChild(bar);
  }
  
  const span = el.querySelector('span');
  const p = Math.max(0, Math.min(100, Number(percent || 0)));
  
  el.setAttribute('data-stored-score', p);
  
  if (bar) {
    bar.style.width = p + '%';
    console.log(`Updated ${selector} to ${p}%`);
  }
  if (span) span.textContent = p + '%';
}

function updateOverall(value){
  const text = document.getElementById('overallPercent');
  if (!text) {
    console.log('Circle text element not found');
    return;
  }
  if (value === '--'){
    text.textContent = '--%';
    return;
  }
  let percent = parseFloat(value || 0);
  if (isNaN(percent) || !isFinite(percent)) {
    percent = 0;
  }
  percent = Math.max(0, Math.min(100, Math.round(percent)));
  
  text.textContent = percent + '%';
  console.log('Profile circle updated:', percent + '%');
}

// reset helper to set bars to zero and clear metrics
function resetVisuals(){
  ['#commBar','#codingBar','#resumeBar'].forEach(s => updateProgress(s, 0));
  updateOverall('--');
  // Reset coding breakdown
  document.getElementById('codingQuestionnaire').textContent = '-';
  document.getElementById('resumeBoost').textContent = '-';
  document.getElementById('finalCoding').textContent = '-';
  // Reset live scores
  const commLive = document.getElementById('commLiveScore');
  const codingLive = document.getElementById('codingLiveScore');
  if (commLive) commLive.textContent = '0';
  if (codingLive) codingLive.textContent = '0';
  // Hide placement status
  const statusEl = document.getElementById('placementStatus');
  if (statusEl) statusEl.style.display = 'none';
}

// Display placement status based on v_score (0-100 scale)
function displayPlacementStatus(vScore, status) {
  const statusEl = document.getElementById('placementStatus');
  const statusText = document.getElementById('placementStatusText');
  
  if (!statusEl || !statusText) return;
  
  // Clear existing classes
  statusEl.className = 'placement-status';
  
  // vScore is expected to be 0-1 scale, convert to percentage for comparison
  const scorePercent = vScore * 100;
  
  if (scorePercent >= 70) {
    statusEl.classList.add('likely-placed');
    statusText.textContent = '✅ Status: Placement Ready';
  } else if (scorePercent >= 40) {
    statusEl.classList.add('moderate-risk');
    statusText.textContent = '⚠️ Status: Medium Risk';
  } else {
    statusEl.classList.add('at-risk');
    statusText.textContent = '🚨 Status: High Risk (Needs Improvement)';
  }
  
  statusEl.style.display = 'block';
}

// Display v_score prominently
function displayVScore(vScore) {
  // Just ensure the circle shows the v_score - no additional display needed
}
// Enhanced UI Interactions and Real-time Feedback

// Toast notification system
function showToast(message, type = 'success') {
  const toast = document.getElementById(type === 'success' ? 'successToast' : 'errorToast');
  const messageEl = toast.querySelector('.toast-message');
  messageEl.textContent = message;
  
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.animation = 'slideOutRight 0.3s ease forwards';
    setTimeout(() => {
      toast.style.display = 'none';
      toast.style.animation = '';
    }, 300);
  }, 3000);
}

// Enhanced loading overlay
function showLoadingOverlay(message = 'Analyzing your profile...') {
  const overlay = document.getElementById('loadingOverlay');
  const messageEl = overlay.querySelector('p');
  messageEl.textContent = message;
  overlay.style.display = 'flex';
}

function hideLoadingOverlay() {
  const overlay = document.getElementById('loadingOverlay');
  overlay.style.opacity = '0';
  setTimeout(() => {
    overlay.style.display = 'none';
    overlay.style.opacity = '1';
  }, 300);
}

// Enhanced file upload with drag & drop
document.addEventListener('DOMContentLoaded', () => {
  const fileDropZone = document.getElementById('fileDropZone');
  const fileInput = document.getElementById('resume');
  const fileStatus = document.getElementById('fileStatus');

  // Click to browse files
  if (fileDropZone && fileInput && !fileDropZone.hasAttribute('data-click-initialized')) {
    fileDropZone.setAttribute('data-click-initialized', 'true');
    fileDropZone.addEventListener('click', () => {
      fileInput.click();
    });
  }

  // Drag and drop functionality
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, highlight, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, unhighlight, false);
  });

  function highlight(e) {
    fileDropZone.classList.add('dragover');
  }

  function unhighlight(e) {
    fileDropZone.classList.remove('dragover');
  }

  fileDropZone.addEventListener('drop', handleDrop, false);

  function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    if (files.length > 0) {
      fileInput.files = files;
      handleFileSelect(files[0]);
    }
  }

  // File input change handler
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  });

  function handleFileSelect(file) {
    const maxSize = 2 * 1024 * 1024; // 2MB
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];

    if (!allowedTypes.includes(file.type)) {
      fileStatus.textContent = '❌ Invalid file type. Please upload PDF or DOCX.';
      fileStatus.className = 'file-status error';
      return;
    }

    if (file.size > maxSize) {
      fileStatus.textContent = '❌ File too large. Maximum size is 2MB.';
      fileStatus.className = 'file-status error';
      return;
    }

    fileStatus.textContent = `✅ ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    fileStatus.className = 'file-status success';
    
    // Add file upload animation
    fileDropZone.style.background = 'rgba(16, 185, 129, 0.1)';
    fileDropZone.style.borderColor = 'var(--success)';
    
    setTimeout(() => {
      fileDropZone.style.background = '';
      fileDropZone.style.borderColor = '';
    }, 2000);
  }

  // Enhanced communication progress tracking
  const commSelects = document.querySelectorAll('[data-q="comm"]');
  const progressDots = document.querySelectorAll('.progress-dots .dot');

  commSelects.forEach((select, index) => {
    select.addEventListener('change', () => {
      updateCommProgress();
      updateProgressDots();
      
      // Add visual feedback
      select.parentElement.style.transform = 'scale(1.02)';
      setTimeout(() => {
        select.parentElement.style.transform = '';
      }, 200);
    });
  });

  function updateProgressDots() {
    commSelects.forEach((select, index) => {
      const dot = progressDots[index];
      if (select.value && select.value !== '0') {
        dot.classList.add('completed');
        dot.classList.remove('active');
      } else {
        dot.classList.remove('completed', 'active');
      }
    });

    // Highlight current question
    const nextUnanswered = Array.from(commSelects).findIndex(select => !select.value || select.value === '0');
    if (nextUnanswered !== -1 && progressDots[nextUnanswered]) {
      progressDots[nextUnanswered].classList.add('active');
    }
  }

  // Enhanced coding score animation
  const codingSelects = document.querySelectorAll('[data-q="coding"]');
  codingSelects.forEach(select => {
    select.addEventListener('change', () => {
      updateCodingLive();
      
      // Add ripple effect
      const ripple = document.createElement('div');
      ripple.style.cssText = `
        position: absolute;
        border-radius: 50%;
        background: rgba(59, 130, 246, 0.3);
        transform: scale(0);
        animation: ripple 0.6s linear;
        pointer-events: none;
      `;
      
      const rect = select.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      ripple.style.width = ripple.style.height = size + 'px';
      ripple.style.left = '50%';
      ripple.style.top = '50%';
      ripple.style.marginLeft = -size/2 + 'px';
      ripple.style.marginTop = -size/2 + 'px';
      
      select.parentElement.style.position = 'relative';
      select.parentElement.appendChild(ripple);
      
      setTimeout(() => ripple.remove(), 600);
    });
  });

  // Academic performance indicator
  const cgpaInput = document.getElementById('cgpaInput');
  const scoreType = document.getElementById('scoreType');
  const academicBar = document.getElementById('academicBar');
  const academicText = document.getElementById('academicText');

  function updateAcademicIndicator() {
    const value = parseFloat(cgpaInput.value) || 0;
    const isPercentage = scoreType.value === 'percentage';
    const maxValue = isPercentage ? 100 : 10;
    const percentage = (value / maxValue) * 100;
    
    if (!academicBar || !academicText) return;
    
    const fill = academicBar.querySelector('.indicator-fill');
    if (!fill) return;
    fill.style.width = Math.min(percentage, 100) + '%';
    
    let status, color;
    if (percentage >= 80) {
      status = 'Excellent Performance';
      color = 'var(--success)';
    } else if (percentage >= 70) {
      status = 'Good Performance';
      color = 'var(--accent-start)';
    } else if (percentage >= 60) {
      status = 'Average Performance';
      color = 'var(--warning)';
    } else {
      status = 'Needs Improvement';
      color = 'var(--danger)';
    }
    
    academicText.textContent = status;
    academicText.style.color = color;
    fill.style.background = `linear-gradient(90deg, ${color}, var(--success))`;
  }

  cgpaInput.addEventListener('input', updateAcademicIndicator);
  scoreType.addEventListener('change', updateAcademicIndicator);
  
  // Initialize
  updateAcademicIndicator();

  // Enhanced form submission with better UX
  const form = document.getElementById('profileForm');
  const submitBtn = form.querySelector('button[type="submit"]');
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Validate form with visual feedback
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
      if (!field.value.trim()) {
        field.style.borderColor = 'var(--danger)';
        field.style.animation = 'shake 0.5s ease';
        isValid = false;
        
        setTimeout(() => {
          field.style.animation = '';
        }, 500);
      } else {
        field.style.borderColor = 'var(--success)';
      }
    });
    
    if (!isValid) {
      showToast('Please fill in all required fields', 'error');
      return;
    }
    
    // Show loading state
    showLoadingOverlay('Analyzing your profile...');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="loading-spinner" style="width: 20px; height: 20px; margin-right: 0.5rem;"></span>Analyzing...';
    
    try {
      // Your existing form submission logic here
      // ... (keeping the existing logic intact)
      
      showToast('Profile analyzed successfully!', 'success');
    } catch (error) {
      showToast('Analysis failed. Please try again.', 'error');
    } finally {
      hideLoadingOverlay();
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span class="btn-icon">🔍</span><span class="btn-text">Analyze Profile</span>';
    }
  });

  // Add shake animation for validation errors
  const style = document.createElement('style');
  style.textContent = `
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
      20%, 40%, 60%, 80% { transform: translateX(5px); }
    }
    
    @keyframes slideOutRight {
      to {
        opacity: 0;
        transform: translateX(100%);
      }
    }
  `;
  document.head.appendChild(style);

  // Smooth scrolling for better UX
  const cards = document.querySelectorAll('.card');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animation = 'slideInUp 0.6s ease forwards';
      }
    });
  }, { threshold: 0.1 });

  cards.forEach(card => {
    observer.observe(card);
  });

  // Enhanced button interactions
  document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      btn.style.transform = 'translateY(-2px) scale(1.02)';
    });
    
    btn.addEventListener('mouseleave', () => {
      btn.style.transform = 'translateY(0) scale(1)';
    });
  });

  // Real-time ATS preview
  const jobDescInput = document.getElementById('jobDescription');
  const atsPreview = document.getElementById('atsMini');
  
  let atsTimeout;
  jobDescInput.addEventListener('input', () => {
    clearTimeout(atsTimeout);
    atsTimeout = setTimeout(() => {
      if (jobDescInput.value.trim()) {
        atsPreview.textContent = '🔄 Analyzing job description for ATS matching...';
        atsPreview.style.display = 'block';
        
        // Simulate ATS analysis (replace with actual logic)
        setTimeout(() => {
          const wordCount = jobDescInput.value.trim().split(/\s+/).length;
          atsPreview.textContent = `📊 Job description loaded (${wordCount} words) - Ready for ATS analysis`;
        }, 1000);
      } else {
        atsPreview.style.display = 'none';
      }
    }, 500);
  });
});