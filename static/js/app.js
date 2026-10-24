// ====================================================================
// NIVORA — Intelligent Civic Water Supply & Complaint Platform
// Light Purple & Royal Elegant Edition — Client Engine
// ====================================================================

let appState = {
    currentRole: 'resident',
    currentView: 'landing',
    currentUser: { id: 1, name: 'Priya Sharma', role: 'resident', locality_id: 1 },
    categories: [],
    localities: [],
    users: [],
    complaints: [],
    clusters: [],
    allAdminComplaints: [],
    allTechnicianJobs: [],
    mapInstance: null,
    mapMarkers: [],
    mapCircles: [],
    categoryChartInstance: null,
    techFilters: { priority: 'all', status: 'all' },
    adminFilters: { search: '', locality_id: 'all', category_id: 'all', status: 'all' },
    lastGeneratedTicket: null
};

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
    lucide.createIcons();
    initIncidentTimeDefault();
    await fetchMetadata();
    await loadComplaints();
    await loadClusters();
    setupCategorySelector();
    
    // Default to Landing Page overview
    switchView('landing');
});

function initIncidentTimeDefault() {
    const input = document.getElementById('complaint-incident-time');
    if (input) {
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        input.value = now.toISOString().slice(0, 16);
    }
}

// ====================================================================
// 1. Navigation & View Switching System
// ====================================================================

function switchView(viewName) {
    appState.currentView = viewName;

    // Hide all view sections
    document.querySelectorAll('.role-view').forEach(view => view.classList.add('hidden'));

    // Reveal the requested view section
    const targetView = document.getElementById(`view-${viewName}`);
    if (targetView) targetView.classList.remove('hidden');

    // Reset navigation bar button styling
    document.querySelectorAll('.nav-item-btn').forEach(btn => {
        btn.classList.remove('bg-white', 'text-[#5B21B6]', 'font-semibold', 'shadow-sm');
        btn.classList.add('text-[#6B7280]');
    });

    const activeBtn = document.getElementById(`nav-btn-${viewName}`) || document.getElementById(`role-btn-${viewName}`);
    if (activeBtn) {
        activeBtn.classList.add('bg-white', 'text-[#5B21B6]', 'font-semibold', 'shadow-sm');
        activeBtn.classList.remove('text-[#6B7280]');
    }

    // Update Context Banner
    const roleBadge = document.getElementById('banner-role-badge');
    const userInfo = document.getElementById('banner-user-info');
    const headerBtnText = document.getElementById('header-user-btn-text');

    if (viewName === 'landing') {
        if (roleBadge) {
            roleBadge.textContent = 'Municipal Overview';
            roleBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#5B21B6] text-white shadow-xs';
        }
        if (userInfo) {
            userInfo.innerHTML = `Welcome to <strong>NIVORA</strong> • Citywide Civic Water Utility & Proactive Clustering`;
        }
    } else if (viewName === 'resident') {
        switchRole('resident', false);
    } else if (viewName === 'admin') {
        switchRole('admin', false);
    } else if (viewName === 'technician') {
        switchRole('technician', false);
    } else if (viewName === 'reports') {
        if (roleBadge) {
            roleBadge.textContent = 'Performance & SLA';
            roleBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#4C1D95] text-white shadow-xs';
        }
        if (userInfo) {
            userInfo.innerHTML = `Official Municipal Performance & SLA Reports • 15 Wards Audited`;
        }
        loadReportsDashboard();
    }

    lucide.createIcons();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function switchRole(role, triggerView = true) {
    appState.currentRole = role;

    const roleBadge = document.getElementById('banner-role-badge');
    const userInfo = document.getElementById('banner-user-info');
    const headerBtnText = document.getElementById('header-user-btn-text');

    if (role === 'resident') {
        appState.currentUser = { id: 1, name: 'Priya Sharma', role: 'resident', locality_id: 1 };
        if (roleBadge) {
            roleBadge.textContent = 'Resident Portal';
            roleBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#5B21B6] text-white shadow-xs';
        }
        if (userInfo) {
            userInfo.innerHTML = `Logged in as <strong>Priya Sharma</strong> (North Ward - Sector 4)`;
        }
        if (headerBtnText) headerBtnText.textContent = 'Priya Sharma (Resident)';
        loadComplaints();
    } else if (role === 'admin') {
        appState.currentUser = { id: 9, name: 'City Water Commissioner', role: 'admin' };
        if (roleBadge) {
            roleBadge.textContent = 'Administrator Portal';
            roleBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#1E1B4B] text-white shadow-xs';
        }
        if (userInfo) {
            userInfo.innerHTML = `Central Operations Command Center • GIS Locality Analytics Active`;
        }
        if (headerBtnText) headerBtnText.textContent = 'Commissioner (Admin)';
        loadAdminDashboard();
    } else if (role === 'technician') {
        appState.currentUser = { id: 6, name: 'Rajesh Kumar', role: 'technician', locality_id: 1 };
        if (roleBadge) {
            roleBadge.textContent = 'Service-Team Portal';
            roleBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#7C3AED] text-white shadow-xs';
        }
        if (userInfo) {
            userInfo.innerHTML = `Logged in as <strong>Rajesh Kumar</strong> (Field Specialist • Grid Alpha)`;
        }
        if (headerBtnText) headerBtnText.textContent = 'Rajesh Kumar (Field)';
        loadTechnicianJobs();
    }

    if (triggerView) {
        switchView(role);
    }
}

// ====================================================================
// 2. Authentication Modal & Quick Switcher
// ====================================================================

function openAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.remove('hidden');
    lucide.createIcons();
}

function closeAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.add('hidden');
}

function signInWithRole(role) {
    closeAuthModal();
    switchRole(role);
}

// ====================================================================
// 3. Metadata Fetching
// ====================================================================

async function fetchMetadata() {
    try {
        const res = await fetch('/api/meta');
        const data = await res.json();
        appState.categories = data.categories;
        appState.localities = data.localities;
        appState.users = data.users;

        // Populate resident locality dropdown
        const locSelect = document.getElementById('resident-locality-select');
        if (locSelect) {
            locSelect.innerHTML = data.localities.map(l => 
                `<option value="${l.id}">${l.name} (${l.zone_code})</option>`
            ).join('');
        }

        // Populate admin filter dropdowns
        const adminLocFilter = document.getElementById('admin-filter-locality');
        if (adminLocFilter) {
            adminLocFilter.innerHTML = `<option value="all">All Localities</option>` + 
                data.localities.map(l => `<option value="${l.id}">${l.name}</option>`).join('');
        }

        const adminCatFilter = document.getElementById('admin-filter-category');
        if (adminCatFilter) {
            adminCatFilter.innerHTML = `<option value="all">All Categories</option>` + 
                data.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
        }
    } catch (err) {
        console.error('Failed to load metadata', err);
    }
}

// ====================================================================
// 4. 3-Step Complaint Registration Wizard
// ====================================================================

