document.addEventListener('DOMContentLoaded', ()=>{
  const backBtn = document.getElementById('backBtn');
  backBtn?.addEventListener('click', ()=> {
    // Get student ID from analytics data and pass it to profile page
    const raw = sessionStorage.getItem('analyticsData');
    if (raw) {
      try {
        const data = JSON.parse(raw);
        const studentId = data.roll_no || data.register_number;
        if (studentId) {
          // Store student ID for profile page to load
          sessionStorage.setItem('loadStudentId', studentId);
        }
      } catch(e) {}
    }
    window.location.href = 'student_profile.html';
  });

  const raw = sessionStorage.getItem('analyticsData');
  if (!raw){
    // no analytics available
    const container = document.querySelector('.analytics-container');
    const noDataDiv = document.createElement('div');
    noDataDiv.style.cssText = 'padding:24px;background:#fff;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.04)';
    
    const heading = document.createElement('h3');
    heading.textContent = 'No analytics available';
    
    const para1 = document.createElement('p');
    para1.textContent = 'Please run "Analyze Profile" in your profile page (upload resume if needed) and then click "View My Analytics".';
    
    const para2 = document.createElement('p');
    para2.style.marginTop = '12px';
    
    const button = document.createElement('button');
    button.className = 'btn';
    button.textContent = 'Go to Profile';
    button.onclick = () => window.location.href = 'student_profile.html';
    
    para2.appendChild(button);
    noDataDiv.appendChild(heading);
    noDataDiv.appendChild(para1);
    noDataDiv.appendChild(para2);
    container.appendChild(noDataDiv);
    return;
  }

  let data;
  try{ data = JSON.parse(raw); }catch(e){ sessionStorage.removeItem('analyticsData'); location.reload(); return; }

  // DEBUG: Log CGPA data flow
  console.log('Analytics Data CGPA Debug:', {
    'data.cgpa': data.cgpa,
    'data.form_data?.cgpa': data.form_data?.cgpa,
    'Full data keys': Object.keys(data)
  });

  // ANALYTICS PAGE IS READ-ONLY - USE EXACT VALUES FROM STORED DATA
  
  // Use exact stored v_score - NO modifications
  let overall = parseFloat(data.v_score);
  if (isNaN(overall)) {
    console.error('No valid v_score in analytics data:', data.v_score);
    overall = 0;
  }
  
  console.log('Analytics displaying ML v_score:', overall);
  
  const text = document.getElementById('overallPercent');
  if (text) {
    text.textContent = overall + '%';
    console.log('Analytics circle updated:', overall + '%');
  }

  // Use exact stored v_score with null checks
  const metaCgpa = document.getElementById('metaCgpa');
  const metaCoding = document.getElementById('metaCoding');
  const metaComm = document.getElementById('metaComm');
  
  if (metaCgpa) metaCgpa.textContent = data.cgpa || '-';
  if (metaCoding) metaCoding.textContent = `${data.breakdown?.coding || '-'}%`;
  if (metaComm) metaComm.textContent = `${data.breakdown?.communication || '-'}%`;
  
  // Display ML score in meta section
  const mlScoreDisplay = document.getElementById('mlScoreDisplay');
  if (mlScoreDisplay) mlScoreDisplay.textContent = overall + '%';

  // animate bars - use exact breakdown values with null checks
  const breakdown = data.breakdown || {};
  const keys = Object.keys(breakdown);
  keys.forEach(k=>{
    const bar = document.querySelector(`.bar[data-key="${k}"]`);
    if (!bar) return;
    const v = Math.max(0, Math.min(100, Number(breakdown[k] || 0)));
    const fill = bar.querySelector('.bar-fill');
    const label = bar.querySelector('.bar-value');
    if (fill && label) {
      setTimeout(()=>{ 
        fill.style.width = v + '%'; 
        label.textContent = v + '%'; 
      }, 120);
    }
  });

  // resume insights - use exact stored values with null checks
  const resumeMetrics = data.resume_metrics || {};
  const insSkills = document.getElementById('insSkills');
  const insProjects = document.getElementById('insProjects');
  const insInternships = document.getElementById('insInternships');
  const insCerts = document.getElementById('insCerts');
  const insWorkshops = document.getElementById('insWorkshops');
  const insHackathons = document.getElementById('insHackathons');
  const insAtsScore = document.getElementById('insAtsScore');
  const insExperienceIndex = document.getElementById('insExperienceIndex');
  
  if (insSkills) insSkills.textContent = resumeMetrics.skills_count ?? '-';
  if (insProjects) insProjects.textContent = resumeMetrics.projects ?? '-';
  if (insInternships) insInternships.textContent = resumeMetrics.internships ?? '-';
  if (insCerts) insCerts.textContent = resumeMetrics.certifications ?? '-';
  if (insWorkshops) insWorkshops.textContent = resumeMetrics.workshops ?? '-';
  if (insHackathons) insHackathons.textContent = resumeMetrics.hackathons ?? '-';
  if (insAtsScore) insAtsScore.textContent = resumeMetrics.ats_score ?? '-';
  if (insExperienceIndex) insExperienceIndex.textContent = data.experience_index ?? '-';

  // Build doughnut chart for resume distribution (Chart.js)
  try{
    const labels = ['Skills','Projects','Internships','Certifications','Workshops','Hackathons','ATS Score','Experience'];
    const values = [
      Number(data.resume_metrics?.skills_count || 0),
      Number(data.resume_metrics?.projects || 0),
      Number(data.resume_metrics?.internships || 0),
      Number(data.resume_metrics?.certifications || 0),
      Number(data.resume_metrics?.workshops || 0),
      Number(data.resume_metrics?.hackathons || 0),
      Number(data.resume_metrics?.ats_score || 0),
      Number(data.experience_index || 0)
    ];
    const total = values.reduce((a,b)=>a+b,0);
    const colors = ['#f45ca8','#10b981','#f59e0b','#06b6d4','#7c3aed','#65ea9d','#b3f65c','#252dc7'];
    const ctx = document.getElementById('resumeDoughnut');

if (ctx && typeof Chart !== 'undefined') {
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#ffffff',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,   // ✅ KEY FIX
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            boxWidth: 18,
            padding: 14
          }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const pct = total ? Math.round((ctx.parsed / total) * 100) : 0;
              return `${ctx.label}: ${ctx.parsed} (${pct}%)`;
            }
          }
        }
      },
      animation: {
        duration: 900
      }
    }
  });
}
  }catch(e){console.warn('Chart error', e)}

  // Experience Composition Index - use stored value if available
  const expIndex = data.experience_index || 0;
  const expValEl = document.getElementById('expVal');
  const fill = document.getElementById('expBarFill');
  if (expValEl) expValEl.textContent = expIndex;
  const percent = Math.max(0, Math.min(100, Math.round((expIndex / 10) * 100)));
  if (fill) setTimeout(()=> fill.style.width = percent + '%', 120);

  // strengths & improvements (rules) - use v_score as single source
  const strengths = [];
  const improvements = [];
  const b = data.breakdown || {};
  const r = data.resume_metrics || {};
  const vScore = data.v_score || data.overall_readiness || 0;

  if ((b.coding || 0) >= 75) strengths.push('Strong technical foundation');
  else if ((b.coding||0) >= 50) strengths.push('Decent coding readiness');
  else improvements.push('Work on coding - practice DSA & projects');

  if ((b.communication||0) >= 65) strengths.push('Good communication readiness');
  else improvements.push('Improve communication & interview practice');

  if (vScore >= 70) strengths.push('Balanced academic & skill performance');
  else improvements.push('Enhance overall profile readiness');

  if ((b.resume || 0) >= 75) strengths.push('Well-optimized resume');
  else if ((b.resume || 0) < 60) improvements.push('Optimize resume');


  if ((r.skills_count || 0) >= 6) strengths.push('Diverse technical skills listed');
  else improvements.push('Increase number of listed technical skills');
  
  if ((r.projects || 0) >= 2) strengths.push('Hands-on project experience');
  else improvements.push('Add more projects to showcase skills');

  if ((r.internships || 0) >= 1) strengths.push('Real-world internship exposure');
  else improvements.push('Gain internship experience');

  if ((r.certifications || 0) >= 2) strengths.push('Relevant certifications acquired');
  else improvements.push('Obtain more industry-relevant certifications');

  if ((r.workshops || 0) >= 2) strengths.push('Active participation in workshops');
  else improvements.push('Attend more skill-building workshops');

  if ((r.hackathons || 0) >= 1) strengths.push('Experience from hackathons/competitions');
  else improvements.push('Participate in hackathons or competitions');

  if ((data.resume_metrics?.ats_score || 0) >= 60) strengths.push('Good resume ATS alignment');
  else improvements.push('Improve resume ATS alignment (keywords, formatting)');

  if (data.experience_index >= 7) strengths.push('Strong experience profile');
  else improvements.push('Build a stronger experience profile');

  if ((data.cgpa || 0) < 6 || (data.backlogs || 0) > 2) {
    improvements.push('Focus on academics - improve CGPA and clear backlogs');
  }


  const strengthsList = document.getElementById('strengthsList');
  const improveList = document.getElementById('improveList');
  strengths.forEach(s=>{ 
    const d = document.createElement('div'); 
    d.className='pill'; 
    d.textContent = '✓ ' + s; 
    d.setAttribute('role', 'listitem');
    strengthsList.appendChild(d); 
  });
  
  improvements.forEach(s=>{ 
    const d = document.createElement('div'); 
    d.className='pill'; 
    d.textContent = '⚠ ' + s; 
    d.setAttribute('role', 'listitem');
    improveList.appendChild(d); 
  });

  // personalized recommendations (simple rule-based)
  const recsEl = document.getElementById('recs');
  const recs = [];
  const pref = (data.preferred_domain || '').toLowerCase();
  /*if (pref.includes('ai') || pref.includes('machine') || (data.resume_metrics?.skills_count || 0) > 10) {
    recs.push({title:'Data / ML Roles', body:'Suggested roles: ML Engineer, Data Scientist. Focus: statistics, model projects, Python, ML libraries.'});
  }
  if (pref.includes('backend') || (data.breakdown?.coding || 0) >= 70) {
    recs.push({title:'Backend Developer', body:'Suggested roles: Backend / API developer. Focus: SQL, system design, databases.'});
  }
  if (recs.length < 3) {
    recs.push({title:'Full-Stack / Software', body:'Suggested roles: Full-Stack Developer. Focus: Node/React, system design basics, portfolio projects.'});
  }*/

  // Frontend / UI Developer
  if (pref.includes('frontend') || pref.includes('ui') || pref.includes('react') || pref.includes('web')) {
    recs.push({title: 'Frontend / UI Developer',body: 'Suggested roles: Frontend Engineer, UI Developer. Focus: HTML, CSS, JavaScript, React, UI performance.'});
  }

  // Data / AI / ML Roles
  if (pref.includes('ai') || pref.includes('machine') || pref.includes('ml') || pref.includes('data')) {
    recs.push({title: 'Data / AI / ML Roles',body: 'Suggested roles: Data Analyst, ML Engineer, Data Scientist. Focus: Python, statistics, SQL, ML projects, data-driven problem solving.'});
  }

  // Backend / API / Systems Developer
  if (pref.includes('backend') || pref.includes('api') || pref.includes('server')) {
    recs.push({title: 'Backend / API Developer',body: 'Suggested roles: Backend Developer, API Engineer. Focus: SQL, databases, REST APIs, system design, performance optimization.'});
  }

  // Full-Stack / Software Engineer (Fallback)
  if (pref.includes('fullstack') || pref.includes('full-stack') || pref.includes('software') || pref.includes('web')) {
  recs.push({title: 'Full-Stack / Software Engineer',body: 'Suggested roles: Full-Stack Developer, Software Engineer. Focus: frontend + backend integration, APIs, databases, system design, portfolio projects.'});
  }

  // Cloud / DevOps Engineer
  if (pref.includes('cloud') || pref.includes('devops')){
    recs.push({title: 'Cloud / DevOps Engineer',body: 'Suggested roles: Cloud Engineer, DevOps Engineer. Focus: AWS/Azure, Docker, CI/CD, system reliability.'});
  }

  // Software Test / QA Engineer
  if (pref.includes('testing') || pref.includes('qa') || pref.includes('automation')) {
    recs.push({title: 'Software Test / QA Engineer',body: 'Suggested roles: QA Engineer, Automation Tester. Focus: test automation, debugging, quality assurance.'});
  }

  // Mobile App Developer
  if (pref.includes('mobile') || pref.includes('android') || pref.includes('ios')) {
    recs.push({title: 'Mobile App Developer',body: 'Suggested roles: Android/iOS Developer. Focus: app lifecycle, APIs, UI/UX, performance.'});
  }

  // Cybersecurity / Security Analyst
  if (pref.includes('security') || pref.includes('cyber') || pref.includes('security analyst')) {
    recs.push({title: 'Cybersecurity Analyst',body: 'Suggested roles: Security Analyst. Focus: secure coding, vulnerabilities, networks, threat analysis.'});
  }

  // Data Analyst / BI Engineer
  if (pref.includes('data') || pref.includes('analytics') || pref.includes('bi')) {
    recs.push({title: 'Data Analyst / BI Engineer',body: 'Suggested roles: Data Analyst, BI Engineer. Focus: SQL, Power BI/Tableau, data interpretation.'});
  }

  // Product / Software Analyst
  if (pref.includes('product') || pref.includes('analyst')) {
    recs.push({title: 'Product / Software Analyst',body: 'Suggested roles: Product Analyst, Software Analyst. Focus: requirements, metrics, system understanding.'});
  }

  

  // Add tailored tips about resume & skills
  //if ((data.resume_metrics?.ats_score || 0) <= 59) {
    recs.push({title:'ATS Improvement', body:'Enhance ATS score by adding relevant keywords from job descriptions, improving formatting, and including measurable achievements.'});
  //}

  

  recs.forEach(r=>{
    const el = document.createElement('div'); 
    el.className='rec';
    el.setAttribute('role', 'listitem');
    
    const title = document.createElement('div');
    title.style.fontWeight = '700';
    title.style.marginBottom = '8px';
    title.textContent = r.title;
    
    const body = document.createElement('div');
    body.style.color = 'var(--muted)';
    body.style.fontSize = '13px';
    body.textContent = r.body;
    
    el.appendChild(title);
    el.appendChild(body);
    recsEl.appendChild(el);
  });

});

// Display v_score prominently in analytics
function displayAnalyticsVScore(vScore) {
  // Just ensure the circle shows the v_score - no additional display needed
}

