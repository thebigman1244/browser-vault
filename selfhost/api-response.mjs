export class ApiResponseError extends Error {
  constructor(message, needsSignIn = false) { super(message); this.needsSignIn = needsSignIn; }
}
export async function readApiResponse(response) {
  if (response.status === 401 || response.status === 403 || response.redirected || response.type === 'opaqueredirect') {
    throw new ApiResponseError('Your secure sign-in needs refreshing. Use Sign in again to reconnect.', true);
  }
  const type = response.headers.get('content-type') || '';
  if (!type.toLowerCase().includes('application/json')) {
    if (response.status >= 500) throw new ApiResponseError('The Pi is temporarily unavailable or restarting. Wait a minute, then reconnect.');
    throw new ApiResponseError('The connection returned a web page instead of the browser service. Sign in again to reconnect.', true);
  }
  let result;
  try { result = await response.json(); }
  catch { throw new ApiResponseError('The browser service returned an incomplete response. Please reconnect.'); }
  if (!response.ok) throw new ApiResponseError(result?.error || 'The server could not complete that request.');
  return result;
}
