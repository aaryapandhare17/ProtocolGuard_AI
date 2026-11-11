import { spawnSync } from "node:child_process";
import { cp, mkdir, rm } from "node:fs/promises";
const result = spawnSync("npm", ["run", "build"], {
  stdio: "inherit",
  env: {
    ...process.env,
    ADMIN_BASE_PATH: "/admin/",
    VITE_LIVE_TRANSPORT: "poll",
  },
});
if (result.status !== 0) process.exit(result.status || 1);
await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await cp("apps/securebank/dist", "dist", { recursive: true });
await cp("apps/admin/dist", "dist/admin", { recursive: true });
