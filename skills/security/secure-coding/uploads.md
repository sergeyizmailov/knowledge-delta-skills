# File Uploads & Path Traversal

Related: `express.md` · `ssrf.md` (for fetched URLs that produce files).

## File Upload

```javascript
const multer = require('multer');
const path = require('path');
const crypto = require('crypto');

const ALLOWED_MIME = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 5 * 1024 * 1024;

const upload = multer({
  storage: multer.diskStorage({
    destination: '/tmp/uploads',
    filename: (req, file, cb) => {
      const name = crypto.randomBytes(16).toString('hex');
      const ext = path.extname(file.originalname).toLowerCase();
      cb(null, `${name}${ext}`);
    }
  }),
  limits: { fileSize: MAX_SIZE, files: 1 },
  fileFilter: (req, file, cb) => {
    if (!ALLOWED_MIME.includes(file.mimetype)) {
      return cb(new Error('Invalid file type'));
    }
    cb(null, true);
  }
});
```

Rules:
- Random filenames (never original name)
- Validate MIME type AND extension
- Check magic bytes, not just extension — `file.mimetype` comes from the client, easily spoofed; use `file-type` (npm) on the buffer after upload
- Store outside web root, serve via separate route
- Size limits
- Strip EXIF after upload (`exiftool -all=` or sharp's `.rotate()` chain)

## Path Traversal Prevention

```javascript
const path = require('path');

const SAFE_DIR = '/app/uploads';

function safePath(userInput) {
  const resolved = path.resolve(SAFE_DIR, userInput);
  if (!resolved.startsWith(SAFE_DIR + path.sep) && resolved !== SAFE_DIR) {
    throw new Error('Path traversal attempt');
  }
  return resolved;
}
```

Bypass attempts:
- `../../../etc/passwd`
- `..%2f..%2f..%2fetc/passwd` (URL encoded)
- `..%252f` (double encoding)
- `....//....//etc/passwd` (filter bypass)
- `path.normalize` does NOT prevent traversal by itself
- Absolute paths: `path.resolve(SAFE_DIR, '/etc/passwd')` returns `/etc/passwd` (the check above catches it)
- Symlinks: user-uploaded symlink inside SAFE_DIR escapes via `fs.realpath` — for sensitive ops, also check `realpath` stays in SAFE_DIR
