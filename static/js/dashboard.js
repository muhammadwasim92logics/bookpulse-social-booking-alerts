/**
 * Renowned Homes — Admin Dashboard Operations & Pop-ups
 */

document.addEventListener('DOMContentLoaded', function () {
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  const csrftoken = getCookie('csrftoken');

  // Test Slack Webhook Trigger
  const btnTestSlack = document.getElementById('btnTestSlack');
  if (btnTestSlack) {
    btnTestSlack.addEventListener('click', function () {
      btnTestSlack.disabled = true;
      const originalHtml = btnTestSlack.innerHTML;
      btnTestSlack.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Dispatching to Slack...`;

      fetch('/dashboard/settings/test-slack/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
        },
      })
        .then((r) => r.json())
        .then((res) => {
          btnTestSlack.disabled = false;
          btnTestSlack.innerHTML = originalHtml;

          if (res.success) {
            window.showToast('Slack Test Delivered', res.message, 'success', 5000);
          } else {
            window.showToast('Slack Error', res.message, 'error', 6000);
          }
        })
        .catch((err) => {
          btnTestSlack.disabled = false;
          btnTestSlack.innerHTML = originalHtml;
          window.showToast('Connection Error', 'Failed to reach Slack test endpoint.', 'error');
        });
    });
  }

  // Test Email SMTP Trigger
  const btnTestEmail = document.getElementById('btnTestEmail');
  if (btnTestEmail) {
    btnTestEmail.addEventListener('click', function () {
      btnTestEmail.disabled = true;
      const originalHtml = btnTestEmail.innerHTML;
      btnTestEmail.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Connecting to Gmail SMTP...`;

      fetch('/dashboard/settings/test-email/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
        },
      })
        .then((r) => r.json())
        .then((res) => {
          btnTestEmail.disabled = false;
          btnTestEmail.innerHTML = originalHtml;

          if (res.success) {
            window.showToast('Email Delivered', res.message, 'success', 5000);
          } else {
            window.showToast('SMTP Error', res.message, 'error', 6000);
          }
        })
        .catch((err) => {
          btnTestEmail.disabled = false;
          btnTestEmail.innerHTML = originalHtml;
          window.showToast('Connection Error', 'Failed to reach email test endpoint.', 'error');
        });
    });
  }

  // Social Analytics "Sync Now" Button
  const btnSyncSocial = document.getElementById('btnSyncSocial');
  if (btnSyncSocial) {
    btnSyncSocial.addEventListener('click', function () {
      btnSyncSocial.disabled = true;
      const orig = btnSyncSocial.innerHTML;
      btnSyncSocial.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Syncing Social APIs...`;

      fetch('/dashboard/analytics/sync/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
        },
      })
        .then((r) => r.json())
        .then((res) => {
          btnSyncSocial.disabled = false;
          btnSyncSocial.innerHTML = orig;
          window.showToast('Sync Completed', res.message, 'success', 3500);
          setTimeout(() => location.reload(), 1200);
        })
        .catch(() => {
          btnSyncSocial.disabled = false;
          btnSyncSocial.innerHTML = orig;
          window.showToast('Sync Failed', 'Could not refresh platform metrics.', 'error');
        });
    });
  }

  // Booking Detail Modal View
  window.viewBookingDetails = function (bookingId) {
    fetch(`/dashboard/bookings/${bookingId}/detail/`)
      .then((r) => r.json())
      .then((res) => {
        if (!res.success) {
          window.showToast('Error', 'Could not load booking details.', 'error');
          return;
        }

        const b = res.booking;
        document.getElementById('modalDetailRef').textContent = b.reference;
        document.getElementById('modalDetailName').textContent = b.full_name;
        document.getElementById('modalDetailEmail').textContent = b.email;
        document.getElementById('modalDetailPhone').textContent = b.phone;
        document.getElementById('modalDetailSocial').textContent = b.social_username;
        document.getElementById('modalDetailService').textContent = b.enquiry_type;
        document.getElementById('modalDetailDateTime').textContent = `${b.appointment_date_formatted} at ${b.appointment_time} (${b.timezone})`;
        document.getElementById('modalDetailMessage').textContent = b.message;
        document.getElementById('modalDetailVerified').innerHTML = b.is_email_verified
          ? `<span class="badge-confirmed">Verified (${b.verified_at || 'Yes'})</span>`
          : `<span class="badge-pending">Unverified</span>`;

        // Attribution
        const attrDiv = document.getElementById('modalDetailAttribution');
        if (b.attribution) {
          attrDiv.innerHTML = `
            <div><strong>Platform:</strong> ${b.attribution.platform}</div>
            <div><strong>Campaign:</strong> ${b.attribution.campaign}</div>
            <div><strong>Video ID / Content:</strong> <code>${b.attribution.video_id}</code></div>
          `;
        } else {
          attrDiv.innerHTML = `<span class="text-muted">Direct / Organic visit</span>`;
        }

        // Slack Status
        const slackDiv = document.getElementById('modalDetailSlack');
        if (slackDiv) {
          slackDiv.innerHTML = `Slack Webhook: <strong>${b.notifications.slack_status}</strong> ${b.notifications.slack_sent_at ? `(${b.notifications.slack_sent_at})` : ''}`;
        }

        // Resend to Slack button binding
        const btnResendSlack = document.getElementById('btnResendSlackNotification');
        if (btnResendSlack) {
          btnResendSlack.onclick = function () {
            btnResendSlack.disabled = true;
            const originalHtml = btnResendSlack.innerHTML;
            btnResendSlack.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Sending...`;

            fetch(`/dashboard/bookings/${bookingId}/resend-slack/`, {
              method: 'POST',
              headers: {
                'X-CSRFToken': csrftoken,
              },
            })
              .then((r) => r.json())
              .then((res) => {
                btnResendSlack.disabled = false;
                btnResendSlack.innerHTML = originalHtml;
                if (res.success) {
                  window.showToast('Slack Dispatched', `Notification for ${res.reference} sent to Slack!`, 'success', 4500);
                  if (slackDiv) {
                    slackDiv.innerHTML = `Slack Webhook: <strong class="text-success">Sent (Just now)</strong>`;
                  }
                } else {
                  window.showToast('Slack Delivery Warning', res.message || 'Failed to dispatch Slack notification.', 'error', 6000);
                }
              })
              .catch(() => {
                btnResendSlack.disabled = false;
                btnResendSlack.innerHTML = originalHtml;
                window.showToast('Network Error', 'Could not reach server endpoint.', 'error');
              });
          };
        }

        // Form controls
        const statusSelect = document.getElementById('modalDetailStatusSelect');
        if (statusSelect) statusSelect.value = b.status;

        const notesArea = document.getElementById('modalDetailNotes');
        if (notesArea) notesArea.value = b.internal_notes || '';

        // Save button binding
        const btnSave = document.getElementById('btnSaveBookingModal');
        btnSave.onclick = function () {
          saveBookingUpdates(bookingId);
        };

        // Open Modal
        window.openModal('bookingDetailModal');
      })
      .catch((err) => {
        window.showToast('Error', 'Failed to retrieve booking information.', 'error');
      });
  };

  function saveBookingUpdates(bookingId) {
    const status = document.getElementById('modalDetailStatusSelect').value;
    const notes = document.getElementById('modalDetailNotes').value;
    const btnSave = document.getElementById('btnSaveBookingModal');

    btnSave.disabled = true;
    btnSave.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Saving...`;

    fetch(`/dashboard/bookings/${bookingId}/update/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
      },
      body: JSON.stringify({
        status: status,
        internal_notes: notes,
      }),
    })
      .then((r) => r.json())
      .then((res) => {
        btnSave.disabled = false;
        btnSave.innerHTML = `Save Changes`;

        if (res.success) {
          window.closeModal('bookingDetailModal');
          window.showToast('Changes Saved', res.message, 'success', 3500);
          setTimeout(() => location.reload(), 900);
        } else {
          window.showToast('Error', res.error || 'Failed to update booking.', 'error');
        }
      })
      .catch(() => {
        btnSave.disabled = false;
        btnSave.innerHTML = `Save Changes`;
        window.showToast('Network Error', 'Could not save updates.', 'error');
      });
  }

  // Reschedule Modal
  window.openRescheduleModal = function (bookingId, currentRef, currentDate, currentTime) {
    document.getElementById('rescheduleBookingRef').textContent = currentRef;
    document.getElementById('rescheduleDate').value = currentDate;
    document.getElementById('rescheduleTime').value = currentTime;

    const btnSubmit = document.getElementById('btnSubmitReschedule');
    btnSubmit.onclick = function () {
      const d = document.getElementById('rescheduleDate').value;
      const t = document.getElementById('rescheduleTime').value;

      if (!d || !t) {
        window.showToast('Missing Date/Time', 'Please select both date and time.', 'warning');
        return;
      }

      btnSubmit.disabled = true;
      btnSubmit.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Rescheduling...`;

      fetch(`/dashboard/bookings/${bookingId}/reschedule/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify({ date: d, time: t }),
      })
        .then((r) => r.json())
        .then((res) => {
          btnSubmit.disabled = false;
          btnSubmit.innerHTML = `Reschedule Appointment`;

          if (res.success) {
            window.closeModal('rescheduleModal');
            window.showToast('Rescheduled', res.message, 'success', 4000);
            setTimeout(() => location.reload(), 900);
          } else {
            window.showToast('Conflict', res.error, 'error', 4500);
          }
        })
        .catch(() => {
          btnSubmit.disabled = false;
          btnSubmit.innerHTML = `Reschedule Appointment`;
          window.showToast('Network Error', 'Rescheduling failed.', 'error');
        });
    };

    window.openModal('rescheduleModal');
  };
});

