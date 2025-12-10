# UI Changes for Scheduled Meetings & Timezone Support

This document outlines the frontend changes needed to support scheduled meeting joins and timezone preferences.

## Overview

The backend now supports:
- User timezone preferences (default: America/New_York)
- Scheduling bot joins for specific times
- Background scheduler that joins meetings automatically
- All times stored in UTC, displayed in user's timezone

## Required UI Changes

### 1. User Profile / Settings Section

Add a timezone selector to allow users to change their timezone preference.

#### Location
Add to the dashboard view, either:
- In the user info card (near user avatar/email)
- As a settings/preferences modal

#### Components
```html
<div class="timezone-selector">
    <label for="user-timezone">Timezone</label>
    <select id="user-timezone" onchange="updateTimezone()">
        <option value="America/New_York">Eastern (EST/EDT)</option>
        <option value="America/Chicago">Central (CST/CDT)</option>
        <option value="America/Denver">Mountain (MST/MDT)</option>
        <option value="America/Phoenix">Arizona (no DST)</option>
        <option value="America/Los_Angeles">Pacific (PST/PDT)</option>
        <option value="America/Anchorage">Alaska (AKST/AKDT)</option>
        <option value="Pacific/Honolulu">Hawaii (HST)</option>
        <option value="UTC">UTC</option>
    </select>
</div>
```

#### JavaScript
```javascript
async function loadUserProfile() {
    const response = await fetch('/api/users/me', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });
    const user = await response.json();

    // Set timezone dropdown
    document.getElementById('user-timezone').value = user.timezone;
}

async function updateTimezone() {
    const timezone = document.getElementById('user-timezone').value;

    const response = await fetch('/api/users/me', {
        method: 'PATCH',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ timezone })
    });

    if (response.ok) {
        showToast('Timezone updated successfully');
        // Reload scheduled meetings to show new times
        loadScheduledMeetings();
    } else {
        showToast('Failed to update timezone', 'error');
    }
}
```

### 2. Schedule Meeting Button & Modal

Add ability to schedule a bot join for a future time.

#### Button Location
Add next to "New Meeting Bot" button in the actions section:

```html
<button class="btn btn-primary" onclick="showScheduleModal()">
    📅 Schedule Meeting
</button>
```

#### Modal HTML
```html
<div class="modal-overlay" id="schedule-modal">
    <div class="modal">
        <div class="modal-header">
            <h2>Schedule Meeting Bot</h2>
            <button class="modal-close" onclick="hideScheduleModal()">&times;</button>
        </div>
        <div class="modal-body">
            <p class="modal-description">
                Schedule a bot to join a meeting at a specific time.
                Times are shown in your timezone: <strong id="user-tz-display">America/New_York</strong>
            </p>

            <div class="form-group">
                <label for="schedule-meeting-url">Meeting URL *</label>
                <input type="text" id="schedule-meeting-url"
                       placeholder="https://zoom.us/j/123456789" required>
            </div>

            <div class="form-group">
                <label for="schedule-date">Date *</label>
                <input type="date" id="schedule-date" required>
            </div>

            <div class="form-group">
                <label for="schedule-time">Time *</label>
                <input type="time" id="schedule-time" required>
            </div>

            <div class="form-group">
                <label for="schedule-bot-name">Bot Name (optional)</label>
                <input type="text" id="schedule-bot-name"
                       placeholder="Meeting Assistant">
            </div>

            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="hideScheduleModal()">
                    Cancel
                </button>
                <button class="btn btn-primary" onclick="scheduleNewMeeting()">
                    Schedule Bot
                </button>
            </div>
        </div>
    </div>
</div>
```

