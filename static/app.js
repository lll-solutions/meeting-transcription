// Auth State
let currentUser = null;
let authToken = localStorage.getItem('auth_token');
let authUser = JSON.parse(localStorage.getItem('auth_user') || 'null');
let featureFlags = {};

// Plugin State
let availablePlugins = [];
let pluginDetails = {};
let defaultPlugin = 'educational'; // Fallback default

// ==========================================
// PLUGIN SYSTEM
// ==========================================

async function loadPlugins() {
    try {
        availablePlugins = await apiCall('/api/plugins');

        // Load details for each plugin
        for (const plugin of availablePlugins) {
            pluginDetails[plugin.name] = await apiCall(`/api/plugins/${plugin.name}`);
        }

        // Populate all plugin dropdowns
        populatePluginDropdowns();
    } catch (error) {
        console.error('Failed to load plugins:', error);
        availablePlugins = [{ name: 'educational', display_name: 'Educational Class' }];
    }
}

function populatePluginDropdowns() {
    const dropdowns = [
        'new-meeting-plugin',
        'schedule-plugin',
        'upload-plugin',
        'settings-default-plugin'
    ];

    dropdowns.forEach(dropdownId => {
        const dropdown = document.getElementById(dropdownId);
        if (dropdown) {
            dropdown.innerHTML = availablePlugins.map(plugin =>
                `<option value="${plugin.name}">${plugin.display_name}</option>`
            ).join('');

            // Set default value
            if (defaultPlugin) {
                dropdown.value = defaultPlugin;
            }
        }
    });

    // Trigger metadata field updates for modals
    updateNewMeetingMetadataFields();
    updateScheduleMetadataFields();
    updateUploadMetadataFields();
}

function renderMetadataFields(pluginName, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!pluginName || !pluginDetails[pluginName]) {
        container.innerHTML = '';
        return;
    }

    const plugin = pluginDetails[pluginName];
    const schema = plugin.metadata_schema || {};

    let html = '';
    for (const [fieldName, fieldDef] of Object.entries(schema)) {
        const inputId = `${containerId}-${fieldName}`;
        const requiredMark = fieldDef.required ? '<span style="color: #ef4444;">*</span>' : '';

        html += `<div class="form-group">`;
        html += `<label for="${inputId}">${fieldDef.label || fieldName} ${requiredMark}</label>`;

        if (fieldDef.type === 'select') {
            html += `<select id="${inputId}" ${fieldDef.required ? 'required' : ''}
                style="width: 100%; padding: 0.75rem 1rem; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary); font-family: inherit; font-size: 0.9375rem;">`;

            if (!fieldDef.required) {
                html += `<option value="">(Optional)</option>`;
            }

            fieldDef.options.forEach(opt => {
                const selected = opt === fieldDef.default ? 'selected' : '';
                html += `<option value="${opt}" ${selected}>${opt}</option>`;
            });
            html += `</select>`;
        } else if (fieldDef.type === 'text' || fieldDef.type === 'string') {
            html += `<input type="text" id="${inputId}"
                placeholder="${fieldDef.description || ''}"
                ${fieldDef.required ? 'required' : ''}
                value="${fieldDef.default || ''}">`;
        } else if (fieldDef.type === 'integer') {
            html += `<input type="number" id="${inputId}"
                placeholder="${fieldDef.description || ''}"
                ${fieldDef.required ? 'required' : ''}
                value="${fieldDef.default || ''}">`;
        } else {
            html += `<input type="text" id="${inputId}"
                placeholder="${fieldDef.description || ''}"
                ${fieldDef.required ? 'required' : ''}
                value="${fieldDef.default || ''}">`;
        }

        if (fieldDef.description) {
            html += `<p style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">${fieldDef.description}</p>`;
        }

        html += `</div>`;
    }

    container.innerHTML = html;
}

function getMetadataFromFields(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return {};

    const metadata = {};
    const inputs = container.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        const fieldName = input.id.replace(`${containerId}-`, '');
        let value = input.value;

        // Convert to appropriate type
        if (input.type === 'number') {
            value = parseInt(value);
        } else if (value === '') {
            value = undefined; // Don't include empty values
        }

        if (value !== undefined) {
            metadata[fieldName] = value;
        }
    });

    return metadata;
}

function updateNewMeetingMetadataFields() {
    const pluginName = document.getElementById('new-meeting-plugin')?.value;
    renderMetadataFields(pluginName, 'new-meeting-metadata-fields');
}

function updateScheduleMetadataFields() {
    const pluginName = document.getElementById('schedule-plugin')?.value;
    renderMetadataFields(pluginName, 'schedule-metadata-fields');
}

function updateUploadMetadataFields() {
    const pluginName = document.getElementById('upload-plugin')?.value;
    renderMetadataFields(pluginName, 'upload-metadata-fields');
}

