export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
export async function request(path, { method = 'GET', body } = {}) {
  const response = await fetch(`/api${path}`, { method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': sessionStorage.getItem('bank_csrf') || '' },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Please check your input and try again.', response.status);
  return data;
}