#### JavaScript
```javascript
function showScheduleModal() {
    // Set minimum date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('schedule-date').min = today;
    document.getElementById('schedule-date').value = today;

    // Set current time + 1 hour as default
    const now = new Date();
    now.setHours(now.getHours() + 1);
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    document.getElementById('schedule-time').value = `${hours}:${minutes}`;

    // Show user's timezone
    const userTimezone = document.getElementById('user-timezone').value;
    document.getElementById('user-tz-display').textContent = userTimezone;

    document.getElementById('schedule-modal').classList.add('active');
}

function hideScheduleModal() {
    document.getElementById('schedule-modal').classList.remove('active');
    // Clear form
    document.getElementById('schedule-meeting-url').value = '';
    document.getElementById('schedule-bot-name').value = '';
}

async function scheduleNewMeeting() {
    const meetingUrl = document.getElementById('schedule-meeting-url').value.trim();
    const date = document.getElementById('schedule-date').value;
    const time = document.getElementById('schedule-time').value;
    const botName = document.getElementById('schedule-bot-name').value.trim();

    if (!meetingUrl || !date || !time) {
        showToast('Please fill in all required fields', 'error');
        return;
    }

    // Combine date and time into ISO format
    // The backend will interpret this in the user's timezone
    const scheduledTime = `${date}T${time}:00`;

    const payload = {
        meeting_url: meetingUrl,
        scheduled_time: scheduledTime
    };

    if (botName) {
        payload.bot_name = botName;
    }

    try {
        const response = await fetch('/api/scheduled-meetings', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showToast('Meeting scheduled successfully');
            hideScheduleModal();
            loadScheduledMeetings();
        } else {
            const error = await response.json();
            showToast(error.error || 'Failed to schedule meeting', 'error');
        }
    } catch (err) {
        console.error('Error scheduling meeting:', err);
        showToast('Network error', 'error');
    }
}
```

### 3. Scheduled Meetings List

Add a new section to display upcoming and past scheduled meetings.

#### HTML
Add after the "Bot Meetings" section:

```html
<div class="meetings-section" style="margin-top: 1rem; padding-top: 1rem;">
    <div class="section-title">📅 Scheduled Meetings</div>
    <div id="scheduled-meetings-list">
        <div class="empty-state">
            <div class="empty-state-icon">📅</div>
            <p>No scheduled meetings</p>
        </div>
    </div>
</div>
```

#### JavaScript
```javascript
async function loadScheduledMeetings() {
    const response = await fetch('/api/scheduled-meetings', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });

    if (!response.ok) {
        console.error('Failed to load scheduled meetings');
        return;
    }

    const meetings = await response.json();
    const listElement = document.getElementById('scheduled-meetings-list');

    if (meetings.length === 0) {
        listElement.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <p>No scheduled meetings</p>
            </div>
        `;
        return;
    }

    // Group by status
    const scheduled = meetings.filter(m => m.status === 'scheduled');
    const completed = meetings.filter(m => m.status === 'completed');
    const failed = meetings.filter(m => m.status === 'failed');
    const cancelled = meetings.filter(m => m.status === 'cancelled');

    let html = '';

    // Upcoming meetings
    if (scheduled.length > 0) {
        html += '<div class="scheduled-group"><h4>Upcoming</h4>';
        scheduled.forEach(meeting => {
            html += renderScheduledMeeting(meeting);
        });
        html += '</div>';
    }

    // Completed/Failed/Cancelled
    const past = [...completed, ...failed, ...cancelled];
    if (past.length > 0) {
        html += '<div class="scheduled-group"><h4>Past</h4>';
        past.forEach(meeting => {
            html += renderScheduledMeeting(meeting);
        });
        html += '</div>';
    }

    listElement.innerHTML = html;
}

