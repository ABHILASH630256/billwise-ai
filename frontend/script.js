console.log("BILLWISE FINAL SCRIPT LOADED");

const API_URL = window.location.origin;

let selectedFile = null;
let uploadedFilename = "";
let scannedData = null;

function showToast(message, type = "success") {
  const toastContainer = document.getElementById("toastContainer");
  if (!toastContainer) {
    alert(message);
    return;
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  toast.innerHTML = `
    <i class="fa-solid ${type === "success" ? "fa-circle-check" : "fa-circle-xmark"}"></i>
    <span>${message}</span>
  `;

  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function formatCurrency(value) {
  return `₹${Number(value || 0).toFixed(2)}`;
}

function debounce(fn, delay = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function initUploadPage() {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput) return;

  const chooseFileBtn = document.getElementById("chooseFileBtn");
  const dropZone = document.getElementById("dropZone");
  const previewWrap = document.getElementById("previewWrap");
  const previewImg = document.getElementById("previewImg");
  const removeImg = document.getElementById("removeImg");
  const scanBtn = document.getElementById("scanBtn");

  const resultIdle = document.getElementById("resultIdle");
  const resultLoading = document.getElementById("resultLoading");
  const resultFields = document.getElementById("resultFields");

  const resShop = document.getElementById("resShop");
  const resDate = document.getElementById("resDate");
  const resAmount = document.getElementById("resAmount");
  const resCategoryWrap = document.getElementById("resCategoryWrap");
  const confBar = document.getElementById("confBar");
  const confPct = document.getElementById("confPct");
  const manualAmount = document.getElementById("manualAmount");
  const saveBtn = document.getElementById("saveBtn");

  function resetResults() {
    if (resultIdle) resultIdle.style.display = "flex";
    if (resultLoading) resultLoading.style.display = "none";
    if (resultFields) resultFields.style.display = "none";
  }

  function selectFile(file) {
    if (!file) return;

    const fileName = file.name || "";
    const fileExt = fileName.split('.').pop()?.toLowerCase() || "";
    const validExts = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"];

    if (!file.type.startsWith("image/") && !validExts.includes(fileExt)) {
      showToast("Please select a valid bill image (JPG/PNG).", "error");
      return;
    }

    selectedFile = file;
    uploadedFilename = "";
    scannedData = null;

    const previewURL = URL.createObjectURL(file);
    if (previewImg) previewImg.src = previewURL;

    if (previewImg) {
      previewImg.onload = () => URL.revokeObjectURL(previewURL);
    }

    if (dropZone) dropZone.style.display = "none";
    if (previewWrap) previewWrap.style.display = "block";
    if (scanBtn) scanBtn.disabled = false;

    resetResults();

    console.log("IMAGE SELECTED:", file.name);
    showToast("Image selected successfully.");
  }

  chooseFileBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    fileInput.click();
  });

  dropZone?.addEventListener("click", (event) => {
    if (event.target.closest("#chooseFileBtn")) return;
    event.preventDefault();
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) selectFile(fileInput.files[0]);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("drag-active");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove("drag-active");
    });
  });

  dropZone?.addEventListener("drop", (event) => {
    event.preventDefault();
    if (event.dataTransfer.files.length > 0) selectFile(event.dataTransfer.files[0]);
  });

  removeImg?.addEventListener("click", (event) => {
    event.preventDefault();
    selectedFile = null;
    uploadedFilename = "";
    scannedData = null;

    if (previewImg) previewImg.src = "";
    fileInput.value = "";

    if (previewWrap) previewWrap.style.display = "none";
    if (dropZone) dropZone.style.display = "block";
    if (scanBtn) scanBtn.disabled = true;

    resetResults();
    showToast("Image removed.");
  });

  function showResult(data) {
    if (resultLoading) resultLoading.style.display = "none";
    if (resultIdle) resultIdle.style.display = "none";
    if (resultFields) resultFields.style.display = "block";

    if (resShop) resShop.textContent = data.shop_name || "Unknown";
    if (resDate) resDate.textContent = data.bill_date || "Not detected";

    const amount = Number(data.amount);
    if (resAmount) {
      if (!Number.isNaN(amount) && data.amount !== null && data.amount !== undefined) {
        resAmount.textContent = `₹${amount.toFixed(2)}`;
        if (manualAmount) manualAmount.value = amount;
      } else {
        resAmount.textContent = "Not detected";
        if (manualAmount) manualAmount.value = "";
      }
    }

    const category = data.category || "Other";
    if (resCategoryWrap) resCategoryWrap.innerHTML = `<span class="category-badge">${category}</span>`;

    let confidence = Number(data.confidence || 0);
    if (confidence <= 1) confidence = confidence * 100;
    confidence = Math.round(confidence);

    if (confBar) confBar.style.width = `${confidence}%`;
    if (confPct) confPct.textContent = `${confidence}%`;
  }

  scanBtn?.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!selectedFile) {
      showToast("Please select an image first.", "error");
      return;
    }

    scanBtn.disabled = true;
    const originalButtonHTML = scanBtn.innerHTML;
    scanBtn.innerHTML = `
      <i class="fa-solid fa-spinner fa-spin"></i>
      Scanning bill...
    `;

    if (resultIdle) resultIdle.style.display = "none";
    if (resultFields) resultFields.style.display = "none";
    if (resultLoading) resultLoading.style.display = "flex";

    try {
      const formData = new FormData();
      formData.append("bill_image", selectedFile);

      const scanResponse = await fetch(`${API_URL}/api/scan`, {
    method: "POST",
    credentials: "include",
    body: formData
});

      const rawBody = await scanResponse.text();
      let scanData;
      try {
        scanData = JSON.parse(rawBody);
      } catch (parseError) {
        throw new Error(
          scanResponse.ok
            ? "Server returned an unexpected response. Please try again."
            : `Server error (${scanResponse.status}). The bill may have taken too long to scan — please try again with a smaller/clearer image.`
        );
      }
      if (!scanResponse.ok) throw new Error(scanData.error || "Scanning failed.");

      scannedData = scanData;
      uploadedFilename = scanData.filename || uploadedFilename;
      showResult(scannedData);
      showToast("Bill scanned successfully.");
    } catch (error) {
      if (resultLoading) resultLoading.style.display = "none";
      if (resultFields) resultFields.style.display = "none";
      if (resultIdle) resultIdle.style.display = "flex";
      showToast(error.message || "Unable to scan bill.", "error");
    } finally {
      scanBtn.disabled = false;
      scanBtn.innerHTML = originalButtonHTML;
    }
  });

  saveBtn?.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!scannedData) {
      showToast("Scan a bill before saving.", "error");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/save`, {
    method: "POST",
    credentials: "include",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
        image_name: uploadedFilename,
        shop_name: scannedData.shop_name || "Unknown",
        bill_date: scannedData.bill_date || "",
        amount: Number(manualAmount?.value || scannedData.amount || 0),
        extracted_text: scannedData.extracted_text || "",
        category: scannedData.category || "Other",
        confidence: scannedData.confidence || 0
    })
});

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to save bill.");
      showToast("Bill saved successfully.");
      // Refresh dashboard data used by budgets and run budget checks
      try {
        const dbRes = await fetch(`${API_URL}/api/dashboard`, {
    credentials: "include"
});
        const dbData = await dbRes.json();
        if (dbRes.ok) {
          window.__latestDashboard = dbData;
          // re-render budgets if present
          try { initBudgetModule(); } catch (e) { /* ignore */ }
        }
      } catch (e) { /* ignore */ }

      // Check budget alerts for this saved bill
      try { checkBudgetAlerts(scannedData.category || 'Other', Number(manualAmount?.value || scannedData.amount || 0)); } catch(e){}
    } catch (error) {
      showToast(error.message || "Unable to save bill.", "error");
    }
  });
}

function initDashboardPage() {
  const totalSpending = document.getElementById("totalSpending");
  if (!totalSpending) return;

  const totalBills = document.getElementById("totalBills");
  const topCategory = document.getElementById("topCategory");
  const thisMonth = document.getElementById("thisMonth");
  const pieChartCanvas = document.getElementById("pieChart");
  const barChartCanvas = document.getElementById("barChart");
  const recentTableBody = document.getElementById("recentTableBody");

  function renderRecentBills(bills) {
    if (!recentTableBody) return;
    if (!bills || bills.length === 0) {
      recentTableBody.innerHTML = `
        <tr>
          <td colspan="5" class="empty-row">No recent bills found.</td>
        </tr>
      `;
      return;
    }

    recentTableBody.innerHTML = bills.map((bill) => `
      <tr>
        <td>${bill.shop_name || "Unknown"}</td>
        <td>${bill.bill_date || "—"}</td>
        <td>${formatCurrency(bill.amount)}</td>
        <td>${bill.category || "Other"}</td>
        <td>${bill.created_at || "—"}</td>
      </tr>
    `).join("");
  }

  function renderChart(canvas, type, labels, values) {
    if (!canvas || typeof Chart === "undefined") return;
    const ctx = canvas.getContext('2d');

    // helper to pick a color (use CSS vars if available)
    const getColor = (idx) => {
      try {
        const rootStyle = getComputedStyle(document.documentElement);
        const start = rootStyle.getPropertyValue(`--chart-${idx}-start`).trim();
        if (start) return start;
      } catch (e) {}
      const fallback = ['#6366f1','#10b981','#f59e0b','#ef4444','#06b6d4','#8b5cf6'];
      return fallback[(idx-1) % fallback.length];
    };

    // destroy previous chart instance on this canvas if present
    try { if (canvas._chartInstance) { canvas._chartInstance.destroy(); canvas._chartInstance = null; } } catch(e) {}

    if (type === 'doughnut' || canvas.id === 'pieChart' || type === 'pie') {
      const bg = labels.map((l,i) => getColor((i%6)+1));
      canvas._chartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values, backgroundColor: bg, borderWidth: 0, hoverOffset: 8 }] },
        options: { cutout: '60%', plugins: { legend: { position: 'bottom' } }, responsive: true, maintainAspectRatio: false }
      });
      return;
    }

    if (type === 'bar' || canvas.id === 'barChart') {
      const bg = labels.map((l,i) => getColor((i%6)+1));
      canvas._chartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ data: values, backgroundColor: bg, borderRadius: 6 }] },
        options: {
          plugins: { legend: { display: false } },
          responsive: true,
          maintainAspectRatio: false,
          scales: { x: { grid: { display: false } }, y: { beginAtZero: true } }
        }
      });
      return;
    }

    // fallback: simple chart
    const bg = labels.map((l,i) => getColor((i%6)+1));
    canvas._chartInstance = new Chart(ctx, {
      type,
      data: { labels, datasets: [{ data: values, backgroundColor: bg }] },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  async function loadDashboard() {
    try {
     const response = await fetch(`${API_URL}/api/dashboard`, {
    method: "GET",
    credentials: "include"
});

const data = await response.json();

if (!response.ok) {
    throw new Error(data.error || "Unable to load dashboard.");
}

      if (totalSpending) totalSpending.textContent = formatCurrency(data.total_spending);
      if (totalBills) totalBills.textContent = data.total_bills ?? 0;
      if (topCategory) topCategory.textContent = data.highest_category || "—";
      if (thisMonth) thisMonth.textContent = formatCurrency(data.this_month_spending);

      const categoryLabels = (data.category_spending || []).map((item) => item.category);
      const categoryValues = (data.category_spending || []).map((item) => item.amount);
      const monthlyLabels = (data.monthly_spending || []).map((item) => item.month);
      const monthlyValues = (data.monthly_spending || []).map((item) => item.amount);

      renderChart(pieChartCanvas, "pie", categoryLabels, categoryValues);
      renderChart(barChartCanvas, "bar", monthlyLabels, monthlyValues);
      renderRecentBills(data.recent_bills || []);

      // store latest dashboard data for budgets module
      window.__latestDashboard = data;
      // initialize or update budget UI
      initBudgetModule();
    } catch (error) {
      console.error("Dashboard load error:", error);
      showToast(error.message || "Unable to load dashboard.", "error");
      if (recentTableBody) recentTableBody.innerHTML = `
        <tr>
          <td colspan="5" class="empty-row">Failed to load recent bills.</td>
        </tr>
      `;
    }
  }

  // expose a reload hook so other UI (theme controls) can refresh charts
  window.reloadDashboard = loadDashboard;

  loadDashboard();
}

// -----------------
// Budgets module
// -----------------
function initBudgetModule() {
  const catSelect = document.getElementById('budgetCategory');
  const budgetAmount = document.getElementById('budgetAmount');
  const addBtn = document.getElementById('addBudgetBtn');
  const listWrap = document.getElementById('budgetList');

  if (!catSelect || !addBtn || !listWrap) return;

  const dashboard = window.__latestDashboard || {};
  const categories = (dashboard.category_spending || []).map(item => item.category).filter(Boolean);

  // populate category select (avoid duplicates)
  catSelect.innerHTML = '<option value="">-- Select Category --</option>' +
    [...new Set(categories)].map(c => `<option value="${c}">${c}</option>`).join('');

  function loadBudgets() {
    try { return JSON.parse(localStorage.getItem('bw_budgets') || '{}'); } catch(e) { return {}; }
  }

  function saveBudgets(b) { localStorage.setItem('bw_budgets', JSON.stringify(b || {})); }

  function renderBudgets() {
    const budgets = loadBudgets();
    const rows = Object.keys(budgets).map((cat) => {
      const limit = Number(budgets[cat] || 0);
      const spentItem = (dashboard.category_spending || []).find(i => i.category === cat) || { amount: 0 };
      const spent = Number(spentItem.amount || 0);
      const remaining = Math.max(0, limit - spent);
      const pct = limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : 0;

      return `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 0;border-top:1px solid rgba(255,255,255,0.03);">
          <div style="min-width:160px;">
            <div style="font-weight:700">${cat}</div>
            <div style="font-size:0.9rem;color:var(--text-muted)">Spent: ${formatCurrency(spent)} • Limit: ${formatCurrency(limit)}</div>
          </div>
          <div style="flex:1;margin:0 12px;">
            <div style="height:10px;background:rgba(255,255,255,0.05);border-radius:999px;overflow:hidden;margin-bottom:6px;">
              <div style="width:${pct}%;height:100%;background:var(--gradient-hero);"></div>
            </div>
            <div style="font-size:0.9rem;color:${remaining===0?"var(--accent-red)":"var(--text-secondary)"};">Remaining: ${formatCurrency(remaining)}</div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <button class="btn-ghost btn-compact" data-cat="${cat}" data-action="edit">Edit</button>
            <button class="btn-delete" data-cat="${cat}" data-action="delete">Remove</button>
          </div>
        </div>
      `;
    });

    listWrap.innerHTML = rows.join('') || '<div style="color:var(--text-muted);padding:12px 0">No budgets set yet.</div>';

    // wire edit/delete
    listWrap.querySelectorAll('[data-action="edit"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const cat = btn.getAttribute('data-cat');
        const budgets = loadBudgets();
        budgetAmount.value = budgets[cat] || '';
        catSelect.value = cat;
      });
    });

    listWrap.querySelectorAll('[data-action="delete"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const cat = btn.getAttribute('data-cat');
        const budgets = loadBudgets();
        delete budgets[cat];
        saveBudgets(budgets);
        renderBudgets();
        showToast(`Budget removed for ${cat}`, 'info');
      });
    });
  }

  addBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const cat = catSelect.value || '';
    const amount = Number((budgetAmount.value || '').toString().replace(/[^0-9.]/g, '')) || 0;
    if (!cat || amount <= 0) { showToast('Please select category and enter a valid amount.', 'error'); return; }
    const budgets = loadBudgets();
    budgets[cat] = amount;
    saveBudgets(budgets);
    renderBudgets();
    showToast(`Budget set: ${cat} → ${formatCurrency(amount)}`);
  });

  // initial render
  renderBudgets();
}

// When a bill is saved, check budget thresholds and notify
function checkBudgetAlerts(category, amount) {
  try {
    const budgets = JSON.parse(localStorage.getItem('bw_budgets') || '{}');
    if (!category || !budgets[category]) return;
    const limit = Number(budgets[category] || 0);
    if (!limit || limit <= 0) return;

    // compute spent so far from latest dashboard data
    const dashboard = window.__latestDashboard || {};
    const item = (dashboard.category_spending || []).find(i => i.category === category) || { amount: 0 };
    const spent = Number(item.amount || 0) + Number(amount || 0);
    if (spent > limit) {
      showToast(`Budget exceeded for ${category}: ${formatCurrency(spent)} / ${formatCurrency(limit)}`, 'error');
    } else if (spent > limit * 0.9) {
      showToast(`Approaching budget for ${category}: ${formatCurrency(spent)} / ${formatCurrency(limit)}`, 'info');
    }
  } catch (e) { console.warn('budget check failed', e); }
}

function initHistoryPage() {
  const historyGrid = document.getElementById("historyGrid");
  if (!historyGrid) return;

  const searchInput = document.getElementById("searchInput");
  const catFilter = document.getElementById("catFilter");
  const emptyState = document.getElementById("emptyState");

  function renderBills(bills) {
    if (!historyGrid) return;
    if (!bills || bills.length === 0) {
      historyGrid.innerHTML = "";
      if (emptyState) emptyState.style.display = "block";
      return;
    }

    if (emptyState) emptyState.style.display = "none";

    historyGrid.innerHTML = bills.map((bill) => `
      <div class="history-card">
        <div class="history-card-header">
          <div style="display:flex;gap:12px;align-items:center;">
            <a href="${API_URL}/uploads/${bill.image_name}" target="_blank" rel="noopener" class="hc-thumb-wrap">
              <img src="${API_URL}/uploads/${bill.image_name}" alt="bill-thumb" class="hc-thumb" onerror="this.style.display='none'" />
            </a>
            <div>
              <div class="hc-shop">${bill.shop_name || "Unknown"}</div>
              <div class="hc-meta">${bill.bill_date || "No date"}</div>
            </div>
          </div>
          <div class="hc-amount">${formatCurrency(bill.amount)}</div>
        </div>
        <div class="hc-meta">Category: ${bill.category || "Other"} • Confidence: ${Math.round((bill.confidence || 0) * 100)}%</div>
        <div class="hc-footer">
          <span class="hc-meta">Uploaded: ${bill.created_at || "—"}</span>
          <button class="btn-delete" data-id="${bill.id}">Delete</button>
        </div>
      </div>
    `).join("");

    historyGrid.querySelectorAll(".btn-delete").forEach((button) => {
      button.addEventListener("click", async (event) => {
        const id = event.currentTarget.getAttribute("data-id");
        if (!id) return;
        try {
          const response = await fetch(`${API_URL}/api/bills/${id}`, {
    method: "DELETE",
    credentials: "include"
});
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "Unable to delete bill.");
          showToast("Bill deleted.");
          loadHistory();
        } catch (error) {
          showToast(error.message || "Could not delete bill.", "error");
        }
      });
    });

    // attach lightbox handlers to thumbnails
    historyGrid.querySelectorAll('.hc-thumb-wrap').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        const img = el.querySelector('img.hc-thumb');
        const src = img ? img.src : el.getAttribute('href');
        openLightbox(src);
      });
    });
  }

  async function loadHistory() {
    try {
      const params = new URLSearchParams();
      if (searchInput?.value) params.set("search", searchInput.value.trim());
      if (catFilter?.value) params.set("category", catFilter.value);

      const response = await fetch(`${API_URL}/api/bills?${params.toString()}`, {
    credentials: "include"
});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to load bills.");

      renderBills(data.bills || []);
    } catch (error) {
      console.error("History load error:", error);
      if (emptyState) emptyState.style.display = "block";
      if (historyGrid) historyGrid.innerHTML = "";
      showToast(error.message || "Unable to load bill history.", "error");
    }
  }

  searchInput?.addEventListener("input", debounce(loadHistory, 300));
  catFilter?.addEventListener("change", loadHistory);

  loadHistory();

  // Handle optional actions passed via URL (e.g. from homepage quick actions)
  try {
    const params = new URLSearchParams(window.location.search);
    const action = params.get("action") || params.get("focus");

    if (action) {
      setTimeout(() => {
        if (action === "live-search") {
          searchInput?.focus();
          showToast("Search is ready.");
        } else if (action === "category-filters") {
          catFilter?.focus();
          showToast("Category filter is ready.");
        } else if (action === "quick-delete") {
          // Scroll to first bill and highlight delete button briefly
          const firstDelete = document.querySelector(".history-card .btn-delete");
          if (firstDelete) {
            firstDelete.scrollIntoView({ behavior: "smooth", block: "center" });
            firstDelete.classList.add("flash-delete");
            setTimeout(() => firstDelete.classList.remove("flash-delete"), 2400);
            showToast("Quick delete: press the red button to remove a bill.");
          } else {
            showToast("No bills available to delete.", "info");
          }
        }
      }, 500);
    }
  } catch (e) {
    console.warn("history action handling failed", e);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initHomePage();
  initUploadPage();
  initDashboardPage();
  initHistoryPage();
  initAuthAction();
});

// Chart theme helper: reads CSS vars and applies themes
function applyChartTheme(theme) {
  const root = document.documentElement;
  const themes = {
    default: [
      ['#6366f1', '#8b5cf6'],
      ['#10b981', '#34d399'],
      ['#f59e0b', '#fbbf24'],
      ['#ef4444', '#fb7185'],
      ['#06b6d4', '#67e8f9'],
      ['#8b5cf6', '#c4b5fd']
    ],
    pastel: [
      ['#b7c4ff', '#e6dbff'],
      ['#bff3de', '#d8fff0'],
      ['#ffe8b5', '#fff1d1'],
      ['#ffd6d6', '#ffecec'],
      ['#d6fbff', '#e9fdff'],
      ['#e9dbff', '#f7efff']
    ],
    neon: [
      ['#6d28d9', '#00f5a0'],
      ['#07c3ff', '#00f5a0'],
      ['#ff0066', '#ff9900'],
      ['#ff2d95', '#ff477a'],
      ['#00e5ff', '#00ffa3'],
      ['#b39cff', '#ff7bff']
    ]
  };

  const pairs = themes[theme] || themes.default;
  pairs.forEach((p, i) => {
    root.style.setProperty(`--chart-${i+1}-start`, p[0]);
    root.style.setProperty(`--chart-${i+1}-end`, p[1]);
  });

  // refresh charts
  try { if (window.reloadDashboard) window.reloadDashboard(); } catch(e) {}
}

// Wire up theme control buttons if present
function setupChartThemeControls() {
  const wrap = document.getElementById('chartThemeControls');
  if (!wrap) return;
  wrap.querySelectorAll('button[data-theme]').forEach((btn) => {
    btn.addEventListener('click', () => {
      wrap.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const theme = btn.getAttribute('data-theme');
      applyChartTheme(theme);
    });
  });
}

// initialize controls after DOM ready
document.addEventListener('DOMContentLoaded', () => setupChartThemeControls());


function initHomePage() {
  const liveBtn = document.getElementById("homeLiveSearch");
  const catBtn = document.getElementById("homeCategoryFilters");
  const delBtn = document.getElementById("homeQuickDelete");

  function go(action) {
    // navigate to history with action param
    window.location.href = `history.html?action=${encodeURIComponent(action)}`;
  }

  liveBtn?.addEventListener("click", (e) => { e.preventDefault(); go("live-search"); });
  catBtn?.addEventListener("click", (e) => { e.preventDefault(); go("category-filters"); });
  delBtn?.addEventListener("click", (e) => { e.preventDefault(); go("quick-delete"); });
}

function initAuthAction() {
  const authLink = document.getElementById('authActionLink');
  if (!authLink) return;

  authLink.textContent = 'Logout';
  authLink.addEventListener('click', async (event) => {
    event.preventDefault();

    try {
      await fetch(`${API_URL}/api/logout`, {
    method: 'POST',
    credentials: 'include',
    headers: {
        'Content-Type': 'application/json'
    }
});
    } catch (error) {
      console.warn('Logout failed', error);
    } finally {
      window.location.href = 'login.html';
    }
  });
}

// Lightbox functions for thumbnail preview
function createLightboxIfNeeded() {
  if (document.getElementById('lightboxOverlay')) return;
  const overlay = document.createElement('div');
  overlay.id = 'lightboxOverlay';
  overlay.className = 'lightbox-overlay';
  overlay.innerHTML = `
    <div class="lightbox-content">
      <img class="lightbox-img" src="" alt="preview" />
      <button class="lightbox-close" aria-label="Close">×</button>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay || e.target.classList.contains('lightbox-close')) closeLightbox();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLightbox(); });
}

