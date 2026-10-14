/**
 * Interactive Before & After Image Comparison Slider
 */
function initComparisonSlider(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const overlay = container.querySelector('.comparison-overlay');
  const handle = container.querySelector('.comparison-slider-handle');

  if (!overlay || !handle) return;

  let isDragging = false;

  function moveSlider(x) {
    const rect = container.getBoundingClientRect();
    let pos = x - rect.left;
    if (pos < 0) pos = 0;
    if (pos > rect.width) pos = rect.width;

    const percentage = (pos / rect.width) * 100;
    overlay.style.width = percentage + '%';
    handle.style.left = percentage + '%';
  }

  handle.addEventListener('mousedown', () => isDragging = true);
  window.addEventListener('mouseup', () => isDragging = false);

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    moveSlider(e.clientX);
  });

  // Touch support for mobile devices
  handle.addEventListener('touchstart', () => isDragging = true);
  window.addEventListener('touchend', () => isDragging = false);

  window.addEventListener('touchmove', (e) => {
    if (!isDragging || !e.touches[0]) return;
    moveSlider(e.touches[0].clientX);
  });

  container.addEventListener('click', (e) => {
    moveSlider(e.clientX);
  });
}
