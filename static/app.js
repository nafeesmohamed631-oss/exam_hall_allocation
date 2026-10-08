// ==========================================================================
// Exam Seating System - Frontend JavaScript Logic
// ==========================================================================

// Confirm dialogs for destructive actions (e.g. data-confirm)
document.addEventListener("submit", (e) => {
  const msg = e.target.dataset && e.target.dataset.confirm;
  if (msg && !confirm(msg)) {
    e.preventDefault();
  }
});

// Auto-collapse open details when clicking elsewhere
document.addEventListener("click", (e) => {
  if (!e.target.closest("details")) {
    document.querySelectorAll("details[open]").forEach((d) => {
      d.removeAttribute("open");
    });
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
        <i class="fa-solid fa-spinner fa-spin" style="font-size: 2.2rem; color: var(--primary); margin-bottom: 0.75rem; display: block;"></i>
        <p style="font-size: 1.05rem;">Searching seating records for <strong>${esc(reg)}</strong>…</p>
      </div>
    `;

    try {
      const res = await fetch("/api/lookup/" + encodeURIComponent(reg));
      const data = await res.json();

      if (!res.ok) {
        out.innerHTML = `
          <div class="flash error" style="margin-top: 1rem;">
            <i class="fa-solid fa-circle-exclamation" style="font-size: 1.2rem;"></i>
            <span>${esc(data.error || "No student record found.")}</span>
          </div>
        `;
        return;
      }

      const s = data.student;
      let html = `
        <div class="card" style="border-left: 4px solid var(--primary); margin-bottom: 1.5rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;">
            <div>
              <h2 style="margin-bottom: 0.2rem; font-size: 1.35rem; color: #0f172a;">
                <i class="fa-solid fa-user-check" style="color: var(--success); margin-right: 0.4rem;"></i>
                ${esc(s.name)}
              </h2>
              <p class="muted" style="font-size: 0.95rem;">
                Register No: <strong style="color: #0f172a;">${esc(s.register_no)}</strong> • Department: <strong>${esc(s.department)}</strong> • Year <strong>${esc(s.year)}</strong>
              </p>
            </div>
            <span class="badge success" style="font-size: 0.9rem; padding: 0.4rem 0.85rem;">
              <i class="fa-solid fa-circle-check"></i> Verified Candidate
            </span>
          </div>
        </div>
      `;

      if (!data.allotments || !data.allotments.length) {
        html += `
          <div class="card center muted" style="padding: 3rem;">
            <i class="fa-solid fa-couch" style="font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.4; display: block;"></i>
            <h3 style="color: #334155;">No Seating Allotted Yet</h3>
            <p>Your examination seating arrangement has not been finalized by the administrator. Please check back later.</p>
          </div>
        `;
      } else {
        html += `<h2 style="margin-bottom: 1rem;"><i class="fa-solid fa-calendar-days" style="color: var(--primary);"></i> Allocated Exam Sessions (${data.allotments.length})</h2>`;
        data.allotments.forEach((a) => {
          html += `
            <div class="card result-card">
              <div>
                <span class="tag accent" style="margin-bottom: 0.5rem;"><i class="fa-solid fa-book"></i> ${esc(a.exam_name)}</span>
                <h3 style="font-size: 1.25rem; margin-bottom: 0.75rem; color: #0f172a;">${esc(a.subject)}</h3>
                
                <p style="margin-bottom: 0.4rem; font-size: 0.95rem;">
                  <i class="fa-regular fa-calendar" style="color: var(--primary); width: 20px;"></i>
                  <strong>${esc(a.exam_date)}</strong> at <strong>${esc(a.start_time)}</strong> (${esc(a.duration)} mins)
                </p>
                <p style="margin-bottom: 1rem; font-size: 0.95rem;">
                  <i class="fa-solid fa-location-dot" style="color: #ef4444; width: 20px;"></i>
                  <strong>${esc(a.hall_name)}</strong> ${a.building ? "• " + esc(a.building) : ""}
                </p>

                <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.85rem 1.15rem; display: inline-block;">
                  <div class="muted small-text" style="text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Allocated Seat Number</div>
                  <div class="seat-highlight">${esc(a.seat_no)}</div>
                </div>
              </div>

              <div style="display: flex; flex-direction: column;">
                <div class="hall-img-wrapper" style="border-radius: var(--radius-md); border: 1px solid var(--border); height: 100%; min-height: 200px;">
                  ${
                    a.image_url
                      ? `<img class="hall-img" src="${esc(a.image_url)}" alt="${esc(a.hall_name)}">`
                      : `<div class="hall-img placeholder" style="height: 100%; min-height: 200px;">
                           <i class="fa-solid fa-building-columns" style="font-size: 2.5rem;"></i>
                           <span>${esc(a.hall_name)} Map Preview</span>
                         </div>`
                  }
                </div>
              </div>
            </div>
          `;
        });
      }

      out.innerHTML = html;
    } catch (err) {
      out.innerHTML = `
        <div class="flash error" style="margin-top: 1rem;">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>Connection or server error. Please try again.</span>
        </div>
      `;
    }
  });
}
