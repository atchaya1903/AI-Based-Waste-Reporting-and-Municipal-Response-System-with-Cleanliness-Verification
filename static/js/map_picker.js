/**
 * Leaflet Map Location Picker
 * Allows citizens to pick complaint coordinates on OpenStreetMap and auto-detect municipal ward.
 */
function initMapPicker(options) {
  const defaultLat = options.defaultLat || 12.9716;
  const defaultLng = options.defaultLng || 77.5946;
  const mapElementId = options.mapId || 'locationMap';

  const map = L.map(mapElementId).setView([defaultLat, defaultLng], 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors | Smart Clean Municipality'
  }).addTo(map);

  let marker = L.marker([defaultLat, defaultLng], {
    draggable: true
  }).addTo(map);

  function updateCoordinates(lat, lng) {
    const latInput = document.getElementById(options.latInputId || 'latitude');
    const lngInput = document.getElementById(options.lngInputId || 'longitude');
    if (latInput) latInput.value = lat.toFixed(6);
    if (lngInput) lngInput.value = lng.toFixed(6);

    // Call auto-ward lookup API
    const categorySelect = document.getElementById('category');
    const category = categorySelect ? categorySelect.value : '';

    fetch(`/api/ward-lookup?lat=${lat}&lng=${lng}&category=${encodeURIComponent(category)}`)
      .then(res => res.json())
      .then(data => {
        const infoBadge = document.getElementById('autoWardInfo');
        if (infoBadge && data.ward_name) {
          infoBadge.innerHTML = `
            <div class="alert alert-success d-flex align-items-center mt-2 py-2 px-3 small">
              <i class="fas fa-check-circle me-2 text-success"></i>
              <div>
                <strong>Auto-Assigned Ward:</strong> ${data.ward_name}<br>
                <strong>Responsible Department:</strong> ${data.department_name} (${data.department_code})<br>
                <span class="text-muted">${data.notes}</span>
              </div>
            </div>
          `;
        }
        const wardSelect = document.getElementById('ward_id');
        if (wardSelect && data.ward_id) {
          wardSelect.value = data.ward_id;
        }
      })
      .catch(err => console.log("Ward lookup error:", err));
  }

  marker.on('dragend', function (e) {
    const coord = marker.getLatLng();
    updateCoordinates(coord.lat, coord.lng);
  });

  map.on('click', function (e) {
    marker.setLatLng(e.latlng);
    updateCoordinates(e.latlng.lat, e.latlng.lng);
  });

  // Current GPS Location Button
  const gpsBtn = document.getElementById(options.gpsBtnId || 'btnGetLocation');
  if (gpsBtn && navigator.geolocation) {
    gpsBtn.addEventListener('click', function () {
      gpsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Locating...';
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          map.setView([lat, lng], 16);
          marker.setLatLng([lat, lng]);
          updateCoordinates(lat, lng);
          gpsBtn.innerHTML = '<i class="fas fa-location-arrow"></i> My Location Found';
          setTimeout(() => {
            gpsBtn.innerHTML = '<i class="fas fa-crosshairs"></i> Use My GPS Location';
          }, 3000);
        },
        function (err) {
          alert("GPS Location Error: " + err.message);
          gpsBtn.innerHTML = '<i class="fas fa-crosshairs"></i> Use My GPS Location';
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });
  }

  // Initial trigger
  updateCoordinates(defaultLat, defaultLng);
}
