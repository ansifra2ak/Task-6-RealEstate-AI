"""Task 6 Render entrypoint. Single worker; private snapshot loaded at runtime only."""
import base64
import hashlib
import hmac
import io
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import tarfile
import tempfile
from urllib.parse import urlsplit

MAX_ENCODED = 950_000
MAX_UNPACKED = 16 * 1024 * 1024
MAX_FILES = 512
RUNTIME_FILE = 'task6-runtime.b64'
EXACT = frozenset({
    'data/manifest.json', 'data/raw/house_prices.csv', 'data/processed/train.csv',
    'data/processed/split_manifest.json', 'reports/phase3_model_summary.json',
    'reports/phase3_model_comparison.csv', 'visualizations/phase3_model_performance.png',
    'visualizations/phase3_neural_network_training.png', 'visualizations/phase3_prediction_evaluation.png',
    'champion/deployment.json', '.task6-phase9-generated',
})


def allowed_file(name):
    return name in EXACT or name.startswith('champion/model/')


def allowed_dir(name):
    return name == '.' or name == 'champion/model' or name.startswith('champion/model/') or any(p.startswith(name + '/') for p in EXACT)


def normalized(name):
    if not name or '\\' in name or '\x00' in name or name.startswith('/'):
        raise ValueError('Unsafe runtime path')
    p = PurePosixPath(name)
    if '..' in p.parts or any(x.startswith('.') and x != '.task6-phase9-generated' for x in p.parts):
        raise ValueError('Unsafe runtime path')
    return p.as_posix()


def unpack(encoded, expected_sha, dest):
    """Reject traversal, links, duplicates, unexpected files and decompression bombs."""
    if not re.fullmatch(r'[a-f0-9]{64}', expected_sha or ''):
        raise ValueError('Expected runtime SHA256 is missing or invalid')
    if len(encoded) > MAX_ENCODED:
        raise ValueError('Encoded runtime exceeds safe secret file size')
    compressed = base64.b64decode(b''.join(encoded.split()), validate=True)
    if not hmac.compare_digest(hashlib.sha256(compressed).hexdigest(), expected_sha):
        raise ValueError('Runtime archive checksum mismatch')
    dest = Path(dest)
    if dest.is_symlink() or not dest.is_dir() or any(dest.iterdir()):
        raise ValueError('Runtime destination must be a fresh private directory')
    seen = set(); total = 0
    with tarfile.open(fileobj=io.BytesIO(compressed), mode='r:gz') as archive:
        for member in archive:
            name = normalized(member.name)
            if name in seen or len(seen) >= MAX_FILES:
                raise ValueError('Duplicate path or too many runtime entries')
            seen.add(name)
            target = dest / name
            if member.isdir() and allowed_dir(name):
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
                continue
            if not member.isfile() or not allowed_file(name):
                raise ValueError('Unexpected runtime entry')
            total += member.size
            if total > MAX_UNPACKED or member.size < 0:
                raise ValueError('Runtime exceeds unpacked size limit')
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with archive.extractfile(member) as src, target.open('xb') as out:
                out.write(src.read(member.size + 1))
            target.chmod(0o600)
    if not (EXACT - {'.task6-phase9-generated'}).issubset(seen) or not (dest/'champion/model/MLmodel').is_file():
        raise ValueError('Incomplete runtime archive')
    from backend.phase9_runtime import verify_bundle
    return verify_bundle(dest)


def public_origin(value):
    parsed = urlsplit(value or '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
        parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.port is not None or
        not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', parsed.hostname)):
        raise ValueError('Set RENDER_EXTERNAL_URL to the exact HTTPS service origin')
    return 'https://' + parsed.hostname


class CloudGate:
    """Only /healthz is public. Reuse the exact-origin and Basic Auth Phase 9 guard."""
    def __init__(self, app, origin, password):
        from backend.phase9_runtime import PublicGuard
        if not isinstance(password, str) or len(password) < 32 or any(c.isspace() for c in password):
            raise ValueError('Set a fresh viewer password of at least 32 characters without spaces')
        self.app = PublicGuard(app, public_origin(origin), password)
        self.inflight = 0

    async def __call__(self, scope, receive, send):
        from starlette.responses import JSONResponse
        if scope['type'] == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        if scope['path'] == '/healthz' and scope['method'] in ('GET', 'HEAD'):
            return await JSONResponse({'status':'ok'}, headers={'Cache-Control':'no-store'})(scope, receive, send)
        if self.inflight >= 8:
            return await JSONResponse({'detail':'Service busy'}, status_code=503, headers={'Retry-After':'5','Cache-Control':'no-store'})(scope,receive,send)
        self.inflight += 1
        try:
            return await self.app(scope, receive, send)
        finally:
            self.inflight -= 1


def create_cloud_gateway(root, api, api_key, origin, password):
    import httpx
    from backend.phase6_gateway import create_gateway
    # No network API port: the existing allowlisted gateway calls FastAPI in-process.
    transport = httpx.ASGITransport(app=api, raise_app_exceptions=False)
    gateway = create_gateway(root, api_key, transport=transport)
    return CloudGate(gateway, origin, password)


def main():
    import uvicorn
    from backend.phase9_runtime import api
    origin = public_origin(os.environ.get('RENDER_EXTERNAL_URL'))
    password = os.environ.get('TASK6_RENDER_VIEWER_PASSWORD', '')
    if len(password) < 32 or any(c.isspace() for c in password):
        raise ValueError('Viewer password missing or too short')
    # Require explicit configuration; do not fall back to a local bundle or public files.
    if os.environ.get('TASK6_RENDER_AUTHORIZED') != 'YES':
        raise ValueError('Authorized data/model hosting confirmation missing')
    path = Path('/etc/secrets') / RUNTIME_FILE
    with tempfile.TemporaryDirectory(prefix='task6-runtime-') as td:
        root = Path(td)
        with path.open('rb') as f:
            encoded = f.read(MAX_ENCODED + 1)
        unpack(encoded, os.environ.get('TASK6_RENDER_SHA256', ''), root)
        del encoded
        # The existing Phase 9 factory expects a file-backed API key, generated fresh in memory.
        api_key = secrets.token_urlsafe(40)
        keyfile = root / '.api_key'
        keyfile.write_text(api_key); keyfile.chmod(0o600)
        os.environ['TASK6_API_KEY_FILE'] = str(keyfile)
        # The private root contains reports/charts; the React build lives in the source-only image.
        (root/'frontend').symlink_to(Path('/app/frontend'), target_is_directory=True)
        app = create_cloud_gateway(root, api(root), api_key, origin, password)
        keyfile.unlink()
        print('Task 6 runtime integrity and champion parity verified; HTTPS gateway ready.', flush=True)
        uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT','10000')), workers=1,
                    access_log=False, proxy_headers=False, limit_concurrency=16, timeout_keep_alive=5)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Avoid reporting credentials, dataset rows or archive content in provider logs.
        print('Render startup failed: ' + type(exc).__name__ + '. Check runtime configuration, dependency compatibility and local parity.', flush=True)
        raise SystemExit(1) from None
