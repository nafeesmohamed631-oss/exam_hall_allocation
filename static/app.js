// ==========================================================================
// Exam Seating System - Frontend JavaScript Logic
// ==========================================================================

// Global Modal Handlers
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("active");
    document.body.style.overflow = "hidden";
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("active");
    document.body.style.overflow = "";
  }
}

// Close modal when clicking on overlay background or pressing Escape
document.addEventListener("click", (e) => {
  if (e.target.classList && e.target.classList.contains("modal-overlay")) {
    e.target.classList.remove("active");
    document.body.style.overflow = "";
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay.active").forEach((m) => {
      m.classList.remove("active");
    });
    document.body.style.overflow = "";
  }
});

// Confirm dialogs for destructive actions (e.g. data-confirm)
document.addEventListener("submit", (e) => {
  const msg = e.target.dataset && e.target.dataset.confirm;
  if (msg && !confirm(msg)) {
    e.preventDefault();
  }
});

// Helper to escape HTML characters
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c])
  );

// Student lookup feature (AJAX call to /api/lookup/<reg>)
const form = document.getElementById("lookupForm");
if (form) {
  const out = document.getElementById("result");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const regInput = document.getElementById("regInput");
    const reg = regInput.value.trim();
    if (!reg) return;

    out.innerHTML = `
      <div class="card center muted" style="padding: 2.5rem;">
        <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: var(--primary); margin-bottom: 0.5rem; display: block;"></i>
        <p>Searching records for <strong>${esc(reg)}</strong>…</p>
      </div>
    `;

    try {
      const res = await fetch("/api/lookup/" + encodeURIComponent(reg));
      const data = await res.json();

      if (!res.ok) {
        out.innerHTML = `
          <div class="flash error">
            <i class="fa-solid fa-circle-exclamation"></i>
            <span>${esc(data.error || "No student record found with this register number.")}</span>
          </div>
        `;
        return;
      }

      const s = data.student;
      let html = `
        <div class="card" style="border-left: 4px solid var(--primary); margin-bottom: 1.25rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <div>
              <h2 style="margin: 0 0 0.25rem 0; font-size: 1.25rem;">
                <i class="fa-solid fa-user-check" style="color: var(--success); margin-right: 0.35rem;"></i>
                ${esc(s.name)}
              </h2>
              <p class="muted" style="font-size: 0.9rem;">
                Register No: <strong style="color: #0f172a;">${esc(s.register_no)}</strong> • Department: <strong>${esc(s.department)}</strong> • Year <strong>${esc(s.year)}</strong>
              </p>
            </div>
            <span class="badge success">
              <i class="fa-solid fa-check"></i> Registered Student
            </span>
          </div>
        </div>
      `;

      if (!data.allotments || !data.allotments.length) {
        html += `
          <div class="card center muted" style="padding: 2.5rem;">
            <i class="fa-solid fa-chair" style="font-size: 2rem; opacity: 0.4; display: block; margin-bottom: 0.5rem;"></i>
            <h3 style="color: #334155; margin-bottom: 0.25rem;">No Seating Allotted Yet</h3>
            <p>Your seating arrangement has not been generated yet. Please check back before the exam.</p>
          </div>
        `;
      } else {
        html += `<h3 style="margin-bottom: 0.85rem;"><i class="fa-solid fa-calendar-days" style="color: var(--primary);"></i> Exam Seating Schedule (${data.allotments.length})</h3>`;
        data.allotments.forEach((a) => {
          html += `
            <div class="result-allotment-card">
              <div>
                <span class="tag accent" style="margin-bottom: 0.4rem;">${esc(a.exam_name)}</span>
                <h3 style="font-size: 1.15rem; margin-bottom: 0.5rem;">${esc(a.subject)}</h3>
                <p style="font-size: 0.9rem; margin-bottom: 0.3rem;">
                  <i class="fa-regular fa-calendar" style="color: var(--primary); width: 18px;"></i>
                  <strong>${esc(a.exam_date)}</strong> at <strong>${esc(a.start_time)}</strong> (${esc(a.duration)} mins)
                </p>
                <p style="font-size: 0.9rem; margin-bottom: 0.5rem;">
                  <i class="fa-solid fa-location-dot" style="color: var(--danger); width: 18px;"></i>
                  <strong>${esc(a.hall_name)}</strong> ${a.building ? "• " + esc(a.building) : ""}
                </p>
                <div class="seat-box">
                  <div class="muted small-text" style="font-weight: 700; text-transform: uppercase;">Seat Number</div>
                  <div class="seat-number">${esc(a.seat_no)}</div>
                </div>
              </div>

              <div>
                ${
                  a.image_url
                    ? `<img src="${esc(a.image_url)}" alt="${esc(a.hall_name)}" style="width: 100%; height: 140px; object-fit: cover; border-radius: var(--radius-sm); border: 1px solid var(--border);">`
                    : `<div class="card center muted" style="padding: 1.5rem 0.5rem; margin: 0; background: #f8fafc;">
                         <i class="fa-solid fa-building-columns" style="font-size: 1.5rem; display: block; margin-bottom: 0.35rem;"></i>
                         <span class="small-text">${esc(a.hall_name)}</span>
                       </div>`
                }
              </div>
            </div>
          `;
        });
      }

      out.innerHTML = html;
    } catch (err) {
      out.innerHTML = `
        <div class="flash error">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>Connection or server error. Please try again.</span>
        </div>
      `;
    }
  });
}