function renderScheduledMeeting(meeting) {
    const scheduledDate = new Date(meeting.scheduled_time);
    const formattedDate = scheduledDate.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });

    const statusClass = meeting.status === 'scheduled' ? 'status-scheduled' :
                       meeting.status === 'completed' ? 'status-completed' :
                       meeting.status === 'failed' ? 'status-failed' : 'status-cancelled';

    const statusEmoji = meeting.status === 'scheduled' ? '⏰' :
                       meeting.status === 'completed' ? '✅' :
                       meeting.status === 'failed' ? '❌' : '🚫';

    return `
        <div class="meeting-card scheduled-meeting-card">
            <div class="meeting-header">
                <div class="meeting-info">
                    <div class="meeting-name">${meeting.bot_name}</div>
                    <div class="meeting-time">${formattedDate}</div>
                </div>
                <div class="meeting-status ${statusClass}">
                    ${statusEmoji} ${meeting.status}
                </div>
            </div>
            <div class="meeting-url">${meeting.meeting_url}</div>
            ${meeting.status === 'scheduled' ? `
                <div class="meeting-actions">
                    <button class="btn btn-sm btn-danger" onclick="cancelScheduledMeeting('${meeting.id}')">
                        Cancel
                    </button>
                </div>
            ` : ''}
            ${meeting.actual_meeting_id ? `
                <div class="meeting-link">
                    <a href="#" onclick="viewMeeting('${meeting.actual_meeting_id}'); return false;">
                        View Meeting Results
                    </a>
                </div>
            ` : ''}
            ${meeting.error ? `
                <div class="meeting-error">Error: ${meeting.error}</div>
            ` : ''}
        </div>
    `;
}

async function cancelScheduledMeeting(meetingId) {
    if (!confirm('Are you sure you want to cancel this scheduled meeting?')) {
        return;
    }

    const response = await fetch(`/api/scheduled-meetings/${meetingId}`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });

    if (response.ok) {
        showToast('Scheduled meeting cancelled');
        loadScheduledMeetings();
    } else {
        showToast('Failed to cancel scheduled meeting', 'error');
    }
}
```

### 4. Additional CSS Styles

Add these styles to support the new components:

```css
/* Timezone selector */
.timezone-selector {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
}

.timezone-selector label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.timezone-selector select {
    width: 100%;
    padding: 0.5rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-primary);
    font-family: inherit;
}

/* Scheduled meetings */
.scheduled-group {
    margin-bottom: 1rem;
}

.scheduled-group h4 {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.scheduled-meeting-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.75rem;
}

.meeting-time {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}

.meeting-url {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 0.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.status-scheduled {
    background: rgba(99, 102, 241, 0.1);
    color: var(--accent);
}

.status-completed {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
}

.status-failed,
.status-cancelled {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
}

.meeting-error {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 4px;
    font-size: 0.75rem;
    color: #ef4444;
}

.meeting-link {
    margin-top: 0.5rem;
    font-size: 0.875rem;
}

.meeting-link a {
    color: var(--accent);
    text-decoration: none;
}

.meeting-link a:hover {
    text-decoration: underline;
}

.btn-sm {
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
}
```

### 5. Integration Steps

1. Add timezone selector to user info section
2. Add "Schedule Meeting" button to actions
3. Create schedule modal HTML
4. Add scheduled meetings section
5. Add CSS styles
6. Update `loadDashboard()` to call `loadUserProfile()` and `loadScheduledMeetings()`
7. Set up periodic refresh of scheduled meetings (optional)

### 6. Testing Checklist

- [ ] User can view and change timezone preference
- [ ] Timezone change persists after page refresh
- [ ] Schedule meeting modal opens and closes
- [ ] Can schedule a meeting with valid URL and time
- [ ] Scheduled meetings appear in the list
- [ ] Times display correctly in user's timezone
- [ ] Can cancel a scheduled meeting
- [ ] Completed scheduled meetings link to actual meeting results
- [ ] Failed scheduled meetings show error message
- [ ] Past meetings are grouped separately from upcoming

### 7. Optional Enhancements

- Auto-refresh scheduled meetings every 30 seconds to show status updates
- Show countdown timer for upcoming scheduled meetings
- Add recurring meeting support
- Show notification when scheduled meeting is about to start
- Add calendar view for scheduled meetings
- Export scheduled meetings to .ics file