// Initialize
async function initApp() {
    // Fetch feature flags first
    await fetchFeatureFlags();

    // Load plugins
    await loadPlugins();

    if (authToken && authUser) {
        currentUser = authUser;

        // Set timezone from user data
        if (currentUser.timezone) {
            currentUserTimezone = currentUser.timezone;
        }

        // Set default plugin from user data
        if (currentUser.default_plugin) {
            defaultPlugin = currentUser.default_plugin;
            populatePluginDropdowns(); // Re-populate with correct default
        }

        showDashboard(currentUser);
        loadMeetings();

        // Start polling for scheduled meetings updates every 60 seconds
        setInterval(() => {
            if (document.getElementById('dashboard-view').style.display !== 'none') {
                loadScheduledMeetings();
            }
        }, 60000);
    } else {
        showSignIn();
    }
}

// Fetch feature flags from backend
async function fetchFeatureFlags() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        featureFlags = config.features || {};

        // Apply feature flags to UI
        applyFeatureFlags();
    } catch (error) {
        console.error('Failed to fetch feature flags:', error);
        // Default to all features enabled if fetch fails
        featureFlags = { botJoining: true };
    }
}

// Apply feature flags to UI elements
function applyFeatureFlags() {
    const newMeetingBtn = document.getElementById('new-meeting-bot-btn');
    const scheduleBtn = document.getElementById('schedule-bot-btn');

    if (newMeetingBtn) {
        if (featureFlags.botJoining === false) {
            newMeetingBtn.style.display = 'none';
        } else {
            newMeetingBtn.style.display = 'flex';
        }
    }

    if (scheduleBtn) {
        if (featureFlags.botJoining === false) {
            scheduleBtn.style.display = 'none';
        } else {
            scheduleBtn.style.display = 'flex';
        }
    }
}

// Handle Login Form Submission
async function handleLogin(event) {
    event.preventDefault();

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        showToast('Please enter email and password', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            // Success
            authToken = data.token;
            currentUser = data.user;

            localStorage.setItem('auth_token', authToken);
            localStorage.setItem('auth_user', JSON.stringify(currentUser));

            // Set timezone from user data
            if (currentUser.timezone) {
                currentUserTimezone = currentUser.timezone;
            }

            showDashboard(currentUser);
            loadMeetings();
            showToast('Signed in successfully', 'success');
        } else {
            showToast(data.error || 'Login failed', 'error');
            showSignIn();
        }
    } catch (error) {
        console.error('Login error:', error);
        showToast('Login failed: ' + error.message, 'error');
        showSignIn();
    }
}

// Sign out
function signOut() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    authToken = null;
    currentUser = null;
    showSignIn();
    showToast('Signed out successfully', 'success');
}

// Get API Headers with Auth
function getHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };

    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    return headers;
}

// API call helper
async function apiCall(endpoint, options = {}) {
    const headers = {
        ...getHeaders(), // Use the new getHeaders function
        ...options.headers
    };

    const response = await fetch(endpoint, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(error.error || error.message || 'Request failed');
    }

    return response.json();
}

// Load meetings
async function loadMeetings() {
    try {
        const meetings = await apiCall('/api/meetings');
        renderMeetings(meetings);
    } catch (error) {
        console.error('Load meetings error:', error);
        // If authentication fails, force sign out
        if (error.message.includes('Authentication') || error.message.includes('Unauthorized')) {
            signOut();
            showToast('Session expired. Please sign in again.', 'error');
        }
    }
}

// Render meetings list (separated into uploads and bot meetings)
function renderMeetings(meetings) {
    const uploadsContainer = document.getElementById('uploads-list');
    const meetingsContainer = document.getElementById('meetings-list');

    if (!meetings || meetings.length === 0) {
        uploadsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📄</div>
                <p>No uploads yet</p>
            </div>
        `;
        meetingsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>No bot meetings yet</p>
            </div>
        `;
        return;
    }

    // Separate uploads from bot meetings
    const uploads = meetings.filter(m => m.id && m.id.startsWith('upload-'));
    const botMeetings = meetings.filter(m => !m.id || !m.id.startsWith('upload-'));

    // Render uploads
    if (uploads.length === 0) {
        uploadsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📄</div>
                <p>No uploads yet</p>
            </div>
        `;
    } else {
        uploadsContainer.innerHTML = uploads.map(meeting => `
            <div class="meeting-item" data-meeting-id="${meeting.id}" style="cursor: pointer;">
                <div class="meeting-info">
                    <div class="meeting-title">${meeting.bot_name || meeting.title || 'Uploaded Transcript'}</div>
                    <div class="meeting-meta">${formatDate(meeting.created_at)}</div>
                </div>
                <span class="meeting-status ${meeting.status}">${meeting.status}</span>
            </div>
        `).join('');
    }

    // Render bot meetings
    if (botMeetings.length === 0) {
        meetingsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>No bot meetings yet</p>
            </div>
        `;
    } else {
        meetingsContainer.innerHTML = botMeetings.map(meeting => `
            <div class="meeting-item" data-meeting-id="${meeting.id}" style="cursor: pointer;">
                <div class="meeting-info">
                    <div class="meeting-title">${meeting.bot_name || 'Meeting'}</div>
                    <div class="meeting-meta">${formatDate(meeting.created_at)}</div>
                </div>
                <span class="meeting-status ${meeting.status}">${meeting.status}</span>
            </div>
        `).join('');
    }
}

