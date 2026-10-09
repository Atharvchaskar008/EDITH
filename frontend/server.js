const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.PORT || 3000;
const ROOT_DIR = __dirname;
const APP_DIR = path.join(ROOT_DIR, 'www.un.org', 'en', 'content', 'feature', 'theracetosavespace');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json',
  '.hdr': 'image/vnd.radiance',
  '.mp3': 'audio/mpeg',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain; charset=utf-8'
};

function resolveFilePath(reqUrl) {
  let pathname = '';
  try {
    const parsed = new URL(reqUrl, `http://localhost:${PORT}`);
    pathname = decodeURIComponent(parsed.pathname);
  } catch {
    pathname = reqUrl.split('?')[0];
  }

  pathname = pathname.replace(/\\/g, '/');

  // Prefix handling: /en/content/feature/theracetosavespace
  const prefix = '/en/content/feature/theracetosavespace';
  if (pathname.startsWith(prefix)) {
    const sub = pathname.slice(prefix.length) || '/';
    if (sub === '/' || sub === '/index.html') {
      return path.join(APP_DIR, 'index.html');
    }
    const target = path.join(APP_DIR, sub.replace(/^\//, ''));
    if (fs.existsSync(target) && fs.statSync(target).isFile()) {
      return target;
    }
  }

  // Check direct file under APP_DIR (e.g. /_nuxt/..., /data/..., /img/..., /video/..., /gl/..., /audio/...)
  const directUnderApp = path.join(APP_DIR, pathname.replace(/^\//, ''));
  if (fs.existsSync(directUnderApp) && fs.statSync(directUnderApp).isFile()) {
    return directUnderApp;
  }

  // Check under ROOT_DIR (e.g., /fonts.googleapis.com/..., /fonts.gstatic.com/..., /ipapi.co/...)
  const directUnderRoot = path.join(ROOT_DIR, pathname.replace(/^\//, ''));
  if (fs.existsSync(directUnderRoot) && fs.statSync(directUnderRoot).isFile()) {
    return directUnderRoot;
  }

  // Check ipapi mock
  if (pathname === '/json' || pathname === '/json/' || pathname.includes('ipapi.co/json')) {
    const ipapiFile = path.join(ROOT_DIR, 'ipapi.co', 'json', 'index.html');
    if (fs.existsSync(ipapiFile)) return ipapiFile;
  }

  return null;
}

const server = http.createServer((req, res) => {
  let pathname = '';
  try {
    const parsed = new URL(req.url, `http://localhost:${PORT}`);
    pathname = parsed.pathname;
  } catch {
    pathname = req.url.split('?')[0];
  }

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Redirect root / to Nuxt baseURL /en/content/feature/theracetosavespace/
  if (pathname === '/' || pathname === '') {
    res.writeHead(302, { 'Location': '/en/content/feature/theracetosavespace/' });
    res.end();
    return;
  }

  // API endpoint for ipapi if requested locally
  if (pathname === '/ipapi/json') {
    const ipapiFile = path.join(ROOT_DIR, 'ipapi.co', 'json', 'index.html');
    if (fs.existsSync(ipapiFile)) {
      return serveFile(req, res, ipapiFile);
    }
  }

  const filePath = resolveFilePath(req.url);

  if (!filePath || !fs.existsSync(filePath)) {
    // If it's a SPA route or subpath under baseURL, serve index.html
    if (pathname.startsWith('/en/content/feature/theracetosavespace')) {
      const indexFile = path.join(APP_DIR, 'index.html');
      return serveFile(req, res, indexFile);
    }
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end(`404 Not Found: ${req.url}`);
    return;
  }

  serveFile(req, res, filePath);
});

function serveFile(req, res, filePath) {
  try {
    const stat = fs.statSync(filePath);
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    // Support HTTP Range requests for video/audio seeking
    const range = req.headers.range;
    if (range && (ext === '.mp4' || ext === '.webm' || ext === '.mp3')) {
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : stat.size - 1;

      if (start >= stat.size || end >= stat.size) {
        res.writeHead(416, {
          'Content-Range': `bytes */${stat.size}`
        });
        return res.end();
      }

      const chunksize = end - start + 1;
      const fileStream = fs.createReadStream(filePath, { start, end });
      res.writeHead(206, {
        'Content-Range': `bytes ${start}-${end}/${stat.size}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunksize,
        'Content-Type': contentType,
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      });
      fileStream.pipe(res);
      return;
    }

    res.writeHead(200, {
      'Content-Length': stat.size,
      'Content-Type': contentType,
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'no-store, no-cache, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0'
    });

    const fileStream = fs.createReadStream(filePath);
    fileStream.pipe(res);
  } catch (err) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end(`Internal Error: ${err.message}`);
  }
}

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running at http://localhost:${PORT}/`);
  console.log(`Presenting UN: The Race to Save Space at http://localhost:${PORT}/en/content/feature/theracetosavespace/`);
});
