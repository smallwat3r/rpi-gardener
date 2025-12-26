import type { AdminSettings } from '@/types';

export async function getAdminSettings(): Promise<AdminSettings> {
  const response = await fetch('/api/admin/settings');
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Unauthorized');
    }
    if (response.status === 503) {
      throw new Error('Admin not configured');
    }
    throw new Error(`Failed to get settings: ${response.statusText}`);
  }
  return response.json();
}

export async function updateAdminSettings(
  settings: Partial<AdminSettings>,
): Promise<AdminSettings> {
  const response = await fetch('/api/admin/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.errors?.join(', ') || data.error || 'Update failed');
  }
  return response.json();
}
