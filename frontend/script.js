// Landing page role card redirects
document.addEventListener('DOMContentLoaded', function(){
	document.querySelectorAll('button[data-target]').forEach(btn => {
		btn.addEventListener('click', () => {
			const t = btn.getAttribute('data-target');
			if(t === 'student') window.location.href = 'login_student.html';
			if(t === 'tpo') window.location.href = 'login_tpo.html';
		});
	});

	// Sidebar toggle (used on student & tpo pages)
	const toggle = document.getElementById('sidebarToggle');
	const toggleTpo = document.getElementById('sidebarToggleTpo');
	function bindToggle(elId){
		const btn = document.getElementById(elId);
		const sidebar = document.getElementById('sidebar');
		if(btn && sidebar){
			btn.addEventListener('click', ()=>{
				sidebar.classList.toggle('collapsed');
			});
		}
	}
	if(toggle) bindToggle('sidebarToggle');
	if(toggleTpo) bindToggle('sidebarToggleTpo');
});