function viewMeeting(meetingId) {
    window.location.href = `/ui/meetings/${meetingId}`;
}

// ==========================================
// NEW MEETING BOT MODAL
// ==========================================

function openNewMeetingModal() {
    document.getElementById('new-meeting-url').value = '';
    document.getElementById('new-meeting-bot-name').value = '';
    document.getElementById('new-meeting-validation-error').style.display = 'none';

    // Set default plugin
    if (defaultPlugin) {
        document.getElementById('new-meeting-plugin').value = defaultPlugin;
        updateNewMeetingMetadataFields();
    }

    document.getElementById('new-meeting-modal').classList.add('show');
}

function closeNewMeetingModal() {
    document.getElementById('new-meeting-modal').classList.remove('show');
}

async function submitNewMeeting() {
    const meetingUrl = document.getElementById('new-meeting-url').value.trim();
    const botName = document.getElementById('new-meeting-bot-name').value.trim();
    const pluginName = document.getElementById('new-meeting-plugin').value;
    const errorEl = document.getElementById('new-meeting-validation-error');

    // Validation
    if (!meetingUrl) {
        errorEl.textContent = 'Please enter a meeting URL';
        errorEl.style.display = 'block';
        return;
    }

    if (!pluginName) {
        errorEl.textContent = 'Please select a plugin';
        errorEl.style.display = 'block';
        return;
    }

    errorEl.style.display = 'none';

    // Get metadata from dynamic fields
    const metadata = getMetadataFromFields('new-meeting-metadata-fields');

    const submitBtn = document.getElementById('new-meeting-submit-btn');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Creating...';

    try {
        const payload = {
            meeting_url: meetingUrl,
            bot_name: botName || 'Meeting Assistant',
            plugin: pluginName,
            metadata: metadata
        };

        const meeting = await apiCall('/api/meetings', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        closeNewMeetingModal();
        showToast('Meeting bot created!', 'success');
        loadMeetings();
    } catch (error) {
        console.error('Create meeting error:', error);
        showToast('Failed to create meeting: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// UI Helpers
function showSignIn() {
    document.getElementById('signin-view').style.display = 'block';
    document.getElementById('loading-view').style.display = 'none';
    document.getElementById('dashboard-view').style.display = 'none';
}

function showLoading() {
    document.getElementById('signin-view').style.display = 'none';
    document.getElementById('loading-view').style.display = 'block';
    document.getElementById('dashboard-view').style.display = 'none';
}

function showDashboard(user) {
    document.getElementById('signin-view').style.display = 'none';
    document.getElementById('loading-view').style.display = 'none';
    document.getElementById('dashboard-view').style.display = 'block';

    // Update user info
    document.getElementById('user-name').textContent = user.name || user.email || 'User';
    document.getElementById('user-email').textContent = user.email;

    const avatarEl = document.getElementById('user-avatar');
    if (user.photoURL) { // Assuming user object might still have photoURL for display
        avatarEl.innerHTML = `<img src="${user.photoURL}" alt="Avatar">`;
    } else {
        avatarEl.textContent = (user.name || user.email || '?')[0].toUpperCase();
    }

    // Store user timezone for scheduling
    if (user.timezone) {
        currentUserTimezone = user.timezone;
    }

    // Load scheduled meetings
    loadScheduledMeetings();

    // Apply feature flags after dashboard is shown
    applyFeatureFlags();
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const timezone = currentUserTimezone || 'America/New_York';
    const options = {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: timezone,
        timeZoneName: 'short'
    };
    return date.toLocaleString('en-US', options);
}

// ==========================================
// Upload Transcript Functions
// ==========================================

let selectedFile = null;
let transcriptData = null;

function showUploadModal() {
    // Set default plugin
    if (defaultPlugin) {
        document.getElementById('upload-plugin').value = defaultPlugin;
        updateUploadMetadataFields();
    }

    document.getElementById('upload-modal').classList.add('show');
}

function hideUploadModal() {
    document.getElementById('upload-modal').classList.remove('show');
    clearFile();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        processSelectedFile(file);
    }
}

function processSelectedFile(file) {
    const fileName = file.name.toLowerCase();
    const isJson = fileName.endsWith('.json');
    const isVtt = fileName.endsWith('.vtt');
    const isTxt = fileName.endsWith('.txt');

    if (!isJson && !isVtt && !isTxt) {
        showToast('Please select a JSON, VTT, or TXT file', 'error');
        return;
    }

    selectedFile = file;

    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const fileContent = e.target.result;

            // For JSON files, parse as JSON
            if (isJson) {
                transcriptData = JSON.parse(fileContent);
            } else {
                // For VTT and TXT files, send as text string
                transcriptData = fileContent;
            }

            showFilePreview(file, transcriptData);
        } catch (err) {
            showToast(`Invalid ${isJson ? 'JSON' : 'text'} file: ${err.message}`, 'error');
            clearFile();
        }
    };
    reader.readAsText(file);
}

function showFilePreview(file, data) {
    document.getElementById('upload-zone').style.display = 'none';
    document.getElementById('file-preview').style.display = 'block';
    document.getElementById('file-name').textContent = file.name;

    // Calculate stats
    let statsHtml = '';

    if (Array.isArray(data)) {
        // JSON transcript - show detailed stats
        let segmentCount = data.length;
        let wordCount = 0;
        let participants = new Set();
        let duration = 0;

        data.forEach(segment => {
            if (segment.words) {
                wordCount += segment.words.length;
            }
            if (segment.participant?.name) {
                participants.add(segment.participant.name);
            }
            // Calculate duration from timestamps
            if (segment.words?.length > 0) {
                const lastWord = segment.words[segment.words.length - 1];
                const endTime = lastWord.end_timestamp?.relative || 0;
                if (endTime > duration) duration = endTime;
            }
        });

        const durationMin = Math.floor(duration / 60);
        const durationSec = Math.floor(duration % 60);

        statsHtml = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                <div>📊 ${segmentCount} segments</div>
                <div>📝 ${wordCount.toLocaleString()} words</div>
                <div>👥 ${participants.size} participants</div>
                <div>⏱️ ${durationMin}m ${durationSec}s</div>
            </div>
        `;
    } else if (typeof data === 'string') {
        // Text transcript (VTT or TXT) - show basic stats
        const lines = data.split('\n').filter(line => line.trim().length > 0);
        const wordCount = data.split(/\s+/).filter(w => w.length > 0).length;
        const fileSize = (file.size / 1024).toFixed(1);
        const format = file.name.toLowerCase().endsWith('.vtt') ? 'VTT' : 'Text';

        statsHtml = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                <div>📄 ${format} format</div>
                <div>📝 ${wordCount.toLocaleString()} words</div>
                <div>📏 ${lines.length} lines</div>
                <div>💾 ${fileSize} KB</div>
            </div>
        `;
    }

    document.getElementById('file-stats').innerHTML = statsHtml;
    document.getElementById('process-btn').disabled = false;
}

function clearFile() {
    selectedFile = null;
    transcriptData = null;
    document.getElementById('file-input').value = '';
    document.getElementById('upload-zone').style.display = 'block';
    document.getElementById('file-preview').style.display = 'none';
    document.getElementById('process-btn').disabled = true;
    document.getElementById('meeting-title').value = '';
}

async function processUpload() {
    if (!transcriptData) {
        showToast('No file selected', 'error');
        return;
    }

    // Save transcript data and form values before modal is hidden
    const dataToUpload = transcriptData;
    const title = document.getElementById('meeting-title').value || `Upload ${new Date().toLocaleDateString()}`;
    const pluginName = document.getElementById('upload-plugin').value;
    const metadata = getMetadataFromFields('upload-metadata-fields');

    // Hide upload modal, show processing modal
    hideUploadModal();
    document.getElementById('processing-modal').classList.add('show');

    // Reset progress steps
    document.querySelectorAll('.progress-step').forEach(step => {
        step.classList.remove('active', 'complete');
    });

    try {
        updateProgress('upload', 'Uploading transcript...');

        // Submit for async processing
        const result = await apiCall('/api/transcripts/upload', {
            method: 'POST',
            body: JSON.stringify({
                transcript: dataToUpload,
                title: title,
                plugin: pluginName,
                metadata: metadata
            })
        });

        const meetingId = result.meeting_id;
        updateProgress('combine', 'Processing transcript...');

        // Poll for status
        await pollForCompletion(meetingId);

    } catch (error) {
        console.error('Upload error:', error);
        document.getElementById('processing-modal').classList.remove('show');
        showToast('Failed to process transcript: ' + error.message, 'error');
    }
}

async function pollForCompletion(meetingId) {
    const statusMap = {
        'queued': { step: 'upload', msg: 'Queued for processing...' },
        'processing': { step: 'summarize', msg: 'AI is analyzing content...' },
        'completed': { step: 'pdf', msg: 'Processing complete!' },
        'failed': { step: null, msg: 'Processing failed' }
    };

    let attempts = 0;
    const maxAttempts = 120; // 10 minutes max (5s intervals)

    while (attempts < maxAttempts) {
        try {
            const meeting = await apiCall(`/api/meetings/${meetingId}`);
            const status = meeting.status || 'processing';

            const statusInfo = statusMap[status] || { step: 'summarize', msg: `Status: ${status}` };

            if (statusInfo.step) {
                updateProgress(statusInfo.step, statusInfo.msg);
            }
            document.getElementById('processing-status').textContent = statusInfo.msg;

            if (status === 'completed') {
                // Mark all steps complete
                document.querySelectorAll('.progress-step').forEach(step => {
                    step.classList.add('complete');
                });

                setTimeout(() => {
                    document.getElementById('processing-modal').classList.remove('show');
                    showToast('Transcript processed successfully!', 'success');
                    loadMeetings();
                }, 1500);
                return;
            }

            if (status === 'failed') {
                document.getElementById('processing-modal').classList.remove('show');
                showToast('Processing failed: ' + (meeting.error || 'Unknown error'), 'error');
                return;
            }

            // Wait before next poll
            await new Promise(resolve => setTimeout(resolve, 5000));
            attempts++;

        } catch (error) {
            console.error('Poll error:', error);
            attempts++;
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
    }

    // Timeout
    document.getElementById('processing-modal').classList.remove('show');
    showToast('Processing is taking longer than expected. Check back later.', 'error');
}

function updateProgress(step, message) {
    document.getElementById('processing-status').textContent = message;

    const stepEl = document.querySelector(`.progress-step[data-step="${step}"]`);
    if (stepEl) {
        // Mark previous steps as complete
        let prevSibling = stepEl.previousElementSibling;
        while (prevSibling) {
            prevSibling.classList.remove('active');
            prevSibling.classList.add('complete');
            prevSibling = prevSibling.previousElementSibling;
        }
        stepEl.classList.add('active');
    }
}

// ==========================================
// Schedule Bot Functions
// ==========================================

let currentUserTimezone = 'America/New_York'; // Will be set from user data

function openScheduleModal() {
    // Ensure timezone label shows user's timezone
    updateTimezoneLabel();

    // Reset form
    document.getElementById('schedule-meeting-url').value = '';
    document.getElementById('schedule-bot-name').value = '';
    document.getElementById('schedule-datetime').value = '';
    document.getElementById('schedule-validation-error').style.display = 'none';

    // Set default plugin
    if (defaultPlugin) {
        document.getElementById('schedule-plugin').value = defaultPlugin;
        updateScheduleMetadataFields();
    }

    // Set min datetime to now
    setMinDatetime();

    document.getElementById('schedule-modal').classList.add('show');
}

function closeScheduleModal() {
    document.getElementById('schedule-modal').classList.remove('show');
}

function updateTimezoneLabel() {
    const label = document.getElementById('user-timezone-label');
    if (currentUserTimezone) {
        label.textContent = `(${currentUserTimezone})`;
    }
}

function setMinDatetime() {
    // Set min datetime to now + 5 minutes (in LOCAL time, not UTC)
    const now = new Date();
    now.setMinutes(now.getMinutes() + 5);

    // Format as YYYY-MM-DDTHH:MM in local timezone
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const minDateTime = `${year}-${month}-${day}T${hours}:${minutes}`;

    document.getElementById('schedule-datetime').min = minDateTime;
}

async function submitScheduledMeeting() {
    const meetingUrl = document.getElementById('schedule-meeting-url').value.trim();
    const botName = document.getElementById('schedule-bot-name').value.trim() || 'Meeting Assistant';
    const instructorName = document.getElementById('schedule-instructor-name').value.trim();
    const datetimeLocal = document.getElementById('schedule-datetime').value;
    const errorEl = document.getElementById('schedule-validation-error');

    // Validation
    if (!meetingUrl) {
        showValidationError(errorEl, 'Please enter a meeting URL');
        return;
    }

    if (!datetimeLocal) {
        showValidationError(errorEl, 'Please select a date and time');
        return;
    }

    // Validate meeting URL format
    if (!isValidMeetingUrl(meetingUrl)) {
        showValidationError(errorEl, 'Please enter a valid meeting URL (Zoom, Google Meet, Teams, etc.)');
        return;
    }

    // Validate datetime is in future
    const selectedDate = new Date(datetimeLocal);
    const now = new Date();
    if (selectedDate <= now) {
        showValidationError(errorEl, 'Please select a time in the future');
        return;
    }

    // Hide error if validation passed
    errorEl.style.display = 'none';

    // Submit
    await scheduleBot(meetingUrl, botName, instructorName, datetimeLocal);
}

function showValidationError(errorEl, message) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

function isValidMeetingUrl(url) {
    try {
        const urlObj = new URL(url);
        // Check for common meeting platform domains
        const validDomains = [
            'zoom.us', 'meet.google.com', 'teams.microsoft.com',
            'webex.com', 'whereby.com', 'meet.jio.com'
        ];
        return validDomains.some(domain => urlObj.hostname.includes(domain));
    } catch {
        return false;
    }
}

async function scheduleBot(meetingUrl, botName, instructorName, datetimeLocal) {
    const submitBtn = document.getElementById('schedule-submit-btn');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Scheduling...';

    try {
        // Convert datetime-local to ISO string for API
        // datetime-local format: "2024-12-10T15:30"
        // Need to send as ISO8601: "2024-12-10T15:30:00"
        const isoDateTime = datetimeLocal + ':00';

        // Get plugin and metadata
        const pluginName = document.getElementById('schedule-plugin').value;
        const metadata = getMetadataFromFields('schedule-metadata-fields');

        const payload = {
            meeting_url: meetingUrl,
            bot_name: botName,
            scheduled_time: isoDateTime,
            plugin: pluginName,
            metadata: metadata
        };

        // Add instructor name if provided
        if (instructorName) {
            payload.instructor_name = instructorName;
        }

        const response = await apiCall('/api/scheduled-meetings', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        closeScheduleModal();
        showToast('Bot scheduled successfully! It will join at the specified time.', 'success');

        // Reload scheduled meetings list
        loadScheduledMeetings();

    } catch (error) {
        console.error('Schedule bot error:', error);
        showToast('Failed to schedule bot: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// ==========================================
// SETTINGS MODAL
// ==========================================

function openSettingsModal() {
    // Load current timezone setting
    const timezoneSelect = document.getElementById('settings-timezone');
    if (currentUserTimezone) {
        timezoneSelect.value = currentUserTimezone;
    }

    // Load current default plugin
    const pluginSelect = document.getElementById('settings-default-plugin');
    if (defaultPlugin && pluginSelect) {
        pluginSelect.value = defaultPlugin;
    }

    // Hide success/error messages
    document.getElementById('settings-success').style.display = 'none';
    document.getElementById('settings-error').style.display = 'none';

    // Show modal
    document.getElementById('settings-modal').classList.add('show');
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.remove('show');
}

async function saveSettings() {
    const timezone = document.getElementById('settings-timezone').value;
    const plugin = document.getElementById('settings-default-plugin').value;
    const saveBtn = document.getElementById('settings-save-btn');
    const successEl = document.getElementById('settings-success');
    const errorEl = document.getElementById('settings-error');

    // Hide previous messages
    successEl.style.display = 'none';
    errorEl.style.display = 'none';

    // Disable button while saving
    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = '💾 Saving...';

    try {
        const response = await apiCall('/api/users/me', {
            method: 'PATCH',
            body: JSON.stringify({
                timezone: timezone,
                default_plugin: plugin
            })
        });

        // Update local settings
        currentUserTimezone = timezone;
        defaultPlugin = plugin;
        updateTimezoneLabel();
        populatePluginDropdowns(); // Refresh all dropdowns with new default

        // Update currentUser and localStorage
        if (currentUser) {
            currentUser.timezone = timezone;
            currentUser.default_plugin = plugin;
            localStorage.setItem('auth_user', JSON.stringify(currentUser));
        }

        // Show success message
        successEl.style.display = 'block';
        showToast('Settings saved successfully', 'success');

        // Reload meetings to show updated times
        setTimeout(() => {
            loadMeetings();
            closeSettingsModal();
        }, 1000);

    } catch (error) {
        console.error('Save settings error:', error);
        errorEl.textContent = 'Failed to save settings: ' + error.message;
        errorEl.style.display = 'block';
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
    }
}

async function loadScheduledMeetings() {
    try {
        const response = await apiCall('/api/scheduled-meetings?status=scheduled');
        const meetings = Array.isArray(response) ? response : [];

        renderScheduledMeetings(meetings);

        // Refresh countdown timers every 30 seconds
        if (meetings.length > 0) {
            clearInterval(window.countdownInterval);
            window.countdownInterval = setInterval(() => {
                updateCountdownTimers(meetings);
            }, 30000);
        }
    } catch (error) {
        console.error('Load scheduled meetings error:', error);
    }
}

function renderScheduledMeetings(meetings) {
    const section = document.getElementById('scheduled-meetings-section');
    const listContainer = document.getElementById('scheduled-meetings-list');

    if (!meetings || meetings.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';

    listContainer.innerHTML = meetings.map(meeting => {
        const countdown = formatCountdown(meeting.scheduled_time);
        const urlDisplay = truncateUrl(meeting.meeting_url, 40);

        return `
            <div class="scheduled-meeting-item" data-meeting-id="${meeting.id}">
                <div class="scheduled-meeting-info">
                    <div class="scheduled-meeting-title">${escapeHtml(meeting.bot_name)}</div>
                    <div class="scheduled-meeting-meta">
                        🔗 ${urlDisplay}
                    </div>
                    <div class="scheduled-meeting-meta">
                        📅 ${formatScheduledTime(meeting.scheduled_time, meeting.user_timezone)}
                    </div>
                    <div class="scheduled-meeting-countdown" data-time="${meeting.scheduled_time}">
                        ⏱️ ${countdown}
                    </div>
                </div>
                <div class="scheduled-meeting-actions">
                    <span class="meeting-status ${meeting.status}">
                        ${meeting.status}
                    </span>
                    <button class="btn btn-danger cancel-scheduled-meeting-btn"
                        style="padding: 0.5rem 0.75rem; font-size: 0.875rem;"
                        data-meeting-id="${meeting.id}">
                        ✕ Cancel
                    </button>
                </div>
            </div>
        `;
    }).join('');

    // Start countdown updates
    updateCountdownTimers(meetings);
}

function updateCountdownTimers(meetings) {
    document.querySelectorAll('.scheduled-meeting-countdown').forEach(el => {
        const scheduledTime = el.getAttribute('data-time');
        const countdown = formatCountdown(scheduledTime);
        el.textContent = `⏱️ ${countdown}`;
    });
}

function formatScheduledTime(isoTime, timezone) {
    try {
        const date = new Date(isoTime);
        const options = {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZone: timezone
        };
        return date.toLocaleDateString('en-US', options);
    } catch (error) {
        return isoTime;
    }
}

function formatCountdown(isoTime) {
    try {
        const scheduledDate = new Date(isoTime);
        const now = new Date();
        const diffMs = scheduledDate - now;

        if (diffMs <= 0) {
            return 'Starting now';
        }

        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 60) {
            return `in ${diffMins} min${diffMins !== 1 ? 's' : ''}`;
        }

        const diffHours = Math.floor(diffMins / 60);
        const remainingMins = diffMins % 60;

        if (diffHours < 24) {
            return remainingMins > 0
                ? `in ${diffHours}h ${remainingMins}m`
                : `in ${diffHours}h`;
        }

        const diffDays = Math.floor(diffHours / 24);
        const remainingHours = diffHours % 24;

        return remainingHours > 0
            ? `in ${diffDays}d ${remainingHours}h`
            : `in ${diffDays}d`;
    } catch (error) {
        return 'Loading...';
    }
}

function truncateUrl(url, maxLength) {
    try {
        const urlObj = new URL(url);
        const shortened = urlObj.hostname + (urlObj.pathname !== '/' ? urlObj.pathname : '');

        if (shortened.length > maxLength) {
            return shortened.substring(0, maxLength) + '...';
        }
        return shortened;
    } catch {
        if (url.length > maxLength) {
            return url.substring(0, maxLength) + '...';
        }
        return url;
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

async function cancelScheduledMeeting(meetingId) {
    const confirmed = confirm('Are you sure you want to cancel this scheduled meeting?');

    if (!confirmed) {
        return;
    }

    try {
        showToast('Cancelling scheduled meeting...', 'info');

        await apiCall(`/api/scheduled-meetings/${meetingId}`, {
            method: 'DELETE'
        });

        showToast('Scheduled meeting cancelled', 'success');
        loadScheduledMeetings();
    } catch (error) {
        console.error('Cancel error:', error);
        showToast('Failed to cancel: ' + error.message, 'error');
    }
}

// Drag and drop support
document.addEventListener('DOMContentLoaded', function () {
    const uploadZone = document.getElementById('upload-zone');

    if (uploadZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => uploadZone.classList.add('dragover'));
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => uploadZone.classList.remove('dragover'));
        });

        uploadZone.addEventListener('drop', function (e) {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                processSelectedFile(files[0]);
            }
        });

        // Upload zone click to trigger file input
        uploadZone.addEventListener('click', function() {
            document.getElementById('file-input').click();
        });
    }

    // Schedule modal event handlers
    const scheduleModal = document.getElementById('schedule-modal');
    if (scheduleModal) {
        // Close modal when clicking outside
        scheduleModal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeScheduleModal();
            }
        });
    }

    // Close modals with Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const scheduleModal = document.getElementById('schedule-modal');
            if (scheduleModal && scheduleModal.classList.contains('show')) {
                closeScheduleModal();
            }
        }
    });

    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // Dashboard buttons
    const newMeetingBtn = document.getElementById('new-meeting-bot-btn');
    if (newMeetingBtn) {
        newMeetingBtn.addEventListener('click', openNewMeetingModal);
    }

    const scheduleBotBtn = document.getElementById('schedule-bot-btn');
    if (scheduleBotBtn) {
        scheduleBotBtn.addEventListener('click', openScheduleModal);
    }

    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', showUploadModal);
    }

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadMeetings);
    }

    const settingsBtn = document.getElementById('settings-btn');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', openSettingsModal);
    }

    const signoutBtn = document.getElementById('signout-btn');
    if (signoutBtn) {
        signoutBtn.addEventListener('click', signOut);
    }

    // Upload modal
    const closeUploadModal = document.getElementById('close-upload-modal');
    if (closeUploadModal) {
        closeUploadModal.addEventListener('click', hideUploadModal);
    }

    const cancelUploadBtn = document.getElementById('cancel-upload-btn');
    if (cancelUploadBtn) {
        cancelUploadBtn.addEventListener('click', hideUploadModal);
    }

    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }

    const fileRemoveBtn = document.getElementById('file-remove-btn');
    if (fileRemoveBtn) {
        fileRemoveBtn.addEventListener('click', clearFile);
    }

    const uploadPluginSelect = document.getElementById('upload-plugin');
    if (uploadPluginSelect) {
        uploadPluginSelect.addEventListener('change', updateUploadMetadataFields);
    }

    const processBtn = document.getElementById('process-btn');
    if (processBtn) {
        processBtn.addEventListener('click', processUpload);
    }

    // Schedule modal
    const closeScheduleModalBtn = document.getElementById('close-schedule-modal');
    if (closeScheduleModalBtn) {
        closeScheduleModalBtn.addEventListener('click', closeScheduleModal);
    }

    const cancelScheduleBtn = document.getElementById('cancel-schedule-btn');
    if (cancelScheduleBtn) {
        cancelScheduleBtn.addEventListener('click', closeScheduleModal);
    }

    const schedulePluginSelect = document.getElementById('schedule-plugin');
    if (schedulePluginSelect) {
        schedulePluginSelect.addEventListener('change', updateScheduleMetadataFields);
    }

    const scheduleSubmitBtn = document.getElementById('schedule-submit-btn');
    if (scheduleSubmitBtn) {
        scheduleSubmitBtn.addEventListener('click', submitScheduledMeeting);
    }

    // Settings modal
    const closeSettingsModalBtn = document.getElementById('close-settings-modal');
    if (closeSettingsModalBtn) {
        closeSettingsModalBtn.addEventListener('click', closeSettingsModal);
    }

    const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
    if (cancelSettingsBtn) {
        cancelSettingsBtn.addEventListener('click', closeSettingsModal);
    }

    const settingsSaveBtn = document.getElementById('settings-save-btn');
    if (settingsSaveBtn) {
        settingsSaveBtn.addEventListener('click', saveSettings);
    }

    // New meeting modal
    const closeNewMeetingModalBtn = document.getElementById('close-new-meeting-modal');
    if (closeNewMeetingModalBtn) {
        closeNewMeetingModalBtn.addEventListener('click', closeNewMeetingModal);
    }

    const cancelNewMeetingBtn = document.getElementById('cancel-new-meeting-btn');
    if (cancelNewMeetingBtn) {
        cancelNewMeetingBtn.addEventListener('click', closeNewMeetingModal);
    }

    const newMeetingPluginSelect = document.getElementById('new-meeting-plugin');
    if (newMeetingPluginSelect) {
        newMeetingPluginSelect.addEventListener('change', updateNewMeetingMetadataFields);
    }

    const newMeetingSubmitBtn = document.getElementById('new-meeting-submit-btn');
    if (newMeetingSubmitBtn) {
        newMeetingSubmitBtn.addEventListener('click', submitNewMeeting);
    }

    // Event delegation for dynamically created meeting items
    document.addEventListener('click', function(event) {
        // Handle meeting item clicks (uploads and bot meetings)
        const meetingItem = event.target.closest('.meeting-item');
        if (meetingItem && meetingItem.dataset.meetingId) {
            viewMeeting(meetingItem.dataset.meetingId);
            return;
        }

        // Handle cancel scheduled meeting button clicks
        const cancelBtn = event.target.closest('.cancel-scheduled-meeting-btn');
        if (cancelBtn && cancelBtn.dataset.meetingId) {
            cancelScheduledMeeting(cancelBtn.dataset.meetingId);
            return;
        }
    });
});

// Initialize
document.addEventListener('DOMContentLoaded', initApp);
