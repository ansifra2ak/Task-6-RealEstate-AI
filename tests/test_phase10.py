import sys, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_phase10 import collect, number, private_path, SHOTS, generate

def test_missing_reports_are_not_success(tmp_path):
    d=collect(tmp_path,reference=True)
    assert not any(v['passed'] for v in d['validations'])
    assert number(None)=='Not available'

def test_private_paths():
    for p in ['.env.phase5','.phase9-private/champion/model/MLmodel','models/a.joblib','screenshots/01.png','reports/phase10/a.docx','infrastructure/a.tfstate']:
        assert private_path(p)
    assert not private_path('backend/main.py')
    assert not private_path('.env.example')

def test_png_alias_and_signature(tmp_path):
    folder=tmp_path/'screenshots'; folder.mkdir(); (folder/'13_phase3_model_performance.png').write_bytes(b'\x89PNG\r\n\x1a\n'); (folder/'01_project_structure.png').write_text('not PNG')
    d=collect(tmp_path,reference=True)
    assert len(SHOTS)==40 and d['screenshots'][12]['found']=='13_phase3_model_performance.png'
    assert not d['screenshots'][0]['found']

def test_generate_missing_evidence(tmp_path):
    out=tmp_path/'out'; deck=tmp_path/'deck'; generate(tmp_path,out,deck,reference=True)
    from pptx import Presentation
    from docx import Document
    assert len(Presentation(deck/'realestate_ai_presentation.pptx').slides)==12
    assert Document(out/'technical_report.docx').paragraphs
    assert 'Not available' in (out/'model_card.md').read_text()
    assert json.loads((out/'verification.json').read_text())['manual_review_required']
