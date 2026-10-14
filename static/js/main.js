// Main JavaScript Utilities
document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 6000);
  });

  // Notification read handler
  document.querySelectorAll('.mark-read-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const nid = this.dataset.id;
      fetch(`/notifications/mark-read/${nid}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      }).then(res => res.json())
        .then(data => {
          if (data.success) {
            const item = document.getElementById(`notif-item-${nid}`);
            if (item) {
              item.classList.remove('bg-light');
              this.remove();
            }
            const badge = document.getElementById('notif-badge');
            if (badge) {
              let count = parseInt(badge.textContent) - 1;
              if (count <= 0) badge.remove();
              else badge.textContent = count;
            }
          }
        });
    });
  });
});
