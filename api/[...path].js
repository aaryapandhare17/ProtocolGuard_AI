/** Same-origin API bridge: cookies stay on Vercel; the backend URL is server-only. */
const MAX_BODY = 64 * 1024;
function backendOrigin(value) {
  const url = new URL(value);
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw new Error("BACKEND_ORIGIN must be one exact HTTPS origin");
  return url.origin;
}
async function requestBody(request) {
  if (["GET", "HEAD"].includes(request.method)) return undefined;
  let body;
  if (request.body !== undefined) {
    body = Buffer.isBuffer(request.body)
      ? request.body
      : Buffer.from(
          typeof request.body === "string"
            ? request.body
            : JSON.stringify(request.body),
        );
  } else {
    const chunks = [];
    let size = 0;
    for await (const chunk of request) {
      const buffer = Buffer.from(chunk);
      size += buffer.length;
      if (size > MAX_BODY) throw new Error("PAYLOAD_LIMIT");
      chunks.push(buffer);
    }
    body = Buffer.concat(chunks);
  }
  if (body.length > MAX_BODY) throw new Error("PAYLOAD_LIMIT");
  return body;
}
async function proxy(request, response) {
  response.setHeader("Cache-Control", "private, no-store");
  if (!["GET", "HEAD", "POST", "OPTIONS"].includes(request.method)) {
    response.setHeader("Allow", "GET, HEAD, POST, OPTIONS");
    return response.status(405).json({ detail: "Method not allowed" });
  }
  let origin;
  try {
    origin = backendOrigin(process.env.BACKEND_ORIGIN);
  } catch {
    return response
      .status(503)
      .json({ detail: "Backend connection is not configured" });
  }
  const incoming = new URL(request.url, "https://frontend.invalid");
  if (!incoming.pathname.startsWith("/api/"))
    return response.status(404).json({ detail: "Not found" });
  const target = new URL(incoming.pathname + incoming.search, origin);
  // Do not forward user-supplied host, proxy identity or arbitrary authorization headers.
  const headers = {};
  for (const name of [
    "content-type",
    "accept",
    "cookie",
    "origin",
    "x-csrf-token",
  ]) {
    if (typeof request.headers[name] === "string")
      headers[name] = request.headers[name];
  }
  try {
    const body = await requestBody(request);
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
      signal: AbortSignal.timeout(25000),
    });
    response.status(upstream.status);
    for (const name of ["content-type", "allow", "retry-after"]) {
      const value = upstream.headers.get(name);
      if (value) response.setHeader(name, value);
    }
    const cookies = upstream.headers.getSetCookie();
    if (cookies.length) response.setHeader("Set-Cookie", cookies);
    const location = upstream.headers.get("location");
    if (location) {
      const redirect = new URL(location, target);
      if (redirect.origin === origin)
        response.setHeader("Location", redirect.pathname + redirect.search);
    }
    response.end(
      request.method === "HEAD"
        ? undefined
        : Buffer.from(await upstream.arrayBuffer()),
    );
  } catch (error) {
    const oversized = error.message === "PAYLOAD_LIMIT";
    response
      .status(oversized ? 413 : 502)
      .json({
        detail: oversized
          ? "Request is too large"
          : "Backend is temporarily unavailable",
      });
  }
}
module.exports = proxy;
module.exports.backendOrigin = backendOrigin;
