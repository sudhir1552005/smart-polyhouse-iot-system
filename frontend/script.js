// const API_ROOT =
//   window.location.hostname === "localhost"
//     ? "http://10.117.239.84:8080/sensors"
//     : "https://polyhouse-qqiy.onrender.com/sensors";
const API_ROOT = "https://polyhouse-qqiy.onrender.com/sensors";

const tbody = document.querySelector("#dataTable tbody");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const pageInfo = document.getElementById("pageInfo");
const pageSizeSelect = document.getElementById("pageSize");
const searchBox = document.getElementById("searchBox");
const viewDataBtn = document.getElementById("viewDataBtn");

let allData = [];
let page = 1;
let size = parseInt(pageSizeSelect.value);

async function loadData() {
  try {
    const res = await fetch(`${API_ROOT}/data`);

    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }

    allData = await res.json();
    renderTable();
  } catch (err) {
    console.error("Error fetching data:", err);
    alert("Unable to load sensor data");
  }
}

function exportToCSV() {
  if (!allData.length) {
    alert("No data available to export!");
    return;
  }

  // Create CSV header
  const headers = ["S.No", "Temperature (°C)", "Timestamp"];
  const rows = allData.map((d, i) => [
    i + 1,
    d.waterTemperature ?? "-",
    d.timestamp ?? "-"
  ]);

  // Combine headers and rows
  const csvContent = [headers, ...rows]
    .map(e => e.join(","))
    .join("\n");

  // Create a blob and trigger download
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `polyhouse_data_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
// ===== PROFILE MENU & LOGOUT =====

// Remove profile icon if not logged in
const profileMenu = document.querySelector(".profile-menu");
if (!token && profileMenu) {
  profileMenu.remove();
}

const profileIcon = document.getElementById("profileIcon");
const dropdown = document.getElementById("profileDropdown");
const logoutBtn = document.getElementById("logoutBtn");

if (profileIcon && dropdown && logoutBtn) {
  // Toggle dropdown
  profileIcon.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("active");
  });

  // Logout
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("token");
    window.location.href = "login.html";
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".profile-menu")) {
      dropdown.classList.remove("active");
    }
  });
}

function renderTable() {
  size = parseInt(pageSizeSelect.value);
  const search = searchBox.value.trim().toLowerCase();

  let filtered = allData.filter(
    d =>
      d.waterTemperature?.toString().toLowerCase().includes(search) ||
      d.timestamp?.toLowerCase().includes(search)
  );

  const totalPages = Math.ceil(filtered.length / size);
  page = Math.max(1, Math.min(page, totalPages));

  const start = (page - 1) * size;
  const pageData = filtered.slice(start, start + size);

  tbody.innerHTML = pageData
    .map(
      (d, i) => `
      <tr>
        <td>${start + i + 1}</td>
        <td>${d.waterTemperature ?? '-'}</td>
        <td>${d.timestamp ?? '-'}</td>
      </tr>
    `
    )
    .join('');

  pageInfo.textContent = `Page ${page} of ${totalPages || 1} (${filtered.length} records)`;
  prevBtn.disabled = page <= 1;
  nextBtn.disabled = page >= totalPages;
}

pageSizeSelect.addEventListener("change", () => {
  page = 1;
  renderTable();
});

searchBox.addEventListener("input", () => {
  page = 1;
  renderTable();
});

prevBtn.addEventListener("click", () => {
  if (page > 1) {
    page--;
    renderTable();
  }
});

nextBtn.addEventListener("click", () => {
  page++;
  renderTable();
});

viewDataBtn.onclick = () => window.location.href = 'viewdata.html';
document.getElementById("exportBtn").addEventListener("click", exportToCSV);

loadData();
