(function () {
  const toggle = document.getElementById('staff-push-enabled');
  const status = document.getElementById('staff-push-status');
  const csrf = document.querySelector('#staff-push-settings input[name=csrfmiddlewaretoken]')?.value;
  if (!toggle || !status || !csrf) return;

  function message(text) { status.textContent = text; }
  function keyBytes(value) {
    const base64 = (value + '='.repeat((4 - value.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
  }
  async function api(path, method, body) {
    const response = await fetch('/api/v1/push/' + path, {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) {
      const error = new Error('Запрос не выполнен.');
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : response.json();
  }

  async function enable() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      throw new Error('Этот браузер не поддерживает push-уведомления.');
    }
    const config = await api('public-key/', 'GET');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Разрешите уведомления в настройках браузера.');
    const registration = await navigator.serviceWorker.register('/admin/push-sw.js', { scope: '/admin/' });
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(config.public_key),
      });
    }
    await api('preferences/', 'PUT', { enabled: true });
    try {
      await api('subscriptions/', 'POST', subscription.toJSON());
    } catch (error) {
      try {
        if (error.status === 409) {
          await subscription.unsubscribe();
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: keyBytes(config.public_key),
          });
          await api('subscriptions/', 'POST', subscription.toJSON());
        } else {
          throw error;
        }
      } catch (retryError) {
        await api('preferences/', 'PUT', { enabled: false });
        throw retryError;
      }
    }
    message('Уведомления включены для этого браузера.');
  }

  async function disable() {
    await api('preferences/', 'PUT', { enabled: false });
    const registration = await navigator.serviceWorker.getRegistration('/admin/');
    const subscription = await registration?.pushManager.getSubscription();
    if (subscription) {
      try { await subscription.unsubscribe(); } catch (_) { /* Server preference is already disabled. */ }
    }
    message('Уведомления отключены.');
  }

  toggle.addEventListener('change', async () => {
    toggle.disabled = true;
    const wanted = toggle.checked;
    try {
      if (wanted) await enable(); else await disable();
    } catch (error) {
      toggle.checked = !wanted;
      message(error.message || 'Не удалось изменить настройку.');
    } finally {
      toggle.disabled = false;
    }
  });
  api('preferences/', 'GET')
    .then((data) => { toggle.checked = data.enabled; })
    .catch(() => message('Не удалось загрузить настройку.'));

  const emailForm = document.getElementById('staff-email-settings');
  const emailStatus = document.getElementById('staff-email-status');
  emailForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = emailForm.querySelector('button[type=submit]');
    button.disabled = true;
    emailStatus.textContent = '';
    try {
      const response = await fetch('/api/v1/auth/email/request-verification/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({
          email: document.getElementById('staff-email-address').value,
          current_password: document.getElementById('staff-email-password').value,
        }),
      });
      if (!response.ok) throw new Error('Не удалось отправить письмо. Проверьте адрес и пароль.');
      emailStatus.textContent = 'Если адрес доступен, письмо со ссылкой отправлено.';
      document.getElementById('staff-email-password').value = '';
    } catch (error) {
      emailStatus.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
})();