function openLightbox(src) {
  if (!src) return;
  createLightboxIfNeeded();
  const overlay = document.getElementById('lightboxOverlay');
  const img = overlay.querySelector('.lightbox-img');
  img.src = src;
  overlay.classList.add('show');
}

function closeLightbox() {
  const overlay = document.getElementById('lightboxOverlay');
  if (!overlay) return;
  overlay.classList.remove('show');
  const img = overlay.querySelector('.lightbox-img');
  if (img) setTimeout(() => (img.src = ''), 200);
}

// Show a clear message when the frontend is opened via file:// protocol
function showServeWarningIfNeeded() {
  if (window.location.protocol === 'file:') {
    const warn = document.createElement('div');
    warn.style.position = 'fixed';
    warn.style.inset = '20px';
    warn.style.background = 'rgba(10,10,18,0.98)';
    warn.style.color = '#fff';
    warn.style.zIndex = 999999;
    warn.style.padding = '22px';
    warn.style.borderRadius = '12px';
    warn.style.boxShadow = '0 12px 40px rgba(0,0,0,0.6)';
    warn.innerHTML = `
      <h3 style="margin:0 0 8px;">Page opened locally</h3>
      <div style="color:#cbd5e1;">It looks like you're opening the HTML files directly (file://). To use BillWise properly, start the backend server and open pages via <strong>http://127.0.0.1:5000</strong>.<br/><br/>
      Run in terminal: <code>cd backend && python app.py</code><br/>
      Then open: <a href="http://127.0.0.1:5000/history.html" style="color:#9ae6b4">http://127.0.0.1:5000/history.html</a>
      </div>
    `;
    document.body.appendChild(warn);
  }
}