function goToWizardStep(step) {
    if (step === 2) {
        const catId = document.getElementById('selected-category-id')?.value;
        if (!catId) {
            alert('Please select an issue category to proceed.');
            return;
        }
    } else if (step === 3) {
        const loc = document.getElementById('resident-locality-select')?.value;
        const time = document.getElementById('complaint-incident-time')?.value;
        if (!loc || !time) {
            alert('Please select your Locality / Ward and observation time.');
            return;
        }
    }

    // Toggle step cards
    document.querySelectorAll('.wizard-step').forEach(s => s.classList.add('hidden'));
    const target = document.getElementById(`wizard-step-${step}`);
    if (target) target.classList.remove('hidden');

    // Update Progress Indicator Circles
    for (let i = 1; i <= 3; i++) {
        const dot = document.getElementById(`step-dot-${i}`);
        if (!dot) continue;
        dot.classList.remove('active', 'completed', 'pending');
        if (i < step) {
            dot.classList.add('completed');
            dot.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i>`;
        } else if (i === step) {
            dot.classList.add('active');
            dot.textContent = i;
        } else {
            dot.classList.add('pending');
            dot.textContent = i;
        }
    }

    // Update Connecting Lines
    const line1 = document.getElementById('step-line-1');
    const line2 = document.getElementById('step-line-2');
    if (line1) {
        if (step >= 2) line1.classList.add('completed');
        else line1.classList.remove('completed');
    }
    if (line2) {
        if (step >= 3) line2.classList.add('completed');
        else line2.classList.remove('completed');
    }

    lucide.createIcons();
}

function setupCategorySelector() {
    const container = document.getElementById('category-selector-container');
    if (!container) return;

    container.innerHTML = appState.categories.map((cat, idx) => {
        const isSelected = idx === 0;
        return `
        <div onclick="selectCategory(${cat.id}, this)" class="cat-pill cursor-pointer border ${isSelected ? 'border-[#7C3AED] bg-[#EDE9FE] ring-2 ring-[#7C3AED]/25' : 'border-[#DDD6FE] bg-white hover:bg-[#F5F3FF]'} p-3 rounded-xl flex items-center space-x-3 transition">
            <div class="w-9 h-9 rounded-lg bg-[#F5F3FF] border border-[#DDD6FE] flex items-center justify-center text-[#5B21B6] shadow-xs flex-shrink-0">
                <i data-lucide="${cat.icon || 'droplet'}" class="w-4 h-4"></i>
            </div>
            <div class="overflow-hidden">
                <div class="text-xs font-bold text-[#1E1B4B] truncate">${cat.name}</div>
                <div class="text-[10px] text-[#5B21B6] uppercase font-semibold">${cat.default_severity} • Target SLA: ${cat.sla_hours}h</div>
            </div>
        </div>
        `;
    }).join('');

    lucide.createIcons();
}

function selectCategory(id, el) {
    document.getElementById('selected-category-id').value = id;
    document.querySelectorAll('.cat-pill').forEach(pill => {
        pill.classList.remove('border-[#7C3AED]', 'bg-[#EDE9FE]', 'ring-2', 'ring-[#7C3AED]/25');
        pill.classList.add('border-[#DDD6FE]', 'bg-white');
    });
    el.classList.add('border-[#7C3AED]', 'bg-[#EDE9FE]', 'ring-2', 'ring-[#7C3AED]/25');
    el.classList.remove('border-[#DDD6FE]', 'bg-white');
}

function autoDetectCoordinates() {
    const jitterLat = 28.6280 + (Math.random() - 0.5) * 0.0015;
    const jitterLng = 77.2080 + (Math.random() - 0.5) * 0.0015;
    document.getElementById('complaint-lat').value = jitterLat.toFixed(4);
    document.getElementById('complaint-lng').value = jitterLng.toFixed(4);
}

// 5. Resident Complaint Submission
async function handleComplaintSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-submit-complaint');
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i><span>Analyzing Proximity & Logging...</span>`;
    lucide.createIcons();

    const payload = {
        resident_id: appState.currentUser.id,
        locality_id: parseInt(document.getElementById('resident-locality-select').value),
        category_id: parseInt(document.getElementById('selected-category-id').value),
        incident_time: document.getElementById('complaint-incident-time').value,
        lat: parseFloat(document.getElementById('complaint-lat').value),
        lng: parseFloat(document.getElementById('complaint-lng').value),
        address_landmark: document.getElementById('complaint-landmark').value,
        house_number: document.getElementById('complaint-house').value || 'Not Specified',
        description: document.getElementById('complaint-desc').value.trim() || 'Water supply issue observed.',
        priority: 'high'
    };

    try {
        const res = await fetch('/api/complaints', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            appState.lastGeneratedTicket = data.ticket_number;
            document.getElementById('modal-ref-number').textContent = data.ticket_number;
            
            const clusterNotice = document.getElementById('modal-cluster-notice');
            if (data.cluster_result && data.cluster_result.clustered) {
                clusterNotice.innerHTML = `<span class="font-bold text-[#5B21B6]">🎉 Recurring Issue Grouping:</span> Linked to Master Incident <strong>${data.cluster_result.cluster_code}</strong> with ${data.cluster_result.total_complaints_in_cluster} neighbor reports.`;
            } else {
                clusterNotice.textContent = "Estimated Category SLA: Response within 6 hours.";
            }

            // Open Reference Success Modal
            document.getElementById('success-reference-modal').classList.remove('hidden');

            // Reset form & return to Step 1
            document.getElementById('complaint-desc').value = '';
            document.getElementById('complaint-landmark').value = '';
            document.getElementById('complaint-house').value = '';
            initIncidentTimeDefault();
            goToWizardStep(1);

            await loadComplaints();
        }
    } catch (err) {
        alert('Error submitting complaint: ' + err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Submit Complaint & Generate Reference</span>`;
        lucide.createIcons();
    }
}

function copyReferenceNumber() {
    if (!appState.lastGeneratedTicket) return;
    navigator.clipboard.writeText(appState.lastGeneratedTicket).then(() => {
        alert(`Copied ${appState.lastGeneratedTicket} to clipboard!`);
    }).catch(() => {
        alert(`Reference: ${appState.lastGeneratedTicket}`);
    });
}

function closeSuccessModal() {
    document.getElementById('success-reference-modal').classList.add('hidden');
}

// 6. 1-Tap Neighborhood Cluster Link
async function quickLinkToCluster(clusterId) {
    const payload = {
        resident_id: appState.currentUser.id,
        cluster_id: clusterId,
        address_landmark: "Sector 4 Main Corridor",
        house_number: "Flat 204",
        incident_time: new Date().toISOString().slice(0, 16),
        lat: 28.6284,
        lng: 77.2085
    };

    try {
        const res = await fetch('/api/complaints/quick-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            appState.lastGeneratedTicket = data.ticket_number;
            document.getElementById('modal-ref-number').textContent = data.ticket_number;
            document.getElementById('modal-cluster-notice').innerHTML = `Joined Master Cluster <strong>${data.cluster_code}</strong>! Total connected homes: ${data.new_count}.`;
            document.getElementById('success-reference-modal').classList.remove('hidden');
            await loadComplaints();
        }
    } catch (err) {
        alert('Failed to link: ' + err);
    }
}

// ====================================================================
// 7. Resident Complaints List & Tracking Timeline
// ====================================================================

async function loadComplaints() {
    try {
        const res = await fetch(`/api/complaints?role=resident&user_id=${appState.currentUser.id}`);
        const data = await res.json();
        appState.complaints = data.complaints;
        renderResidentTickets();
    } catch (err) {
        console.error('Failed to load complaints', err);
    }
}

function renderResidentTickets() {
    const container = document.getElementById('resident-tickets-list');
    if (!container) return;

    const filterVal = document.getElementById('resident-filter-status')?.value || 'all';

    let list = appState.complaints;
    if (filterVal === 'active') {
        list = list.filter(t => ['submitted', 'clustered', 'assigned', 'in_progress'].includes(t.status));
    } else if (filterVal === 'resolved') {
        list = list.filter(t => t.status === 'resolved');
    } else if (filterVal === 'closed') {
        list = list.filter(t => t.status === 'closed');
    }

    if (list.length === 0) {
        container.innerHTML = `
        <div class="text-center py-12 border border-dashed border-[#DDD6FE] rounded-2xl p-6 text-[#6B7280]">
            <i data-lucide="inbox" class="w-10 h-10 mx-auto stroke-1 mb-2 text-[#A78BFA]"></i>
            <h4 class="text-xs font-bold text-[#1E1B4B]">No Complaints Match This Filter</h4>
            <p class="text-[11px] text-[#6B7280] mt-1">Submit a new water supply report using the 3-step wizard above.</p>
        </div>`;
        lucide.createIcons();
        return;
    }

    container.innerHTML = list.map(t => {
        const isResolved = t.status === 'resolved';
        const isClosed = t.status === 'closed';
        const isClustered = t.cluster_code != null;

        // Progress bar step calculation
        const step1 = true;
        const step2 = ['clustered', 'assigned', 'in_progress', 'resolved', 'closed'].includes(t.status);
        const step3 = ['assigned', 'in_progress', 'resolved', 'closed'].includes(t.status);
        const step4 = ['in_progress', 'resolved', 'closed'].includes(t.status);
        const step5 = isResolved || isClosed;

        return `
        <div class="border border-[#DDD6FE] rounded-2xl p-4 bg-white hover:border-[#A78BFA] transition shadow-xs space-y-3">
            <div class="flex items-start justify-between">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="font-mono font-bold text-xs text-[#1E1B4B] bg-[#F5F3FF] px-2 py-0.5 rounded-md border border-[#DDD6FE]">${t.ticket_number}</span>
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${getBadgeClass(t.status)} uppercase">${t.status}</span>
                        ${isClustered ? `
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EDE9FE] text-[#5B21B6] border border-[#DDD6FE] flex items-center">
                            <i data-lucide="network" class="w-3 h-3 mr-1"></i> Cluster: ${t.cluster_code} (${t.cluster_count} homes)
                        </span>` : ''}
                    </div>
                    <h3 class="text-xs font-bold text-[#1E1B4B] mt-1.5">${t.category_name}</h3>
                    <p class="text-xs text-[#6B7280] mt-0.5">${t.description}</p>
                </div>
                <div class="text-right">
                    <span class="text-[10px] text-[#6B7280] font-mono">${formatDate(t.created_at)}</span>
                    ${t.incident_time ? `<div class="text-[10px] text-[#6B7280]">Observed: ${t.incident_time}</div>` : ''}
                </div>
            </div>

            <!-- 5-Step Timeline in Royal Theme -->
            <div class="pt-1">
                <div class="flex items-center text-[10px] font-semibold text-[#6B7280] mb-1 justify-between">
                    <span class="${step1 ? 'text-[#5B21B6] font-bold' : ''}">1. Submitted</span>
                    <span class="${step2 ? 'text-[#5B21B6] font-bold' : ''}">2. Triaged</span>
                    <span class="${step3 ? 'text-[#5B21B6] font-bold' : ''}">3. Dispatched</span>
                    <span class="${step4 ? 'text-[#5B21B6] font-bold' : ''}">4. On-Site</span>
                    <span class="${step5 ? (isClosed ? 'text-[#1E1B4B] font-bold' : 'text-emerald-600 font-bold') : ''}">5. ${isClosed ? 'Confirmed' : 'Resolved'}</span>
                </div>
                <div class="flex items-center space-x-1">
                    <div class="flex-1 h-1.5 rounded-full ${step1 ? 'bg-[#7C3AED]' : 'bg-[#DDD6FE]'}"></div>
                    <div class="flex-1 h-1.5 rounded-full ${step2 ? 'bg-[#7C3AED]' : 'bg-[#DDD6FE]'}"></div>
                    <div class="flex-1 h-1.5 rounded-full ${step3 ? 'bg-[#7C3AED]' : 'bg-[#DDD6FE]'}"></div>
                    <div class="flex-1 h-1.5 rounded-full ${step4 ? 'bg-[#7C3AED]' : 'bg-[#DDD6FE]'}"></div>
                    <div class="flex-1 h-1.5 rounded-full ${step5 ? 'bg-emerald-500' : 'bg-[#DDD6FE]'}"></div>
                </div>
            </div>

            <div class="text-[11px] text-[#6B7280] flex items-center justify-between border-t border-[#DDD6FE] pt-2">
                <span><strong>Landmark:</strong> ${t.address_landmark}</span>
                ${t.technician_name ? `<span><strong>Crew:</strong> ${t.technician_name}</span>` : `<span class="italic">Queued for Dispatch</span>`}
            </div>

            <!-- Confirmation & Rating for Resolved Tickets -->
            ${isResolved ? `
            <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex flex-col sm:flex-row items-center justify-between gap-2">
                <div class="text-xs text-emerald-900">
                    <strong>Service Team Completed Repair!</strong> Please confirm your water pressure/quality is restored.
                </div>
                <div class="flex items-center space-x-2">
                    <button onclick="confirmResolution(${t.id})" class="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold shadow-xs">
                        Confirm Resolution
                    </button>
                </div>
            </div>` : ''}

            <!-- Completed Feedback Display -->
            ${isClosed && t.feedback_rating ? `
            <div class="bg-[#F5F3FF] border border-[#DDD6FE] rounded-xl p-2.5 flex items-center justify-between text-xs">
                <span class="text-[#6B7280]">Resolution Confirmed:</span>
                <span class="font-bold text-amber-500">${'⭐'.repeat(t.feedback_rating)} (${t.feedback_rating}/5)</span>
            </div>` : ''}
        </div>
        `;
    }).join('');

    lucide.createIcons();
}

async function confirmResolution(complaintId) {
    const rating = prompt("Please rate the repair quality (1 to 5 stars):", "5");
    if (!rating) return;
    const comment = prompt("Optional comment for the service team:", "Water supply restored with good pressure.");

    try {
        const res = await fetch('/api/complaints/confirm-resolution', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                complaint_id: complaintId,
                rating: parseInt(rating) || 5,
                comment: comment || 'Resolved.'
            })
        });
        const data = await res.json();
        if (data.success) {
            alert("Thank you! Your resolution confirmation and rating have been recorded.");
            await loadComplaints();
        }
    } catch (err) {
        alert("Failed to confirm: " + err);
    }
}

// ====================================================================
// 8. Administrator Command Console
// ====================================================================

async function loadAdminDashboard() {
    await loadKPIs();
    await loadAdminClusters();
    await loadAdminComplaints();
    await loadLocalityAnalyticsTable();
    await initOrUpdateMap();
    await loadCategoryChart();
    await loadAuditLogs();
}

async function loadKPIs() {
    try {
        const res = await fetch('/api/analytics/performance');
        const data = await res.json();
        const p = data.performance;

        const totalTickets = p.total_tickets || p.total_complaints || 0;
        const activeClusters = p.active_clusters != null ? p.active_clusters : 0;
        const slaRate = p.sla_compliance_rate != null ? p.sla_compliance_rate : 95.0;
        const mttr = p.avg_mttr_hours != null ? p.avg_mttr_hours : (p.mean_time_to_resolve_hours || 4.0);
        const rating = p.avg_rating != null ? p.avg_rating : (p.average_citizen_rating || 4.8);
        const reviews = p.total_reviews != null ? p.total_reviews : (p.total_feedback_reviews || 0);

        document.getElementById('kpi-total-tickets').textContent = totalTickets.toLocaleString();
        document.getElementById('kpi-active-clusters').textContent = activeClusters;
        document.getElementById('kpi-sla-rate').textContent = `${slaRate}%`;
        document.getElementById('kpi-mttr').textContent = `${mttr} hrs`;
        document.getElementById('kpi-rating').textContent = `⭐ ${rating}`;
        document.getElementById('kpi-reviews').textContent = `${reviews} verified reviews`;
    } catch (err) {
        console.error('Failed to load KPIs', err);
    }
}

async function loadAdminClusters() {
    try {
        const res = await fetch('/api/clusters');
        const data = await res.json();
        appState.clusters = data.clusters;

        const badge = document.getElementById('admin-cluster-badge');
        if (badge) badge.textContent = `${data.clusters.length} Active Incident Clusters`;

        const container = document.getElementById('admin-clusters-grid');
        if (!container) return;

        if (data.clusters.length === 0) {
            container.innerHTML = `<div class="col-span-3 text-xs text-[#6B7280] italic">No active multi-household clusters detected in the 250m window.</div>`;
            return;
        }

        container.innerHTML = data.clusters.map(cl => `
        <div class="border border-[#DDD6FE] bg-gradient-to-br from-[#EDE9FE]/50 to-white rounded-xl p-3.5 space-y-2 shadow-xs">
            <div class="flex items-center justify-between">
                <span class="font-mono font-bold text-xs text-[#5B21B6]">${cl.cluster_code}</span>
                <span class="bg-[#EDE9FE] text-[#5B21B6] text-[10px] font-bold px-2 py-0.5 rounded-full border border-[#DDD6FE]">${cl.complaint_count} Linked Homes</span>
            </div>
            <div class="text-xs font-bold text-[#1E1B4B]">${cl.category_name}</div>
            <div class="text-[11px] text-[#6B7280]">
                <strong>Ward:</strong> ${cl.locality_name} (${cl.zone_code})
            </div>
            <div class="pt-1 flex items-center justify-between border-t border-[#DDD6FE]">
                <span class="text-[10px] text-[#6B7280]">Radius: 250m Proximity</span>
                <button onclick="inspectCluster(${cl.id})" class="text-xs font-semibold text-[#5B21B6] hover:underline flex items-center">
                    <span>Inspect Group</span>
                    <i data-lucide="chevron-right" class="w-3.5 h-3.5 ml-0.5"></i>
                </button>
            </div>
        </div>
        `).join('');

        lucide.createIcons();
    } catch (err) {
        console.error('Failed to load clusters', err);
    }
}

// Centralized API Client with Timeout & Error Handling
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);
    options.signal = controller.signal;

    try {
        const response = await fetch(endpoint, options);
        clearTimeout(timeoutId);
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || `HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
            throw new Error('Request timed out. Please verify server connectivity.');
        }
        throw err;
    }
}

function updateResidentClusterAlert() {
    const alertCard = document.getElementById('resident-nearby-cluster-card');
    if (!alertCard) return;

    const activeClusters = (appState.clusters || []).filter(c => c.status === 'active' || c.status === 'investigating');
    if (activeClusters.length > 0) {
        const primary = activeClusters[0];
        alertCard.classList.remove('hidden');
        alertCard.innerHTML = `
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div class="flex items-start space-x-3.5">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#5B21B6] to-[#7C3AED] text-white flex items-center justify-center flex-shrink-0 shadow-md shadow-purple-500/20">
                    <i data-lucide="network" class="w-5 h-5"></i>
                </div>
                <div>
                    <div class="flex items-center space-x-2">
                        <h3 class="text-sm font-bold text-[#1E1B4B]">Active Recurring Issue Detected in Your Area</h3>
                        <span class="bg-[#EDE9FE] text-[#5B21B6] text-[10px] font-bold px-2 py-0.5 rounded-full border border-[#DDD6FE]">Cluster Alert</span>
                    </div>
                    <p class="text-xs text-[#6B7280] mt-1">
                        <strong>${primary.complaint_count} neighbor reports</strong> within 250m match a shared <strong>${primary.category_name}</strong> at incident code <span class="font-mono font-semibold underline text-[#5B21B6]">${primary.cluster_code}</span>. A service team has already been dispatched.
                    </p>
                </div>
            </div>
            <button onclick="quickLinkToCluster(${primary.id})" class="w-full sm:w-auto px-4 py-2.5 btn-royal-primary text-xs flex items-center justify-center space-x-2 flex-shrink-0">
                <i data-lucide="check-check" class="w-4 h-4"></i>
                <span>I Have This Issue Too (1-Tap Confirmation)</span>
            </button>
        </div>`;
    } else {
        alertCard.innerHTML = `
        <div class="flex items-center space-x-3 text-emerald-800 bg-emerald-50/70 p-3 rounded-xl border border-emerald-200">
            <i data-lucide="check-circle" class="w-5 h-5 text-emerald-600 flex-shrink-0"></i>
            <div class="text-xs">
                <strong>Neighborhood Status Clear:</strong> No active trunk pipeline leaks or recurring multi-household failures currently detected within 250m.
            </div>
        </div>`;
    }
    lucide.createIcons();
}

function inspectCluster(clusterId) {
    const cl = appState.clusters.find(c => c.id === clusterId);
    if (!cl) return;

    appState.activeInspectedClusterId = clusterId;
    document.getElementById('inspect-cluster-title').textContent = `Incident Cluster: ${cl.cluster_code}`;
    document.getElementById('inspect-cluster-subtitle').textContent = `${cl.category_name} • ${cl.locality_name}`;
    document.getElementById('inspect-cluster-loc').textContent = `${cl.locality_name} (${cl.zone_code}) — Centroid: [${cl.center_lat.toFixed(4)}, ${cl.center_lng.toFixed(4)}]`;

    const tbody = document.getElementById('inspect-cluster-tbody');
    tbody.innerHTML = (cl.tickets || []).map(t => `
    <tr class="hover:bg-[#F5F3FF]">
        <td class="py-2 px-3 font-mono font-bold text-[#5B21B6]">${t.ticket_number}</td>
        <td class="py-2 px-3 text-[#1E1B4B]">${t.address_landmark}</td>
        <td class="py-2 px-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${getBadgeClass(t.status)} uppercase">${t.status}</span></td>
        <td class="py-2 px-3 text-[#6B7280] font-mono">${formatDate(t.created_at)}</td>
        <td class="py-2 px-3 text-right">
            <button onclick="decoupleTicketFromCluster(${cl.id}, ${t.id})" class="text-rose-600 hover:text-rose-800 text-[10px] font-semibold border border-rose-200 px-2 py-0.5 rounded hover:bg-rose-50 transition" title="Decouple complaint from cluster">Decouple</button>
        </td>
    </tr>
    `).join('');

    document.getElementById('cluster-inspect-modal').classList.remove('hidden');
    lucide.createIcons();
}

async function promptIncidentPriorityOverride() {
    const clusterId = appState.activeInspectedClusterId;
    if (!clusterId) return;
    const cl = appState.clusters.find(c => c.id === clusterId);
    if (!cl) return;

    const newPriority = prompt("Enter new severity ('critical', 'high', 'medium', 'low'):", "critical");
    if (!newPriority || !['critical', 'high', 'medium', 'low'].includes(newPriority.toLowerCase())) {
        if (newPriority) alert("Invalid severity. Must be critical, high, medium, or low.");
        return;
    }
    const justification = prompt("Enter supervisor override justification (min 5 characters):", "Escalated priority due to multiple affected residential blocks.");
    if (!justification || justification.trim().length < 5) {
        alert("A valid justification (min 5 characters) is required.");
        return;
    }

    try {
        const data = await apiCall('/api/incidents/override-priority', 'POST', {
            incident_id: cl.id,
            new_priority: newPriority.toLowerCase(),
            justification: justification,
            supervisor_name: appState.currentUser.name || "Ward Supervisor"
        });
        if (data.success) {
            alert(`Supervisor priority override applied! Severity is now '${newPriority.toUpperCase()}'.`);
            closeClusterModal();
            await loadAdminClusters();
            await loadAdminDashboard();
        }
    } catch (err) {
        alert("Failed to override priority: " + err.message);
    }
}

async function openMergeModal(complaintId, ticketNumber) {
    document.getElementById('merge-complaint-id').value = complaintId;
    document.getElementById('merge-complaint-label').textContent = `${ticketNumber} (Complaint #${complaintId})`;
    
    const select = document.getElementById('merge-target-incident');
    select.innerHTML = '<option value="">Loading master incidents...</option>';
    
    try {
        const res = await fetch('/api/incidents');
        const data = await res.json();
        const incidents = data.incidents || [];
        if (incidents.length === 0) {
            select.innerHTML = '<option value="">No active master incidents found</option>';
        } else {
            select.innerHTML = incidents.map(inc => 
                `<option value="${inc.id}">[${inc.severity.toUpperCase()}] ${inc.incident_number} — ${inc.title} (${inc.locality_name})</option>`
            ).join('');
        }
    } catch (err) {
        select.innerHTML = '<option value="1">INC-SM-16-20260513-001 (Default)</option>';
    }

    document.getElementById('merge-modal').classList.remove('hidden');
    lucide.createIcons();
}

function closeMergeModal() {
    document.getElementById('merge-modal').classList.add('hidden');
}

async function submitIncidentMerge(e) {
    e.preventDefault();
    const complaintId = parseInt(document.getElementById('merge-complaint-id').value);
    const incidentId = parseInt(document.getElementById('merge-target-incident').value);
    const reason = document.getElementById('merge-reason').value.trim();

    if (!complaintId || !incidentId) {
        alert("Please select a target master incident.");
        return;
    }

    try {
        const data = await apiCall('/api/incidents/merge', 'POST', {
            master_incident_id: incidentId,
            complaint_ids: [complaintId],
            reason: reason || "Correlated root-cause failure along main trunk line."
        });

        if (data.success) {
            alert(`Successfully merged complaint into Master Incident ${data.master_incident_number}!`);
            closeMergeModal();
            await loadAdminComplaints();
            await loadAdminClusters();
            await loadAuditLogs();
        }
    } catch (err) {
        alert("Merge failed: " + err.message);
    }
}

async function decoupleTicketFromCluster(incidentId, complaintId) {
    if (!confirm(`Are you sure you want to decouple Complaint ID ${complaintId} from this Incident Cluster?`)) return;
    try {
        const data = await apiCall('/api/incidents/split', 'POST', {
            incident_id: incidentId,
            complaint_id: complaintId,
            reason: "Decoupled via Administrator Console inspection."
        });
        if (data.success) {
            alert(`Complaint ${complaintId} successfully decoupled!`);
            closeClusterModal();
            await loadAdminClusters();
            await loadAdminComplaints();
            await loadAuditLogs();
        }
    } catch (err) {
        alert("Split operation failed: " + err.message);
    }
}

async function promptPriorityOverride(complaintId) {
    const newPriority = prompt("Enter new priority ('critical', 'high', 'medium', 'low'):", "critical");
    if (!newPriority || !['critical', 'high', 'medium', 'low'].includes(newPriority.toLowerCase())) {
        if (newPriority) alert("Invalid priority. Must be critical, high, medium, or low.");
        return;
    }
    const justification = prompt("Enter mandatory justification for supervisor priority override:", "Overdue work order requiring emergency excavation permit.");
    if (!justification || justification.trim().length < 5) {
        alert("A valid justification (min 5 characters) is required.");
        return;
    }

    try {
        const data = await apiCall('/api/complaints/escalate', 'POST', {
            complaint_id: complaintId,
            technician_id: 6,
            reason: justification
        });
        if (data.success) {
            alert(`Priority override applied to Ticket ID ${complaintId}!`);
            await loadAdminComplaints();
            await loadKPIs();
            await loadAuditLogs();
        }
    } catch (err) {
        alert("Override failed: " + err.message);
    }
}

function closeClusterModal() {
    document.getElementById('cluster-inspect-modal').classList.add('hidden');
}

async function loadAdminComplaints() {
    try {
        const res = await fetch('/api/complaints?role=admin');
        const data = await res.json();
        appState.allAdminComplaints = data.complaints;
        applyAdminFilters();
    } catch (err) {
        console.error('Failed to load admin complaints', err);
    }
}

function applyAdminFilters() {
    const search = document.getElementById('admin-filter-search')?.value.toLowerCase() || '';
    const localityId = document.getElementById('admin-filter-locality')?.value || 'all';
    const categoryId = document.getElementById('admin-filter-category')?.value || 'all';
    const status = document.getElementById('admin-filter-status')?.value || 'all';

    let filtered = appState.allAdminComplaints || [];

    if (search) {
        filtered = filtered.filter(c => 
            c.ticket_number.toLowerCase().includes(search) ||
            c.address_landmark.toLowerCase().includes(search) ||
            c.description.toLowerCase().includes(search)
        );
    }

    if (localityId !== 'all') {
        filtered = filtered.filter(c => c.locality_id === parseInt(localityId));
    }

    if (categoryId !== 'all') {
        filtered = filtered.filter(c => c.category_id === parseInt(categoryId));
    }

    if (status !== 'all') {
        filtered = filtered.filter(c => c.status === status);
    }

    renderAdminComplaintsTable(filtered.slice(0, 50));
}

function resetAdminFilters() {
    document.getElementById('admin-filter-search').value = '';
    document.getElementById('admin-filter-locality').value = 'all';
    document.getElementById('admin-filter-category').value = 'all';
    document.getElementById('admin-filter-status').value = 'all';
    applyAdminFilters();
}

function renderAdminComplaintsTable(complaints) {
    const tbody = document.getElementById('admin-complaints-tbody');
    if (!tbody) return;

    if (complaints.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-[#6B7280]">No complaints matching current filters.</td></tr>`;
        return;
    }

    const techOptions = (appState.users || []).filter(u => u.role === 'technician');

    tbody.innerHTML = complaints.map(c => `
    <tr class="hover:bg-[#F5F3FF] transition">
        <td class="py-2.5 px-3 font-mono font-bold text-[#5B21B6]">${c.ticket_number}</td>
        <td class="py-2.5 px-3 text-[#1E1B4B] font-medium">${c.locality_name}</td>
        <td class="py-2.5 px-3 text-[#1E1B4B]">${c.category_name}</td>
        <td class="py-2.5 px-3 text-[#6B7280] text-[11px] font-mono">${c.incident_time || formatDate(c.created_at)}</td>
        <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${getBadgeClass(c.priority)} uppercase">${c.priority}</span></td>
        <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${getBadgeClass(c.status)} uppercase">${c.status}</span></td>
        <td class="py-2.5 px-3">
            <select onchange="assignTechnician(${c.id}, this.value)" class="text-[11px] border border-[#DDD6FE] rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-[#7C3AED]">
                <option value="">${c.technician_name ? `Assigned: ${c.technician_name}` : 'Assign Crew...'}</option>
                ${techOptions.map(t => `<option value="${t.id}" ${c.technician_id === t.id ? 'selected' : ''}>${t.name}</option>`).join('')}
            </select>
        </td>
        <td class="py-2.5 px-3 text-right space-x-1 whitespace-nowrap">
            <button onclick="openMergeModal(${c.id}, '${c.ticket_number}')" class="text-[#7C3AED] hover:text-[#5B21B6] font-semibold text-[11px] px-2 py-0.5 rounded border border-[#DDD6FE] hover:bg-[#EDE9FE] transition" title="Merge into Master Incident">Merge</button>
            <button onclick="promptPriorityOverride(${c.id})" class="text-amber-700 hover:text-amber-900 font-semibold text-[11px] px-2 py-0.5 rounded border border-amber-200 hover:bg-amber-50 transition" title="Supervisor Priority Override">Override</button>
            <button onclick="alert('Ticket: ${c.ticket_number}\\nLandmark: ${c.address_landmark}\\nDetails: ${c.description}')" class="text-[#5B21B6] hover:text-[#4C1D95] font-semibold text-[11px] px-2 py-0.5 rounded border border-[#DDD6FE] hover:bg-[#F5F3FF] transition">Details</button>
        </td>
    </tr>
    `).join('');
}

async function assignTechnician(complaintId, technicianId) {
    if (!technicianId) return;
    try {
        const res = await fetch('/api/assignments/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ complaint_id: complaintId, technician_id: parseInt(technicianId) })
        });
        const data = await res.json();
        if (data.success) {
            alert(`Service team assigned: ${data.technician_name}`);
            await loadAdminComplaints();
            await loadAuditLogs();
        }
    } catch (err) {
        alert('Assignment failed: ' + err);
    }
}

function exportComplaintsCSV() {
    window.location.href = '/api/reports/export/csv';
}

// 9. Locality Trends & Infrastructure Health Table
async function loadLocalityAnalyticsTable() {
    try {
        const res = await fetch('/api/analytics/locality');
        const data = await res.json();
        const tbody = document.getElementById('locality-analytics-tbody');
        if (!tbody) return;

        tbody.innerHTML = data.localities.map(l => {
            const healthColor = l.health_score > 80 ? 'bg-emerald-500' : (l.health_score > 60 ? 'bg-amber-500' : 'bg-rose-500');
            const badgeClass = l.health_score > 80 ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : (l.health_score > 60 ? 'bg-amber-50 text-amber-800 border-amber-200' : 'bg-rose-50 text-rose-800 border-rose-200');

            return `
            <tr class="hover:bg-[#F5F3FF] transition">
                <td class="py-2.5 px-3 font-bold text-[#1E1B4B]">${l.locality_name}</td>
                <td class="py-2.5 px-3 text-[#6B7280] font-mono text-[11px]">${l.pipeline_grid}</td>
                <td class="py-2.5 px-3 font-semibold text-[#1E1B4B]">${l.active_complaints} active / ${l.total_complaints} total</td>
                <td class="py-2.5 px-3">
                    <span class="${l.leak_count > 0 ? 'text-rose-600 font-bold' : 'text-[#6B7280]'}">${l.leak_count}</span>
                </td>
                <td class="py-2.5 px-3">
                    <span class="${l.contamination_count > 0 ? 'text-amber-600 font-bold' : 'text-[#6B7280]'}">${l.contamination_count}</span>
                </td>
                <td class="py-2.5 px-3">
                    <div class="flex items-center space-x-2">
                        <div class="w-16 bg-[#DDD6FE] h-2 rounded-full overflow-hidden">
                            <div class="${healthColor} h-2 rounded-full" style="width: ${l.health_score}%"></div>
                        </div>
                        <span class="font-bold text-[#1E1B4B]">${l.health_score}%</span>
                    </div>
                </td>
                <td class="py-2.5 px-3">
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeClass}">${l.status_tag}</span>
                </td>
                <td class="py-2.5 px-3 text-[#6B7280]">${l.supervisor_name}</td>
            </tr>
            `;
        }).join('');
    } catch (err) {
        console.error('Failed to load locality analytics', err);
    }
}

// 10. Interactive GIS Proximity Map (Leaflet)
async function initOrUpdateMap() {
    const mapElement = document.getElementById('gis-map');
    if (!mapElement) return;

    if (!appState.mapInstance) {
        appState.mapInstance = L.map('gis-map').setView([28.6250, 77.2100], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(appState.mapInstance);
    }

    appState.mapMarkers.forEach(m => appState.mapInstance.removeLayer(m));
    appState.mapCircles.forEach(c => appState.mapInstance.removeLayer(c));
    appState.mapMarkers = [];
    appState.mapCircles = [];

    // Draw Purple Cluster Circles (250m Proximity)
    appState.clusters.forEach(cl => {
        const circle = L.circle([cl.center_lat, cl.center_lng], {
            color: '#7C3AED',
            fillColor: '#8B5CF6',
            fillOpacity: 0.18,
            radius: cl.radius_meters || 250,
            weight: 2,
            dashArray: '4, 6'
        }).addTo(appState.mapInstance);

        circle.bindPopup(`
            <div class="text-xs p-1 font-sans">
                <span class="bg-[#EDE9FE] text-[#5B21B6] font-bold px-1.5 py-0.5 rounded text-[10px]">MASTER CLUSTER</span>
                <div class="font-bold text-sm text-[#1E1B4B] mt-1">${cl.cluster_code}</div>
                <div class="text-[#6B7280] mt-0.5"><strong>Category:</strong> ${cl.category_name}</div>
                <div class="text-[#6B7280]"><strong>Locality:</strong> ${cl.locality_name} (${cl.zone_code})</div>
                <div class="text-[#5B21B6] font-bold mt-1">Grouped Reports: ${cl.complaint_count} Households</div>
            </div>
        `);
        appState.mapCircles.push(circle);
    });

    // Draw Individual Complaint Pins with Preserved Usability Colors
    (appState.allAdminComplaints || []).slice(0, 150).forEach(t => {
        let pinColor = '#0ea5e9';
        if (t.status === 'resolved' || t.status === 'closed') {
            pinColor = '#10b981';
        } else if (t.category_name.includes('Leak') || t.category_name.includes('Burst')) {
            pinColor = '#ef4444';
        } else if (t.category_name.includes('Contamination')) {
            pinColor = '#f59e0b';
        }

        const iconHtml = `
            <div style="background-color: ${pinColor}; width: 22px; height: 22px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: bold;">
                ●
            </div>`;
        const customIcon = L.divIcon({
            className: 'custom-leaflet-marker',
            html: iconHtml,
            iconSize: [22, 22],
            iconAnchor: [11, 11]
        });

        const marker = L.marker([t.lat, t.lng], { icon: customIcon }).addTo(appState.mapInstance);
        marker.bindPopup(`
            <div class="text-xs p-1 font-sans">
                <div class="font-mono font-bold text-[#5B21B6]">${t.ticket_number}</div>
                <div class="font-bold text-[#1E1B4B] mt-0.5">${t.category_name}</div>
                <div class="text-[#6B7280] mt-0.5">${t.description}</div>
                <div class="text-[#6B7280] mt-1">Landmark: ${t.address_landmark}</div>
                <div class="text-[#6B7280]">Status: <span class="font-bold uppercase">${t.status}</span></div>
            </div>
        `);
        appState.mapMarkers.push(marker);
    });

    setTimeout(() => {
        appState.mapInstance.invalidateSize();
    }, 200);
}

// 11. Chart.js Category Breakdown in Royal Palette
async function loadCategoryChart() {
    try {
        const res = await fetch('/api/analytics/performance');
        const data = await res.json();
        const dist = data.performance.category_distribution;

        const ctx = document.getElementById('categoryChart');
        if (!ctx) return;

        if (appState.categoryChartInstance) {
            appState.categoryChartInstance.destroy();
        }

        appState.categoryChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: dist.map(d => d.name),
                datasets: [{
                    data: dist.map(d => d.count),
                    backgroundColor: [
                        '#EF4444', // leak
                        '#F59E0B', // contamination
                        '#5B21B6', // royal purple
                        '#7C3AED', // secondary purple
                        '#A78BFA'  // elegant lavender
                    ],
                    borderWidth: 2,
                    borderColor: '#FFFFFF'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 10, font: { size: 10 }, color: '#1E1B4B' }
                    }
                }
            }
        });

        // Also populate Leaderboard
        const lbContainer = document.getElementById('technician-leaderboard-container');
        if (lbContainer && data.performance.technician_leaderboard) {
            lbContainer.innerHTML = data.performance.technician_leaderboard.map((tech, idx) => `
            <div class="flex items-center justify-between p-2.5 rounded-xl border border-[#DDD6FE] bg-white">
                <div class="flex items-center space-x-2.5">
                    <span class="w-6 h-6 rounded-full bg-[#EDE9FE] text-[#5B21B6] font-bold text-xs flex items-center justify-center">#${idx + 1}</span>
                    <div>
                        <div class="text-xs font-bold text-[#1E1B4B]">${tech.name}</div>
                        <div class="text-[10px] text-[#6B7280]">${tech.phone}</div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-xs font-bold text-emerald-600">${tech.completed_jobs} Jobs Resolved</div>
                    <div class="text-[10px] text-amber-500 font-semibold">⭐ ${tech.avg_rating} Rating</div>
                </div>
            </div>
            `).join('');
        }
    } catch (err) {
        console.error('Failed to load chart', err);
    }
}

