async function loadDashboard() {
  const response = await fetch('/api/services/latest');
  const data = await response.json();

  renderSummary(data.summary);
  
  // Group services by environment
  const grouped = {};
  data.services.forEach(svc => {
    if (!grouped[svc.environment]) {
      grouped[svc.environment] = [];
    }
    grouped[svc.environment].push(svc);
  });
  
  renderEnvironments(grouped);
  document.getElementById('lastUpdated').textContent = `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
}

function validateServiceForm() {
  const name = document.getElementById('serviceName').value.trim();
  const url = document.getElementById('serviceUrl').value.trim();
  const version = document.getElementById('serviceVersion').value.trim();

  if (!name) {
    showMessage('serviceFormMessage', 'Service name is required', 'error');
    return false;
  }
  if (!url) {
    showMessage('serviceFormMessage', 'Service URL is required', 'error');
    return false;
  }
  if (!version) {
    showMessage('serviceFormMessage', 'Expected version is required', 'error');
    return false;
  }
  return true;
}

function showMessage(elementId, message, type) {
  const el = document.getElementById(elementId);
  el.textContent = message;
  el.className = `message ${type}`;
}

function capitalizeEnvironment(env) {
  return env.charAt(0).toUpperCase() + env.slice(1).toLowerCase();
}

function renderEnvironments(environments) {
  const contentEl = document.getElementById('content');
  
  if (!environments || Object.keys(environments).length === 0) {
    contentEl.innerHTML = '<div class="muted">No services checked yet.</div>';
    return;
  }

  let html = '';
  
  for (const [env, services] of Object.entries(environments)) {
    const rows = services.map(svc => `
      <tr>
        <td>${escapeHtml(svc.service_name)}</td>
        <td><a href="${escapeHtml(svc.url)}" target="_blank">${escapeHtml(svc.url)}</a></td>
        <td>${statusBadge(svc.status)}</td>
        <td>${svc.status_code || '-'}</td>
        <td>${svc.latency_ms ? svc.latency_ms.toFixed(2) : '-'} ms</td>
        <td>${escapeHtml(svc.expected_version || 'N/A')}</td>
        <td>${escapeHtml(svc.observed_version || '-')}</td>
        <td>${svc.version_drift ? '<span class="drift">YES</span>' : 'NO'}</td>
        <td>${escapeHtml(svc.error_message || '-')}</td>
        <td>${new Date(svc.checked_at).toLocaleString()}</td>
      </tr>
    `).join('');

    html += `
      <div class="env-title">${capitalizeEnvironment(env)}</div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th>Service</th>
              <th>URL</th>
              <th>Status</th>
              <th>HTTP</th>
              <th>Latency</th>
              <th>Expected</th>
              <th>Observed</th>
              <th>Drift</th>
              <th>Error</th>
              <th>Checked At</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }
  
  contentEl.innerHTML = html;
}


async function loadConfiguredServices() {
  const response = await fetch('/api/config/services');
  const data = await response.json();

  const services = data.services || [];
  const container = document.getElementById('configuredServices');

  if (services.length === 0) {
    container.innerHTML = '<div class="muted">No configured services yet.</div>';
    return;
  }

  const rows = services.map(svc => `
    <tr>
      <td>${escapeHtml(svc.name)}</td>
      <td>${escapeHtml(svc.url)}</td>
      <td>${escapeHtml(svc.expected_version)}</td>
      <td>
        <button class="delete-btn" onclick="deleteService('${escapeHtml(svc.name)}')">Delete</button>
      </td>
    </tr>
  `).join('');

  container.innerHTML = `
    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>URL</th>
            <th>Expected Version</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function deleteService(serviceName) {
  if (!confirm(`Are you sure you want to delete "${serviceName}"?`)) {
    return;
  }

  try {
    const response = await fetch(`/api/services/${encodeURIComponent(serviceName)}`, {
      method: 'DELETE'
    });

    if (!response.ok) {
      const result = await response.json();
      alert(`Error: ${result.detail || 'Failed to delete service'}`);
      return;
    }

    showMessage('uploadMessage', `Service "${serviceName}" deleted successfully.`, 'success');
    await loadConfiguredServices();
    await loadDashboard();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

function renderSummary(summary) {
  const summaryEl = document.getElementById('summary');
  summaryEl.innerHTML = `
    <div class="card"><div>Total Services</div><div class="metric">${summary.total}</div></div>
    <div class="card"><div>Healthy</div><div class="metric">${summary.healthy}</div></div>
    <div class="card"><div>Degraded</div><div class="metric">${summary.degraded}</div></div>
    <div class="card"><div>Down</div><div class="metric">${summary.down}</div></div>
  `;
}

function statusBadge(status) {
  return `<span class="badge ${status}">${status.toUpperCase()}</span>`;
}

function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}



async function submitServiceForm(event) {
  event.preventDefault();
  
  if (!validateServiceForm()) return;

  const form = document.getElementById('serviceForm');
  const formData = new FormData(form);

  try {
    const response = await fetch('/api/services', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (!response.ok) {
      showMessage('serviceFormMessage', result.detail || 'Failed to add service', 'error');
      return;
    }

    showMessage('serviceFormMessage', 'Service added successfully.', 'success');
    form.reset();

    await loadConfiguredServices();
  } catch (err) {
    showMessage('serviceFormMessage', err.message, 'error');
  }
}

async function uploadConfig() {
  const fileInput = document.getElementById('configFile');
  const messageEl = document.getElementById('uploadMessage');

  if (!fileInput.files.length) {
    messageEl.className = 'message error';
    messageEl.textContent = 'Please choose a JSON or CSV file.';
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const response = await fetch('/api/services/import', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || 'Upload failed');
    }

    messageEl.className = 'message success';
    messageEl.textContent = `Import completed. Added ${result.added_count} service(s).`;
    fileInput.value = '';

    await loadConfiguredServices();
  } catch (err) {
    messageEl.className = 'message error';
    messageEl.textContent = err.message;
  }
}

async function loadIncidentSummary() {
  const el = document.getElementById('incidentSummary');
  if (!el) return;

  try {
    const res = await fetch('/api/incidents/summary');

    // read as text first, then parse JSON safely
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { throw new Error(text); }

    if (!res.ok) throw new Error(data.detail || 'Failed to load incident summary');

    el.textContent = data.summary;
  } catch (err) {
    el.textContent = `Failed to load incident summary: ${err.message}`;
  }
}

document.getElementById('serviceForm').addEventListener('submit', submitServiceForm);

loadDashboard();
loadConfiguredServices();
loadIncidentSummary();
setInterval(loadDashboard, 15000);
setInterval(loadConfiguredServices, 15000);
setInterval(loadIncidentSummary, 60000);