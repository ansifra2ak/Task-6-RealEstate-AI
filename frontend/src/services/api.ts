export type Dataset = {name: string; role: string; rows: number; columns: number; status: string};
export type Health = {status: string; version: string; phase: string; model_ready: boolean};
async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<T>;
}
export const getHealth = () => get<Health>('/api/v1/health');
export const getDatasets = () => get<{datasets: Dataset[]}>('/api/v1/datasets');
