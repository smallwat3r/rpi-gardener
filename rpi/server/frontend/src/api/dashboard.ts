import type { DashboardData } from '@/types';

export async function fetchDashboardData(hours: number = 3): Promise<DashboardData> {
  const response = await fetch(`/api/dashboard?hours=${hours}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard data: ${response.statusText}`);
  }
  return response.json();
}
