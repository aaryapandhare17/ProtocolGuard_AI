import { createRequire } from "node:module";
import { isIP } from "node:net";
import { fileURLToPath } from "node:url";
import { loadEnv } from "vite";
const clientIpHeaders = createRequire(import.meta.url)("./client-ip.cjs");

const root = fileURLToPath(new URL("../", import.meta.url));
const headers = [
  "x-protocolguard-client-ip",
  "x-protocolguard-client-time",
  "x-protocolguard-client-signature",
];

export function viteApiProxy(mode, target) {
  const origin = new URL(target);
  const secret = loadEnv(mode, root, "CLIENT_IP_SIGNING_SECRET").CLIENT_IP_SIGNING_SECRET;
  const local = ["127.0.0.1", "localhost", "[::1]"].includes(origin.hostname);
  if (local && secret && Buffer.byteLength(secret) < 32) {
    throw new Error("CLIENT_IP_SIGNING_SECRET must contain at least 32 bytes");
  }
  return {
    target,
    configure(proxy) {
      proxy.on("proxyReq", (outgoing, incoming) => {
        for (const name of headers) outgoing.removeHeader(name);
        const address = incoming.socket.remoteAddress;
        if (!local || !secret || !address || !isIP(address)) return;

        const path = outgoing.path.split("?", 1)[0];
        for (const [name, value] of Object.entries(
          clientIpHeaders.signClientIp(address, outgoing.method, path, secret),
        )) {
          outgoing.setHeader(name, value);
        }
      });
    },
  };
}
