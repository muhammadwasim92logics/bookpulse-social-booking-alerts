/**
 * Renowned Homes — Public Consultation Booking & Verification Flow
 */

document.addEventListener('DOMContentLoaded', function () {
  const bookingForm = document.getElementById('consultationBookingForm');
  const dateInput = document.getElementById('appointmentDate');
  const timeInput = document.getElementById('appointmentTime');
  const slotsContainer = document.getElementById('slotsContainer');
  const slotsLoading = document.getElementById('slotsLoading');
  const slotsEmpty = document.getElementById('slotsEmpty');
  const submitBtn = document.getElementById('btnSubmitBooking');

  // Verification modal elements
  const verificationModal = document.getElementById('verificationModal');
  const modalMaskedEmail = document.getElementById('modalMaskedEmail');
  const btnVerifyCode = document.getElementById('btnVerifyCode');
  const btnResendCode = document.getElementById('btnResendCode');
  const resendTimerText = document.getElementById('resendTimerText');
  const demoHelperBox = document.getElementById('demoHelperBox');
  const demoCodeValue = document.getElementById('demoCodeValue');
  const btnQuickFillDemo = document.getElementById('btnQuickFillDemo');
  const verificationError = document.getElementById('verificationError');

  // Confirmation modal elements
  const confirmationModal = document.getElementById('confirmationSuccessModal');
  const confRef = document.getElementById('confBookingRef');
  const confName = document.getElementById('confClientName');
  const confDate = document.getElementById('confDate');
  const confTime = document.getElementById('confTime');
  const confService = document.getElementById('confService');
  const btnDownloadIcs = document.getElementById('btnDownloadIcs');
  const btnCopyRef = document.getElementById('btnCopyRef');

  let activeBookingRef = null;
  let resendCountdown = 30;
  let resendInterval = null;

  // Initialize PIN input handler
  const pinHandler = window.initPinInputs('#pinGrid', function (fullCode) {
    // When all 6 digits entered, auto-verify!
    submitVerification(fullCode);
  });

  // CSRF token retrieval helper
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

  // Fetch slots whenever the user selects a new date
  if (dateInput) {
    dateInput.addEventListener('change', function () {
      loadSlots(this.value);
    });
  }

  function loadSlots(dateStr) {
    if (!dateStr) return;
    if (slotsLoading) slotsLoading.style.display = 'block';
    if (slotsContainer) slotsContainer.innerHTML = '';
    if (slotsEmpty) slotsEmpty.style.display = 'none';
    if (timeInput) timeInput.value = '';

    fetch(`/api/availability/?date=${encodeURIComponent(dateStr)}`)
      .then((r) => r.json())
      .then((data) => {
        if (slotsLoading) slotsLoading.style.display = 'none';

        if (!data.slots || data.slots.length === 0) {
          if (slotsEmpty) {
            slotsEmpty.textContent = data.message || 'No available slots for this date.';
            slotsEmpty.style.display = 'block';
          }
          return;
        }

        data.slots.forEach((slot) => {
          const pill = document.createElement('div');
          pill.className = `slot-pill ${slot.is_available ? '' : 'disabled'}`;
          pill.dataset.time = slot.time;
          pill.textContent = slot.display;
          pill.title = slot.reason;

          if (slot.is_available) {
            pill.addEventListener('click', function () {
              document.querySelectorAll('.slot-pill').forEach((p) => p.classList.remove('active'));
              this.classList.add('active');
              if (timeInput) timeInput.value = this.dataset.time;
              window.showToast('Time Selected', `Appointment set for ${slot.display}`, 'info', 2000);
            });
          }

          slotsContainer.appendChild(pill);
        });
      })
      .catch((err) => {
        if (slotsLoading) slotsLoading.style.display = 'none';
        if (slotsEmpty) {
          slotsEmpty.textContent = 'Error loading slots. Please try again.';
          slotsEmpty.style.display = 'block';
        }
      });
  }

  // Handle Booking Form Submission
  if (bookingForm) {
    bookingForm.addEventListener('submit', function (e) {
      e.preventDefault();

      const fullName = document.getElementById('fullName').value.trim();
      const email = document.getElementById('email').value.trim();
      const phone = document.getElementById('phone').value.trim();
      const apptDate = dateInput.value.trim();
      const apptTime = timeInput ? timeInput.value.trim() : '';
      const enquiryType = document.getElementById('enquiryType').value;
      const socialUsername = document.getElementById('socialUsername') ? document.getElementById('socialUsername').value.trim() : '';
      const message = document.getElementById('additionalNotes') ? document.getElementById('additionalNotes').value.trim() : '';
      const consent = document.getElementById('consentContact') ? document.getElementById('consentContact').checked : true;
      const marketingConsent = document.getElementById('consentMarketing') ? document.getElementById('consentMarketing').checked : false;

      // Basic client-side validation
      if (!fullName) {
        window.showToast('Missing Field', 'Please enter your full name.', 'warning');
        return;
      }
      if (!email || !email.includes('@')) {
        window.showToast('Invalid Email', 'Please enter a valid email address.', 'warning');
        return;
      }
      if (!phone) {
        window.showToast('Missing Field', 'Please enter your contact phone number.', 'warning');
        return;
      }
      if (!apptDate) {
        window.showToast('Select Date', 'Please choose an appointment date.', 'warning');
        return;
      }
      if (!apptTime) {
        window.showToast('Select Time Slot', 'Please click an available time slot.', 'warning');
        return;
      }
      if (!consent) {
        window.showToast('Consent Required', 'Please accept the consultation contact consent.', 'warning');
        return;
      }

      // Show submitting state
      submitBtn.disabled = true;
      const originalBtnText = submitBtn.innerHTML;
      submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Reserving Slot...`;

      const payload = {
        full_name: fullName,
        email: email,
        phone: phone,
        appointment_date: apptDate,
        appointment_time: apptTime,
        enquiry_type: enquiryType,
        social_username: socialUsername,
        message: message,
        consent_to_contact: consent,
        marketing_consent: marketingConsent,
      };

      fetch('/api/bookings/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(payload),
      })
        .then((r) => r.json())
        .then((res) => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;

          if (!res.success) {
            window.showToast('Booking Error', res.error || 'Failed to submit booking.', 'error');
            return;
          }

          // Booking slot successfully reserved!
          activeBookingRef = res.booking_reference;

          // Update verification pop-up modal
          if (modalMaskedEmail) modalMaskedEmail.textContent = res.email_masked;
          if (demoHelperBox && res.demo_code) {
            demoCodeValue.textContent = res.demo_code;
            demoHelperBox.style.display = 'flex';
          }
          if (verificationError) verificationError.style.display = 'none';

          if (pinHandler) pinHandler.clear();

          // Tasteful notification
          window.showToast('Verification Code Dispatched', res.message, 'info', 4500);

          // Open verification pop-up modal
          window.openModal('verificationModal');
          startResendTimer();
        })
        .catch((err) => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
          window.showToast('Network Error', 'Could not connect to server. Please try again.', 'error');
        });
    });
  }

  // Quick-fill demo button
  if (btnQuickFillDemo) {
    btnQuickFillDemo.addEventListener('click', function () {
      const code = demoCodeValue.textContent.trim();
      if (code && pinHandler) {
        pinHandler.setCode(code);
        window.showToast('Code Filled', 'Demo code automatically inserted.', 'info', 1800);
      }
    });
  }

  // Manual Verify Button click
  if (btnVerifyCode) {
    btnVerifyCode.addEventListener('click', function () {
      const code = pinHandler ? pinHandler.getCode() : '';
      submitVerification(code);
    });
  }

  // Verification request
  function submitVerification(code) {
    if (!activeBookingRef) {
      window.showToast('Error', 'No active booking session found.', 'error');
      return;
    }
    if (!code || code.length !== 6) {
      if (verificationError) {
        verificationError.textContent = 'Please enter the complete 6-digit confirmation code.';
        verificationError.style.display = 'block';
      }
      return;
    }

    if (btnVerifyCode) {
      btnVerifyCode.disabled = true;
      btnVerifyCode.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Verifying...`;
    }

    fetch('/api/bookings/verify/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
      },
      body: JSON.stringify({
        booking_reference: activeBookingRef,
        verification_code: code,
      }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (btnVerifyCode) {
          btnVerifyCode.disabled = false;
          btnVerifyCode.innerHTML = `Confirm Appointment`;
        }

        if (!res.success) {
          if (verificationError) {
            verificationError.textContent = res.error || 'Invalid code.';
            verificationError.style.display = 'block';
          }
          window.showToast('Verification Failed', res.error || 'Incorrect code.', 'error');
          return;
        }

        // Success!
        window.closeModal('verificationModal');

        // Tasteful notification!
        window.showToast('Appointment Confirmed!', 'A confirmation has been saved and our team notified.', 'success', 5000);

        // Populate Confirmation Modal
        const b = res.booking;
        if (confRef) confRef.textContent = b.booking_reference;
        if (confName) confName.textContent = b.full_name;
        if (confDate) confDate.textContent = b.date_formatted;
        if (confTime) confTime.textContent = b.time_formatted;
        if (confService) confService.textContent = b.enquiry_type;

        if (btnDownloadIcs) {
          btnDownloadIcs.href = `/api/bookings/${encodeURIComponent(b.booking_reference)}/calendar.ics`;
        }

        // Open Confirmation Pop-up Modal
        window.openModal('confirmationSuccessModal');

        // Reset form
        if (bookingForm) bookingForm.reset();
        if (dateInput) loadSlots(dateInput.value);
      })
      .catch((err) => {
        if (btnVerifyCode) {
          btnVerifyCode.disabled = false;
          btnVerifyCode.innerHTML = `Confirm Appointment`;
        }
        window.showToast('Network Error', 'Verification service unavailable.', 'error');
      });
  }

  // Resend code timer
  function startResendTimer() {
    resendCountdown = 30;
    if (btnResendCode) btnResendCode.disabled = true;
    if (resendInterval) clearInterval(resendInterval);

    resendInterval = setInterval(() => {
      resendCountdown--;
      if (resendTimerText) {
        resendTimerText.textContent = `(${resendCountdown}s)`;
      }
      if (resendCountdown <= 0) {
        clearInterval(resendInterval);
        if (btnResendCode) btnResendCode.disabled = false;
        if (resendTimerText) resendTimerText.textContent = '';
      }
    }, 1000);
  }

  // Resend button click
  if (btnResendCode) {
    btnResendCode.addEventListener('click', function () {
      if (!activeBookingRef) return;
      btnResendCode.disabled = true;

      fetch('/api/bookings/resend-code/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify({ booking_reference: activeBookingRef }),
      })
        .then((r) => r.json())
        .then((res) => {
          if (res.success) {
            window.showToast('Code Resent', res.message, 'info');
            if (demoCodeValue && res.demo_code) {
              demoCodeValue.textContent = res.demo_code;
            }
            if (pinHandler) pinHandler.clear();
            startResendTimer();
          } else {
            window.showToast('Error', res.error || 'Could not resend code.', 'error');
            btnResendCode.disabled = false;
          }
        })
        .catch(() => {
          btnResendCode.disabled = false;
          window.showToast('Network Error', 'Failed to resend code.', 'error');
        });
    });
  }

  // Copy reference button inside confirmed modal
  if (btnCopyRef) {
    btnCopyRef.addEventListener('click', function () {
      if (confRef && confRef.textContent) {
        window.copyToClipboard(confRef.textContent.trim(), 'Booking reference copied to clipboard!');
      }
    });
  }
});

