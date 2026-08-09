// Custom dev server: runs Next.js (with full HMR) and proxies /api/* to the
// FastAPI backend at the STABLE server level — not via Next's `rewrites()`.
//
// Why: Next's rewrite proxy has an undocumented ~30s timeout and drops in-flight
// sockets on every fast-refresh recompile. Long requests (e.g. LLM /script gen,
// which takes 30-120s) therefore 500 even though the backend succeeds. Proxying
// at this layer removes the timeout and keeps API sockets alive across HMR.
import { createServer } from "node:http";
import { request as httpRequest } from "node:http";
import { URL } from "node:url";
import next from "next";

const dev = process.env.NODE_ENV !== "production";
const port = parseInt(process.env.PORT || "3008", 10);
const BACKEND = process.env.HVA_BACKEND || "http://127.0.0.1:8777";
const backend = new URL(BACKEND);

const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  createServer((req, res) => {
    const url = new URL(req.url || "/", `http://localhost:${port}`);
    const pathname = url.pathname;

    if (pathname.startsWith("/api/")) {
      // Build the backend target URL preserving the path + query string.
      const target = new URL(url.pathname + url.search, backend);
      const opts = {
        protocol: backend.protocol,
        hostname: backend.hostname,
        port: backend.port,
        method: req.method,
        path: target.pathname + target.search,
        headers: { ...req.headers, host: backend.host },
        // No timeout: let long LLM requests run to completion.
      };
      const proxyReq = httpRequest(opts, (proxyRes) => {
        res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
        proxyRes.pipe(res);
      });
      proxyReq.on("error", (err) => {
        if (!res.headersSent) {
          res.writeHead(502, { "content-type": "application/json" });
          res.end(JSON.stringify({ detail: `backend proxy error: ${err.message}` }));
        } else {
          res.destroy();
        }
      });
      req.pipe(proxyReq);
      return;
    }

    // Let Next parse the request itself (avoids handing it a WHATWG URL).
    handle(req, res);
  }).listen(port, () => {
    console.log(`> Ready on http://localhost:${port} (proxy /api -> ${BACKEND})`);
  });
});
