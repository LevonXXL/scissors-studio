import { defineStore } from 'pinia';
import { getAuthProfile, type AuthResult } from '@/api/endpoints';
import { removeCurrentBrowserSubscription } from '@/push';

function verifiedPhones(profile: { phone: string; phones?: string[] }): string[] {
  const phones = Array.isArray(profile.phones) ? profile.phones : [];
  return phones.length ? phones : profile.phone ? [profile.phone] : [];
}

export const useAuthStore = defineStore('auth', {
  state: () => ({ authenticated: false, phone: '', phones: [] as string[], email: '', pendingEmail: '', isStaff: false, hasPassword: false, pushEnabled: false }),
  actions: {
    async restore() {
      if (typeof window === 'undefined') return;
      const access = window.localStorage.getItem('access_token');
      if (!access) return;
      try {
        const profile = await getAuthProfile();
        if (window.localStorage.getItem('access_token') !== access) return;
        this.authenticated = true;
        this.phones = verifiedPhones(profile);
        this.phone = profile.phone || this.phones[0] || '';
        this.email = profile.email;
        this.pendingEmail = profile.pending_email;
        this.isStaff = profile.is_staff;
        this.hasPassword = profile.has_password;
        this.pushEnabled = profile.push_enabled;
      } catch {
        if (window.localStorage.getItem('access_token') === access) void this.logout();
      }
    },
    accept(result: AuthResult) {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem('access_token', result.access);
      this.authenticated = true;
      this.phones = verifiedPhones(result);
      this.phone = result.phone || this.phones[0] || '';
      this.email = result.email;
      this.pendingEmail = result.pending_email;
      this.isStaff = result.is_staff;
      this.hasPassword = result.has_password;
      this.pushEnabled = result.push_enabled;
    },
    async logout() {
      try {
        if (typeof window !== 'undefined') await removeCurrentBrowserSubscription();
      } finally {
        if (typeof window !== 'undefined') window.localStorage.removeItem('access_token');
        this.authenticated = false;
        this.phone = '';
        this.phones = [];
        this.email = '';
        this.pendingEmail = '';
        this.isStaff = false;
        this.hasPassword = false;
        this.pushEnabled = false;
      }
    },
  },
});