// On-page debug panel for quick diagnostics
function createDebugPanel() {
  if (document.getElementById('bwDebugPanel')) return;
  const panel = document.createElement('div');
  panel.id = 'bwDebugPanel';
  panel.style.position = 'fixed';
  panel.style.right = '16px';
  panel.style.bottom = '16px';
  panel.style.zIndex = '999999';
  panel.style.background = 'rgba(17,24,39,0.95)';
  panel.style.color = '#f8fafc';
  panel.style.padding = '10px 12px';
  panel.style.borderRadius = '8px';
  panel.style.fontSize = '13px';
  panel.style.boxShadow = '0 8px 30px rgba(0,0,0,0.6)';
  panel.style.maxWidth = '320px';
  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;">
      <strong style="font-size:13px;">BW Debug</strong>
      <button id="bwDebugClose" style="background:transparent;border:0;color:#94a3b8;cursor:pointer">✕</button>
    </div>
    <div id="bwDebugBody" style="line-height:1.3;color:#cbd5e1;max-height:240px;overflow:auto;font-family:Inter,Segoe UI,Arial,sans-serif;">
      <div>Script: loaded</div>
      <div>API_URL: ${API_URL}</div>
      <div id="bwDebugLoc">Location: ${location.href}</div>
      <div id="bwDebugStatus">Status: idle</div>
    </div>
    <div style="display:flex;gap:8px;margin-top:8px;">
      <button id="bwRunDiag" class="btn-ghost">Run diagnostics</button>
      <button id="bwOpenConsole" class="btn-ghost">Open Console</button>
    </div>
  `;
  document.body.appendChild(panel);

  document.getElementById('bwDebugClose').addEventListener('click', () => panel.remove());
  document.getElementById('bwOpenConsole').addEventListener('click', () => { console.log('BW Debug Console Opened'); alert('Open DevTools (F12) to view console logs.'); });

  document.getElementById('bwRunDiag').addEventListener('click', async () => {
    const body = document.getElementById('bwDebugBody');
    try {
      const chooseBtn = document.getElementById('chooseFileBtn');
      const fileInput = document.getElementById('fileInput');
      const scanBtn = document.getElementById('scanBtn');
      const info = [];
      info.push(`protocol: ${location.protocol}`);
      info.push(`href: ${location.href}`);
      info.push(`chooseFileBtn: ${chooseBtn ? 'present' : 'missing'}`);
      info.push(`fileInput: ${fileInput ? 'present' : 'missing'}`);
      info.push(`scanBtn: ${scanBtn ? 'present' : 'missing'}`);
      // try a programmatic click (may not open dialog without user gesture)
      let clickResult = 'not attempted';
      try {
        if (chooseBtn) { chooseBtn.click(); clickResult = 'programmatic click invoked'; }
        else if (fileInput) { fileInput.click(); clickResult = 'programmatic input click invoked'; }
      } catch (e) { clickResult = 'error: ' + e.message; }
      info.push(`click: ${clickResult}`);
      body.querySelector('#bwDebugStatus').textContent = 'Status: running';
      body.innerHTML = '<div style="color:#9ca3af;">' + info.join('<br/>') + '</div>';
    } catch (e) {
      body.querySelector('#bwDebugStatus').textContent = 'Status: error';
      body.innerHTML = '<div style="color:#fca5a5;">' + e.message + '</div>';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  try { showServeWarningIfNeeded(); } catch (e) { /* ignore */ }
});