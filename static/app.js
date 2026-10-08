// confirm dialogs for destructive actions
document.addEventListener("submit", (e) => {
  const msg = e.target.dataset && e.target.dataset.confirm;
  if (msg && !confirm(msg)) e.preventDefault();
});

// student lookup (calls the Flask JSON API which queries MongoDB)
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

const form = document.getElementById("lookupForm");
if (form) {
  const out = document.getElementById("result");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const reg = document.getElementById("regInput").value.trim();
    out.innerHTML = '<div class="card muted">Searching…</div>';
    try {
      const res = await fetch("/api/lookup/" + encodeURIComponent(reg));
      const data = await res.json();
      if (!res.ok) { out.innerHTML = `<div class="flash error">${esc(data.error)}</div>`; return; }
      const s = data.student;
      let html = `<div class="card"><h2>${esc(s.name)} <span class="muted">(${esc(s.register_no)} · ${esc(s.department)} · Year ${esc(s.year)})</span></h2></div>`;
      if (!data.allotments.length) html += '<div class="card muted">No seat has been allotted yet.</div>';
      data.allotments.forEach((a) => {
        html += `<div class="card result-card"><div>
          <h3>${esc(a.subject)} <span class="muted">${esc(a.exam_name)}</span></h3>
          <p>📅 ${esc(a.exam_date)} at ${esc(a.start_time)} (${esc(a.duration)} min)</p>
          <p>🏛 ${esc(a.hall_name)} ${a.building ? "· " + esc(a.building) : ""}</p>
          <p>Seat number</p><div class="seat">${esc(a.seat_no)}</div></div>
          <div>${a.image_url ? `<img class="hall-img" style="height:200px" src="${esc(a.image_url)}" alt="Hall">` : '<div class="hall-img placeholder" style="height:200px">No hall image</div>'}</div></div>`;
      });
      out.innerHTML = html;
    } catch (err) {
      out.innerHTML = '<div class="flash error">Server error. Please try again.</div>';
    }
  });
}
