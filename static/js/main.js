/* ==========================================================================
   main.js - small vanilla JavaScript helpers
   1. mobile navigation toggle
   2. search autocomplete (calls /api/suggest)
   3. evaluation chart (Chart.js, reads data-chart on the canvas)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  setupNavToggle();
  setupSuggestions();
  drawEvaluationChart();
});

/* 1. Opens and closes the navigation menu on small screens. */
function setupNavToggle() {
  const toggle = document.getElementById("nav-toggle");
  const nav = document.getElementById("main-nav");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", () => nav.classList.toggle("open"));
}

/* 2. Autocomplete: when the user types (or focuses an empty search bar),
      ask the server for suggestions and display them under the input. */
function setupSuggestions() {
  document.querySelectorAll("[data-suggest]").forEach((input) => {
    const box = input.parentElement.querySelector(".suggestions");
    if (!box) return;
    let timer = null;

    const load = () => {
      const url = `/api/suggest?q=${encodeURIComponent(input.value)}`;
      fetch(url, { credentials: "same-origin" })
        .then((response) => response.json())
        .then((data) => renderSuggestions(box, input, data.suggestions))
        .catch(() => { box.hidden = true; });
    };

    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(load, 180);
    });
    input.addEventListener("focus", load);
    document.addEventListener("click", (event) => {
      if (!input.parentElement.contains(event.target)) box.hidden = true;
    });
  });
}

/* Builds the list of suggestions. textContent is used (never innerHTML)
   so that user text can never inject HTML. */
function renderSuggestions(box, input, items) {
  box.innerHTML = "";
  if (!items || items.length === 0) {
    box.hidden = true;
    return;
  }
  const list = document.createElement("ul");
  items.forEach((item) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    const kind = document.createElement("span");
    kind.className = "kind";
    kind.textContent = item.kind;
    button.appendChild(kind);
    button.addEventListener("click", () => {
      input.value = item.value;
      input.form.submit();
    });
    li.appendChild(button);
    list.appendChild(li);
  });
  box.appendChild(list);
  box.hidden = false;
}

/* 3. Draws the Precision/Recall comparison chart on the evaluation page. */
function drawEvaluationChart() {
  const canvas = document.getElementById("eval-chart");
  if (!canvas || typeof Chart === "undefined") return;
  const data = JSON.parse(canvas.dataset.chart);
  new Chart(canvas, {
    type: "bar",
    data: data,
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
      scales: { y: { beginAtZero: true, max: 1, title: { display: true, text: "Valeur (0 à 1)" } } },
    },
  });
}
