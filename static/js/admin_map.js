/**
 * Municipality Admin Complaint Map
 * Renders all active complaints, ward centers, and status badges on Leaflet OpenStreetMap.
 */
function initAdminComplaintMap(mapElementId, complaintsData, wardsData) {
  const mapCenter = [12.9716, 77.5946];
  const map = L.map(mapElementId).setView(mapCenter, 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap | Smart Municipality Waste System'
  }).addTo(map);

  // Status Color Mapping
  function getMarkerColor(status) {
    switch (status) {
      case 'Verified and Closed': return '#10b981'; // green
      case 'AI Verification': return '#0284c7';     // light blue
      case 'Cleanup In Progress': return '#ea580c'; // orange
      case 'Worker Assigned': return '#d97706';     // amber
      case 'AI Analysis Completed': return '#4f46e5'; // indigo
      case 'Rejected': return '#dc2626';            // red
      default: return '#64748b';                    // slate
    }
  }

  // Draw Ward Zones
  if (wardsData && wardsData.length > 0) {
    wardsData.forEach(w => {
      L.circle([w.lat_center, w.lng_center], {
        color: '#10b981',
        fillColor: '#10b981',
        fillOpacity: 0.08,
        radius: 2800,
        dashArray: '4, 8'
      }).bindTooltip(`<b>${w.ward_name}</b><br><small>${w.ward_code}</small>`, { permanent: false }).addTo(map);
    });
  }

  // Draw Complaints Markers
  if (complaintsData && complaintsData.length > 0) {
    const markers = [];
    complaintsData.forEach(c => {
      if (!c.latitude || !c.longitude) return;

      const markerColor = getMarkerColor(c.status);
      const circleMarker = L.circleMarker([c.latitude, c.longitude], {
        radius: 9,
        fillColor: markerColor,
        color: '#ffffff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      });

      const popupHtml = `
        <div style="min-width: 220px; font-family: Inter, sans-serif;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
            <strong style="color:#0f172a; font-size: 0.95rem;">${c.complaint_id}</strong>
            <span style="font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; background:${markerColor}20; color:${markerColor}; font-weight:700;">
              ${c.priority || 'Normal'}
            </span>
          </div>
          <p style="margin: 4px 0; font-size: 0.85rem; color:#475569;">${c.title || c.category}</p>
          <div style="font-size: 0.75rem; color:#64748b; margin-bottom: 8px;">
            <i class="fas fa-map-marker-alt text-danger"></i> ${c.ward_name || 'Ward Area'}<br>
            <i class="fas fa-info-circle text-primary"></i> <strong>Status:</strong> ${c.status}
          </div>
          <div style="display: flex; gap: 6px;">
            <a href="/admin/verification/${c.complaint_id}" class="btn btn-sm btn-outline-primary" style="font-size: 0.75rem; padding: 3px 8px; text-decoration:none;">
              Inspect & Verify
            </a>
            <a href="/track/${c.complaint_id}" target="_blank" class="btn btn-sm btn-outline-secondary" style="font-size: 0.75rem; padding: 3px 8px; text-decoration:none;">
              Tracking View
            </a>
          </div>
        </div>
      `;

      circleMarker.bindPopup(popupHtml).addTo(map);
      markers.push([c.latitude, c.longitude]);
    });

    if (markers.length > 0) {
      map.fitBounds(markers, { padding: [40, 40] });
    }
  }
}
