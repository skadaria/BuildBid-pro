// Simple function to include HTML files into elements with 'data-include' attribute
function includeHTML() {
  const elements = document.querySelectorAll('[data-include]');
  elements.forEach(async (el) => {
    const file = el.getAttribute('data-include');
    if (file) {
      try {
        const resp = await fetch(file);
        if (resp.ok) {
          el.innerHTML = await resp.text();
        } else {
          el.innerHTML = "Include not found.";
        }
      } catch (e) {
        el.innerHTML = "Error loading include.";
      }
    }
  });
}

// Show/hide sections based on nav click
function setupNavShowHide() {
  const navLinks = document.querySelectorAll('.navbar a');
  const sections = [
    '/portfolio/includes/html_notes.html',
    '/portfolio/includes/css_notes.html',
    '/portfolio/includes/http_notes.html',
    '/portfolio/includes/dom_notes.html',
    '/portfolio/includes/javascript_notes.html',
    '/portfolio/includes/ai_notes.html',
    '/portfolio/includes/exercises.html'
  ];
  const sectionDivs = sections.map(
    file => document.querySelector(`[data-include="${file}"]`)
  );
  
  navLinks.forEach((link, idx) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      // Hide all section divs
      sectionDivs.forEach(div => { if (div) div.style.display = 'none'; });
      // Show the clicked section
      if (sectionDivs[idx]) sectionDivs[idx].style.display = '';
      // Optionally, scroll to the section
      if (sectionDivs[idx]) sectionDivs[idx].scrollIntoView({ behavior: 'smooth' });
    });
  });

  // Hide all sections except HTML on load
  sectionDivs.forEach(div => { if (div) div.style.display = 'none'; });
  if (sectionDivs[0]) sectionDivs[0].style.display = '';

}

document.addEventListener("DOMContentLoaded", () => {
  includeHTML();
  setupNavShowHide();
});