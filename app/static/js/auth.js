// Cookie-based auth for the blog.
//
// The JWT lives in an httpOnly cookie (set by POST /api/users/token), so this
// module never sees a token. `authFetch` is the one blessed fetch wrapper:
// it always sends credentials same-origin and adds the required CSRF header to
// non-GET requests, which the backend's CSRFProtectionMiddleware demands on
// cookie-authenticated writes.
let currentUser = null;
let fetchPromise = null;

const CSRF_HEADER = "X-CSRF-Protected";
const CSRF_VALUE = "1";

function buildFetchOptions(options = {}) {
  const { method = "GET", headers = {}, ...rest } = options;
  const headerObject = headers instanceof Headers
    ? Object.fromEntries(headers)
    : { ...headers };
  return {
    method,
    credentials: "same-origin",
    ...rest,
    headers: method === "GET"
      ? headerObject
      : { ...headerObject, [CSRF_HEADER]: CSRF_VALUE },
  };
}

export async function authFetch(input, options = {}) {
  return fetch(input, buildFetchOptions(options));
}

export async function getCurrentUser() {
  if (currentUser) {
    return currentUser;
  }
  if (fetchPromise) {
    return fetchPromise;
  }

  fetchPromise = (async () => {
    try {
      const response = await authFetch("/api/users/me");
      if (response.ok) {
        currentUser = await response.json();
        return currentUser;
      }
      return null;
    } catch (error) {
      console.error("Error fetching current user:", error);
      return null;
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export async function logout() {
  currentUser = null;
  await fetch("/api/users/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { [CSRF_HEADER]: CSRF_VALUE },
  });
  window.location.href = "/";
}

export function clearUserCache() {
  currentUser = null;
}