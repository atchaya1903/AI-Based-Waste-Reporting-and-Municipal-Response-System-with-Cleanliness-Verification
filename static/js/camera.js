/**
 * Live Camera Capture Module
 * Uses HTML5 getUserMedia to capture webcam images for waste reporting and cleanup verification.
 */
function initWebcamCapture(config) {
  const videoElem = document.getElementById(config.videoId);
  const canvasElem = document.getElementById(config.canvasId);
  const startBtn = document.getElementById(config.startBtnId);
  const snapBtn = document.getElementById(config.snapBtnId);
  const retakeBtn = document.getElementById(config.retakeBtnId);
  const hiddenInput = document.getElementById(config.hiddenInputId);
  const cameraBox = document.getElementById(config.cameraBoxId);
  const previewImg = document.getElementById(config.previewImgId);

  let stream = null;

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    if (startBtn) {
      startBtn.disabled = true;
      startBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Webcam not supported on this browser';
    }
    return;
  }

  // Start Camera
  if (startBtn) {
    startBtn.addEventListener('click', async function () {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
          audio: false
        });
        videoElem.srcObject = stream;
        videoElem.style.display = 'block';
        if (canvasElem) canvasElem.style.display = 'none';
        if (previewImg) previewImg.style.display = 'none';
        cameraBox.classList.remove('d-none');
        startBtn.classList.add('d-none');
        snapBtn.classList.remove('d-none');
        if (retakeBtn) retakeBtn.classList.add('d-none');
      } catch (err) {
        alert("Camera access error: " + err.message + "\nPlease grant camera permission or use the file upload option.");
      }
    });
  }

  // Snap Photo
  if (snapBtn) {
    snapBtn.addEventListener('click', function () {
      if (!stream) return;
      const width = videoElem.videoWidth || 640;
      const height = videoElem.videoHeight || 480;
      canvasElem.width = width;
      canvasElem.height = height;

      const ctx = canvasElem.getContext('2d');
      ctx.drawImage(videoElem, 0, 0, width, height);

      // Convert to JPEG Data URL
      const dataUrl = canvasElem.toDataURL('image/jpeg', 0.9);
      hiddenInput.value = dataUrl;

      // Stop camera stream to free resources
      stream.getTracks().forEach(track => track.stop());
      videoElem.style.display = 'none';

      // Show preview
      if (previewImg) {
        previewImg.src = dataUrl;
        previewImg.style.display = 'block';
      } else {
        canvasElem.style.display = 'block';
      }

      snapBtn.classList.add('d-none');
      if (retakeBtn) retakeBtn.classList.remove('d-none');
    });
  }

  // Retake Photo
  if (retakeBtn) {
    retakeBtn.addEventListener('click', function () {
      hiddenInput.value = '';
      if (previewImg) previewImg.style.display = 'none';
      if (startBtn) startBtn.click();
    });
  }
}
