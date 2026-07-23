const SESSION_TOKEN_KEY = "neutron_session_token";

export function clearSessionToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SESSION_TOKEN_KEY);
}