// 12. Audit Logs
async function loadAuditLogs() {
    try {
        const res = await fetch('/api/audit-logs');
        const data = await res.json();
        const container = document.getElementById('audit-logs-list');
        if (!container) return;

        container.innerHTML = data.logs.map(l => `
        <div class="p-1.5 hover:bg-[#F5F3FF] rounded transition flex items-start space-x-2 border-b border-[#DDD6FE]/40">
            <span class="text-[10px] text-[#A78BFA] font-mono flex-shrink-0">${formatDate(l.timestamp)}</span>
            <span class="text-[10px] font-bold text-[#5B21B6] bg-[#EDE9FE] px-1.5 py-0.2 rounded border border-[#DDD6FE]">${l.action}</span>
            <span class="text-[11px] text-[#1E1B4B] flex-grow">${l.details}</span>
            <span class="text-[10px] text-[#6B7280]">${l.user_name}</span>
        </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load audit logs', err);
    }
}

// ====================================================================
// 13. Service-Team Field Console
// ====================================================================

async function loadTechnicianJobs() {
    try {
        const res = await fetch(`/api/complaints?role=technician&user_id=${appState.currentUser.id}`);
        const data = await res.json();
        appState.allTechnicianJobs = data.complaints;
        renderTechnicianJobs();
    } catch (err) {
        console.error('Failed to load technician jobs', err);
    }
}

function filterTechJobs(type, val) {
    appState.techFilters[type] = val;

    document.querySelectorAll(`.tech-filter-${type === 'priority' ? 'prio' : 'stat'}`).forEach(btn => {
        btn.classList.remove('bg-[#5B21B6]', 'text-white');
        btn.classList.add('bg-[#F5F3FF]', 'text-[#1E1B4B]');
    });

    event.target.classList.add('bg-[#5B21B6]', 'text-white');
    event.target.classList.remove('bg-[#F5F3FF]', 'text-[#1E1B4B]');

    renderTechnicianJobs();
}

function renderTechnicianJobs() {
    const container = document.getElementById('technician-jobs-list');
    if (!container) return;

    let list = appState.allTechnicianJobs || [];

    if (appState.techFilters.priority !== 'all') {
        list = list.filter(j => j.priority === appState.techFilters.priority);
    }

    if (appState.techFilters.status !== 'all') {
        if (appState.techFilters.status === 'pending') {
            list = list.filter(j => ['submitted', 'clustered', 'assigned'].includes(j.status));
        } else if (appState.techFilters.status === 'in_progress') {
            list = list.filter(j => j.status === 'in_progress');
        } else if (appState.techFilters.status === 'resolved') {
            list = list.filter(j => ['resolved', 'closed'].includes(j.status));
        }
    }

    document.getElementById('tech-job-count').textContent = `${list.length} Orders in Queue`;

    if (list.length === 0) {
        container.innerHTML = `
        <div class="text-center py-10 border border-dashed border-[#DDD6FE] rounded-2xl p-6 text-[#6B7280]">
            <i data-lucide="check-check" class="w-10 h-10 mx-auto stroke-1 mb-2 text-[#A78BFA]"></i>
            <h4 class="text-xs font-bold text-[#1E1B4B]">No Work Orders in This Filter Queue</h4>
            <p class="text-[11px] text-[#6B7280] mt-1">All assigned tasks for this criteria have been processed.</p>
        </div>`;
        lucide.createIcons();
        return;
    }

    container.innerHTML = list.map(job => {
        const isResolved = ['resolved', 'closed'].includes(job.status);
        const isEscalated = job.escalated === 1;

        return `
        <div class="border border-[#DDD6FE] rounded-2xl p-5 bg-white hover:border-[#A78BFA] transition shadow-xs space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[#DDD6FE] pb-3 gap-2">
                <div class="flex items-center space-x-2">
                    <span class="font-mono font-bold text-xs text-[#5B21B6] bg-[#F5F3FF] px-2 py-0.5 rounded-md border border-[#DDD6FE]">${job.ticket_number}</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${getBadgeClass(job.priority)} uppercase">${job.priority}</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${getBadgeClass(job.status)} uppercase">${job.status}</span>
                    ${isEscalated ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300">Escalated</span>` : ''}
                </div>
                <div class="text-xs text-[#6B7280] font-mono">Observed: ${job.incident_time || formatDate(job.created_at)}</div>
            </div>

            <div class="space-y-1.5">
                <h3 class="text-sm font-bold text-[#1E1B4B]">${job.category_name}</h3>
                <p class="text-xs text-[#6B7280]">${job.description}</p>
            </div>

            <!-- Privacy Masking Display -->
            <div class="bg-[#F5F3FF] border border-[#DDD6FE] rounded-xl p-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                <div>
                    <span class="text-[#6B7280] block text-[10px] uppercase font-semibold">Field Navigation Landmark:</span>
                    <strong class="text-[#1E1B4B] flex items-center mt-0.5">
                        <i data-lucide="map-pin" class="w-3.5 h-3.5 mr-1 text-[#7C3AED]"></i>
                        ${job.address_landmark}
                    </strong>
                </div>
                <div>
                    <span class="text-[#6B7280] block text-[10px] uppercase font-semibold">Resident Phone (Privacy Protected):</span>
                    <div class="font-mono text-[#5B21B6] font-semibold mt-0.5 flex items-center">
                        <i data-lucide="lock" class="w-3 h-3 mr-1 text-[#7C3AED]"></i>
                        ${job.resident_phone || '[Protected]'}
                    </div>
                </div>
            </div>

            <!-- Technician Actions -->
            <div class="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-[#DDD6FE]">
                ${!isResolved ? `
                    <button onclick="updateTechnicianStatus(${job.id}, 'on_site')" class="btn-royal-secondary px-3.5 py-2 text-xs flex items-center space-x-1.5">
                        <i data-lucide="navigation" class="w-3.5 h-3.5 text-[#5B21B6]"></i>
                        <span>Mark Arrived On-Site</span>
                    </button>
                    <button onclick="openEscalateModal(${job.id})" class="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold rounded-xl flex items-center space-x-1.5 transition">
                        <i data-lucide="alert-triangle" class="w-3.5 h-3.5"></i>
                        <span>Escalate Overdue Work</span>
                    </button>
                    <button onclick="openResolveModal(${job.id})" class="btn-royal-primary px-4 py-2 text-xs flex items-center space-x-1.5">
                        <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
                        <span>Complete Job & Record Resolution</span>
                    </button>
                ` : `
                    <span class="text-xs font-semibold text-emerald-700 flex items-center bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
                        <i data-lucide="check" class="w-4 h-4 mr-1"></i> Resolved & Logged
                    </span>
                `}
            </div>
        </div>
        `;
    }).join('');

    lucide.createIcons();
}

async function updateTechnicianStatus(complaintId, status) {
    try {
        const res = await fetch('/api/assignments/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ complaint_id: complaintId, technician_id: 6, status: status, notes: "Arrived at location. Began inspection." })
        });
        const data = await res.json();
        if (data.success) {
            alert("Status updated to 'Arrived On-Site'!");
            loadTechnicianJobs();
        }
    } catch (err) {
        alert('Error: ' + err);
    }
}

function openResolveModal(complaintId) {
    document.getElementById('resolve-complaint-id').value = complaintId;
    document.getElementById('resolve-modal').classList.remove('hidden');
    lucide.createIcons();
}

function closeResolveModal() {
    document.getElementById('resolve-modal').classList.add('hidden');
}

async function submitWorkOrderResolution(e) {
    e.preventDefault();
    const complaintId = document.getElementById('resolve-complaint-id').value;
    const notes = document.getElementById('resolve-notes').value;
    const photoUrl = document.getElementById('resolve-photo-url').value;

    try {
        const res = await fetch('/api/assignments/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                complaint_id: complaintId,
                technician_id: 6,
                status: 'completed',
                notes: notes,
                proof_photo_url: photoUrl
            })
        });
        const data = await res.json();
        if (data.success) {
            closeResolveModal();
            alert('Work Order successfully completed! All affected neighborhood residents updated.');
            loadTechnicianJobs();
        }
    } catch (err) {
        alert('Failed: ' + err);
    }
}

function openEscalateModal(complaintId) {
    document.getElementById('escalate-complaint-id').value = complaintId;
    document.getElementById('escalate-modal').classList.remove('hidden');
    lucide.createIcons();
}

function closeEscalateModal() {
    document.getElementById('escalate-modal').classList.add('hidden');
}

async function submitWorkOrderEscalation(e) {
    e.preventDefault();
    const complaintId = document.getElementById('escalate-complaint-id').value;
    const reason = document.getElementById('escalate-reason').value;

    try {
        const res = await fetch('/api/complaints/escalate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                complaint_id: complaintId,
                technician_id: 6,
                reason: reason
            })
        });
        const data = await res.json();
        if (data.success) {
            closeEscalateModal();
            alert('Work order escalated to Ward Supervisor.');
            loadTechnicianJobs();
        }
    } catch (err) {
        alert('Failed: ' + err);
    }
}

// ====================================================================
// 14. Reports & SLA Dashboard
// ====================================================================

async function loadReportsDashboard() {
    try {
        const [locRes, perfRes] = await Promise.all([
            fetch('/api/analytics/locality'),
            fetch('/api/analytics/performance')
        ]);
        const locData = await locRes.json();
        const perfData = await perfRes.json();

        // Update top summary metrics
        const slaElem = document.getElementById('report-sla-metric');
        if (slaElem) slaElem.textContent = `${perfData.performance.sla_compliance_rate || 94.4}%`;

        const mttrVal = perfData.performance.avg_mttr_hours || perfData.performance.mean_time_to_resolve_hours || 4.0;
        const mttrElem = document.getElementById('report-mttr-metric');
        if (mttrElem) mttrElem.textContent = `${mttrVal} hrs`;

        // Populate report table
        const tbody = document.getElementById('report-table-tbody');
        if (tbody) {
            tbody.innerHTML = locData.localities.map(l => `
                <tr class="hover:bg-[#F5F3FF] transition">
                    <td class="py-2.5 px-3 font-mono font-bold text-[#5B21B6]">${l.zone_code}</td>
                    <td class="py-2.5 px-3 font-semibold text-[#1E1B4B]">${l.locality_name}</td>
                    <td class="py-2.5 px-3 text-[#6B7280] font-mono text-[11px]">${l.pipeline_grid}</td>
                    <td class="py-2.5 px-3 font-semibold text-[#1E1B4B]">${l.total_complaints} reports</td>
                    <td class="py-2.5 px-3">
                        <span class="font-bold text-[#5B21B6]">${l.health_score}%</span>
                    </td>
                    <td class="py-2.5 px-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${l.health_score >= 80 ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : (l.health_score >= 60 ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-rose-50 text-rose-800 border border-rose-200')}">
                            ${l.status_tag}
                        </span>
                    </td>
                    <td class="py-2.5 px-3 text-[#6B7280]">${l.supervisor_name}</td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Failed to load reports dashboard', err);
    }
}

function exportReportPDF() {
    window.print();
}

// ====================================================================
// 15. Shared Helpers
// ====================================================================

async function loadClusters() {
    try {
        const res = await fetch('/api/clusters');
        const data = await res.json();
        appState.clusters = data.clusters;
        updateResidentClusterAlert();
    } catch (err) {
        console.error(err);
    }
}

function getBadgeClass(status) {
    switch (status) {
        case 'critical': return 'badge-critical';
        case 'high': return 'badge-high';
        case 'medium': return 'badge-medium';
        case 'low': return 'badge-low';
        case 'submitted': return 'badge-submitted';
        case 'clustered': return 'badge-clustered';
        case 'assigned': return 'badge-assigned';
        case 'in_progress': return 'badge-in_progress';
        case 'resolved': return 'badge-resolved';
        case 'closed': return 'badge-closed';
        default: return 'bg-[#F5F3FF] text-[#1E1B4B] border border-[#DDD6FE]';
    }
}

function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return isoStr;
    }
}
