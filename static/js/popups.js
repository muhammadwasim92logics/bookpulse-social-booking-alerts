/**
 * Renowned Homes — Pop-ups & Notification Management System
 */

(function () {
  'use strict';

  // Ensure toast container exists
  function getOrCreateToastContainer() {
    let container = document.getElementById('rhToastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'rhToastContainer';
      document.body.appendChild(container);
    }
    return container;
  }

  /**
   * Dispatches an elegant toast notification to the screen
   * @param {string} title - Heading of the notification
   * @param {string} message - Body text
   * @param {'success'|'info'|'warning'|'error'} type - Style variant
   * @param {number} duration - Auto-dismiss timeout in ms
   */
  window.showToast = function (title, message, type = 'success', duration = 4000) {
    const container = getOrCreateToastContainer();

    const toast = document.createElement('div');
    toast.className = `rh-toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>`;
    } else if (type === 'info') {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    } else if (type === 'warning') {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
    } else {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
    }

    toast.innerHTML = `
      <div class="rh-toast-icon">${iconSvg}</div>
      <div class="rh-toast-body">
        <div class="rh-toast-title">${title}</div>
        <div class="rh-toast-msg">${message}</div>
      </div>
      <button class="rh-toast-close" title="Dismiss" aria-label="Dismiss">&times;</button>
      <div class="rh-toast-progress" style="animation-duration: ${duration}ms;"></div>
    `;

    const closeBtn = toast.querySelector('.rh-toast-close');
    const dismiss = () => {
      toast.classList.add('toast-hiding');
      setTimeout(() => {
        if (toast.parentElement) toast.parentElement.removeChild(toast);
      }, 300);
    };

    closeBtn.addEventListener('click', dismiss);

    const timer = setTimeout(dismiss, duration);

    // Pause dismissal on mouse hover
    toast.addEventListener('mouseenter', () => {
      clearTimeout(timer);
      const prog = toast.querySelector('.rh-toast-progress');
      if (prog) prog.style.animationPlayState = 'paused';
    });

    container.appendChild(toast);
  };

  /**
   * Modal management
   */
  window.openModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Auto-focus first input if exists
    const firstInput = modal.querySelector('input:not([type="hidden"]), select, textarea');
    if (firstInput) {
      setTimeout(() => firstInput.focus(), 100);
    }
  };

  window.closeModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.remove('active');
    document.body.style.overflow = '';
  };

  /**
   * Global modal close handlers (backdrop click and ESC key)
   */
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('rh-modal-overlay')) {
      e.target.classList.remove('active');
      document.body.style.overflow = '';
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const activeModals = document.querySelectorAll('.rh-modal-overlay.active');
      activeModals.forEach((m) => {
        m.classList.remove('active');
      });
      document.body.style.overflow = '';
    }
  });

  /**
   * Clipboard helper
   */
  window.copyToClipboard = function (text, successMsg = 'Copied to clipboard!') {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        window.showToast('Copied', successMsg, 'success', 2800);
      }).catch(() => fallbackCopy(text, successMsg));
    } else {
      fallbackCopy(text, successMsg);
    }
  };

  function fallbackCopy(text, successMsg) {
    const tempInput = document.createElement('input');
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    try {
      document.execCommand('copy');
      window.showToast('Copied', successMsg, 'success', 2800);
    } catch (err) {
      window.showToast('Notice', 'Please copy manually: ' + text, 'info', 4000);
    }
    document.body.removeChild(tempInput);
  }

  /**
   * Helper for multi-digit PIN input auto-advance and paste handling
   */
  window.initPinInputs = function (gridSelector, onCompleteCallback) {
    const grid = document.querySelector(gridSelector);
    if (!grid) return;
    const inputs = Array.from(grid.querySelectorAll('input.pin-digit'));

    inputs.forEach((input, index) => {
      // Input event: move to next
      input.addEventListener('input', function (e) {
        const val = this.value;
        if (val.length >= 1) {
          this.value = val.slice(-1); // Only keep single digit
          if (index < inputs.length - 1) {
            inputs[index + 1].focus();
            inputs[index + 1].select();
          }
        }
        checkFullCode();
      });

      // Keydown event: backspace move to previous
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' && !this.value && index > 0) {
          inputs[index - 1].focus();
          inputs[index - 1].select();
        }
      });

      // Paste event: distribute full code
      input.addEventListener('paste', function (e) {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData).getData('text').trim();
        if (/^\d+$/.test(pasted)) {
          const chars = pasted.slice(0, inputs.length).split('');
          chars.forEach((char, i) => {
            if (inputs[i]) inputs[i].value = char;
          });
          const focusIndex = Math.min(chars.length, inputs.length - 1);
          inputs[focusIndex].focus();
          checkFullCode();
        }
      });
    });

    function checkFullCode() {
      const full = inputs.map((i) => i.value).join('');
      if (full.length === inputs.length && onCompleteCallback) {
        onCompleteCallback(full);
      }
    }

    return {
      getCode: () => inputs.map((i) => i.value).join(''),
      setCode: (code) => {
        const chars = String(code).slice(0, inputs.length).split('');
        inputs.forEach((inp, idx) => {
          inp.value = chars[idx] || '';
        });
        checkFullCode();
      },
      clear: () => {
        inputs.forEach((i) => (i.value = ''));
        if (inputs[0]) inputs[0].focus();
      },
    };
  };
})();

