/* ============================================================
   HKBK Hostel Management System - Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

  /* ----------------------------------------------------------
     Sidebar toggle (mobile)
  ---------------------------------------------------------- */
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('active');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', function () {
      if (sidebar) sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }

  /* ----------------------------------------------------------
     Auto-dismiss flash messages after 5 s
  ---------------------------------------------------------- */
  document.querySelectorAll('.alert').forEach(function (alert) {
    setTimeout(function () {
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-8px)';
      alert.style.transition = 'all 0.4s ease';
      setTimeout(function () { alert.remove(); }, 400);
    }, 5000);
  });

  document.querySelectorAll('.alert .close-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const alert = btn.closest('.alert');
      if (alert) alert.remove();
    });
  });

  /* ----------------------------------------------------------
     Tab navigation (data-tab)
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const target = btn.getAttribute('data-tab');
      const tabGroup = btn.closest('[data-tab-group]');
      const scope = tabGroup || document;

      // Remove active from all tabs in the same group
      const allTabs = tabGroup
        ? tabGroup.querySelectorAll('[data-tab]')
        : document.querySelectorAll('[data-tab]');
      allTabs.forEach(function (t) { t.classList.remove('active'); });
      btn.classList.add('active');

      // Show the correct pane
      const allPanes = scope.querySelectorAll('.tab-pane');
      allPanes.forEach(function (pane) {
        pane.classList.toggle('active', pane.id === target);
      });
    });
  });

  /* ----------------------------------------------------------
     Floor tabs (rooms page)
  ---------------------------------------------------------- */
  document.querySelectorAll('.floor-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      document.querySelectorAll('.floor-tab').forEach(function (t) {
        t.classList.remove('active');
      });
      tab.classList.add('active');

      const floor = tab.getAttribute('data-floor');
      document.querySelectorAll('.floor-section').forEach(function (sec) {
        sec.style.display = sec.getAttribute('data-floor') === floor ? 'block' : 'none';
      });
    });
  });

  // Activate first floor tab by default
  const firstFloorTab = document.querySelector('.floor-tab');
  if (firstFloorTab) firstFloorTab.click();

  /* ----------------------------------------------------------
     Modal open / close
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-modal-open]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-modal-open');
      const modal = document.getElementById(id);
      if (modal) modal.classList.add('open');
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const backdrop = btn.closest('.modal-backdrop');
      if (backdrop) backdrop.classList.remove('open');
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop) backdrop.classList.remove('open');
    });
  });

  /* ----------------------------------------------------------
     Permission modal: populate hidden fields
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-approve-id]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-approve-id');
      const name = btn.getAttribute('data-student-name') || '';
      const modal = document.getElementById('approveModal');
      if (modal) {
        const hiddenId = modal.querySelector('[name="permission_id"]');
        if (hiddenId) hiddenId.value = id;
        const nameEl = modal.querySelector('.modal-student-name');
        if (nameEl) nameEl.textContent = name;
        modal.classList.add('open');
      }
    });
  });

  document.querySelectorAll('[data-reject-id]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-reject-id');
      const name = btn.getAttribute('data-student-name') || '';
      const modal = document.getElementById('rejectModal');
      if (modal) {
        const hiddenId = modal.querySelector('[name="permission_id"]');
        if (hiddenId) hiddenId.value = id;
        const nameEl = modal.querySelector('.modal-student-name');
        if (nameEl) nameEl.textContent = name;
        modal.classList.add('open');
      }
    });
  });

  /* ----------------------------------------------------------
     Attendance: select-all radios by value
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-mark-all]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const val = btn.getAttribute('data-mark-all');
      document.querySelectorAll('.att-status-radio').forEach(function (radio) {
        if (radio.value === val) {
          radio.checked = true;
          updateAttRowStyle(radio);
        }
      });
    });
  });

  document.querySelectorAll('.att-status-radio').forEach(function (radio) {
    radio.addEventListener('change', function () { updateAttRowStyle(radio); });
    // Init style on load
    if (radio.checked) updateAttRowStyle(radio);
  });

  function updateAttRowStyle(radio) {
    const row = radio.closest('tr');
    if (!row) return;
    row.classList.remove('row-success', 'row-danger', 'row-warning', 'out-of-station');
    if (radio.checked) {
      if (radio.value === 'present')          row.classList.add('row-success');
      else if (radio.value === 'absent')      row.classList.add('row-danger');
      else if (radio.value === 'on_leave')    row.classList.add('row-warning');
      else if (radio.value === 'out_of_station') row.classList.add('out-of-station');
    }
  }

  /* ----------------------------------------------------------
     Progress ring animation (attendance circle)
  ---------------------------------------------------------- */
  document.querySelectorAll('.progress-ring-fill').forEach(function (circle) {
    const r = parseFloat(circle.getAttribute('r'));
    const pct = parseFloat(circle.getAttribute('data-percent') || 0);
    const circumference = 2 * Math.PI * r;
    circle.style.strokeDasharray = circumference;
    circle.style.strokeDashoffset = circumference;
    setTimeout(function () {
      circle.style.strokeDashoffset = circumference - (pct / 100) * circumference;
    }, 100);
  });

  /* ----------------------------------------------------------
     Filter tables by search input
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-search-table]').forEach(function (input) {
    const tableId = input.getAttribute('data-search-table');
    const table = document.getElementById(tableId);
    if (!table) return;
    input.addEventListener('input', function () {
      const q = input.value.toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  });

  /* ----------------------------------------------------------
     Confirm before destructive action
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      const msg = el.getAttribute('data-confirm') || 'Are you sure?';
      if (!confirm(msg)) e.preventDefault();
    });
  });

  /* ----------------------------------------------------------
     Toggle user active status
  ---------------------------------------------------------- */
  document.querySelectorAll('.toggle-active-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const form = btn.closest('form');
      if (form) form.submit();
    });
  });

  /* ----------------------------------------------------------
     Weekly menu: save per-row via AJAX (optional fallback = full form)
  ---------------------------------------------------------- */
  // Full form submit is default; JS enhancement is optional.

  /* ----------------------------------------------------------
     Food preference toggle confirmation
  ---------------------------------------------------------- */
  const foodToggleForm = document.getElementById('foodToggleForm');
  if (foodToggleForm) {
    foodToggleForm.addEventListener('submit', function (e) {
      if (!confirm('Are you sure you want to change your food preference?')) {
        e.preventDefault();
      }
    });
  }

  /* ----------------------------------------------------------
     Date pickers: default today
  ---------------------------------------------------------- */
  document.querySelectorAll('input[type="date"][data-default-today]').forEach(function (inp) {
    if (!inp.value) {
      const today = new Date().toISOString().split('T')[0];
      inp.value = today;
    }
  });

  /* ----------------------------------------------------------
     Vendor complaints: inline response toggle
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-toggle-response]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-toggle-response');
      const form = document.getElementById('resp-' + id);
      if (form) {
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
      }
    });
  });

  /* ----------------------------------------------------------
     Warden add-note inline form toggle
  ---------------------------------------------------------- */
  document.querySelectorAll('[data-toggle-note]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-toggle-note');
      const form = document.getElementById('note-' + id);
      if (form) {
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
      }
    });
  });

});
