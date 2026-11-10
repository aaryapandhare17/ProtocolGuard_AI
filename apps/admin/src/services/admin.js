export async function api(path, { method = "GET", body, signal } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    signal,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": sessionStorage.getItem("admin_csrf") || "",
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    data = {
      detail: "Security service returned an invalid response. Try again.",
    };
  }
  if (!response.ok) {
    const message =
      typeof data.detail === "string"
        ? data.detail
        : "Please check the supplied values.";
    if (response.status === 401)
      window.dispatchEvent(new Event("admin:unauthorized"));
    if (response.status === 403 && message === "IP access restricted")
      window.dispatchEvent(new Event("admin:restricted"));
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}
export const dateTime = (value) =>
  value
    ? new Date(value).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "—";
export const shortTime = (value) =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
export const number = (value) => Number(value).toLocaleString();
