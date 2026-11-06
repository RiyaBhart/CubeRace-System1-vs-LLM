"""Platform/packaging checks; no external requests or live agents."""
import asyncio
from pathlib import Path
import httpx
from backend.app.main import app
from backend.app.platform_compat import file_lock, peak_memory_bytes


def test_javascript_mime_type_is_safe_under_nosniff():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
            response=await client.get('/static/cube-view.js')
            assert response.status_code==200
            assert response.headers['content-type'].startswith('application/javascript')
            assert response.headers['x-content-type-options']=='nosniff'
            config=(await client.get('/api/config')).json()
            assert 'api_key' not in config and 'openrouter_api_key' not in config
    asyncio.run(check())


def test_windows_lease_rejects_parallel_owner_and_releases_on_close(tmp_path):
    from backend.app.storage import RunStore
    store=RunStore(tmp_path)
    first=store.execution_lease()
    assert first is not None
    assert store.execution_lease() is None
    first.close()
    next_owner=store.execution_lease()
    assert next_owner is not None
    next_owner.close()
    assert peak_memory_bytes()>0


def test_independent_shell_and_theme_keep_required_controls():
    from backend.app.config import ROOT
    for name in ('index.html','dashboard.html'):
        html=(ROOT/'frontend'/name).read_text(encoding='utf-8')
        assert '/static/local-theme.css' in html
        assert 'workspace-intro' in html and 'workspace-links' in html
        assert 'Adapted source: Srijaali/ai-engineering' in html
        assert 'id="identity"' in html and 'id="consent"' in html
        assert 'Fixed low reasoning / 1,024' not in html
    from scripts.check_contrast import ratio
    for foreground, background in [('#edf3fc','#0b1422'),('#b2bfd2','#122137'),
                                   ('#11223b','#8dbdff'),('#edf3fc','#205049')]:
        assert ratio(foreground,background)>=4.5
