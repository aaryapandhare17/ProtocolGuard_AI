const { createHmac } = require("node:crypto");
const { isIP } = require("node:net");

module.exports = function clientIpHeaders(
  request,
  target,
  environment = process.env,
  now = Date.now(),
) {
  const secret = environment.CLIENT_IP_SIGNING_SECRET;
  if (!secret) return {};
  if (Buffer.byteLength(secret, "utf8") < 32)
    throw new Error("Visitor IP signing is misconfigured");
  if (environment.VERCEL !== "1") return {};
  // Vercel overwrites this edge header; never select a client-supplied generic XFF chain.
  const edge = request.headers["x-vercel-forwarded-for"];
  if (typeof edge !== "string" || !isIP(edge.trim()))
    throw new Error("Verified visitor address is unavailable");
  const address = edge.trim();
  const timestamp = String(Math.floor(now / 1000));
  const message = [
    "pg-ip-v1",
    timestamp,
    request.method.toUpperCase(),
    target.pathname,
    address,
  ].join("\n");
  return {
    "x-protocolguard-client-ip": address,
    "x-protocolguard-client-time": timestamp,
    "x-protocolguard-client-signature": createHmac("sha256", secret)
      .update(message)
      .digest("hex"),
  };
};
