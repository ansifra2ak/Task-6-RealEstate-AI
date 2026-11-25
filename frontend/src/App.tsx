import { useEffect, useState } from 'react';
import { getHealth, getDatasets, type Dataset, type Health } from './services/api';
const phases = ['Data engineering','Model training','Experiment registry','Prediction API','Full dashboard','Monitoring','Testing & load tests','Docker & CI/CD','Public deployment','Documentation & career'];
export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [data, setData] = useState<Dataset[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true); setError('');
    try { const [h,d] = await Promise.all([getHealth(),getDatasets()]); setHealth(h); setData(d.datasets); }
    catch(e) {setHealth(null);setData([]);setError(e instanceof Error ? e.message : 'API unavailable');}
    finally {setLoading(false);}
  }
  useEffect(() => {void refresh();}, []);
  return <div className="shell"><aside><div className="brand"><span className="mark">RE</span><div>RealEstate AI<small>CAPSTONE / TASK 06</small></div></div><nav><a href="#overview">Overview</a><a href="#datasets">Dataset inventory</a><a href="#roadmap">Roadmap</a><a href="http://127.0.0.1:8006/docs" target="_blank" rel="noreferrer">API documentation ↗</a></nav><div className="foot">The Developers Arena<br/>Data Science Internship</div></aside><main><header><span>PROJECT FOUNDATION / V0.1.0</span><button onClick={refresh} disabled={loading}>{loading?'Checking…':'Refresh status'}</button></header><section id="overview" className="hero"><p className="eyebrow">PHASE 01 · DEVELOPMENT</p><h1>Real estate price prediction<br/> & intelligence platform</h1><p>A local foundation for a reproducible, full-stack machine learning system. Prediction features are not trained or available yet.</p></section><div className="cards"><article><label>Backend connectivity</label><strong>{loading?'Checking':health?'Online':'Unavailable'}</strong><small>FastAPI health endpoint</small></article><article><label>Primary dataset</label><strong>{data.find(d=>d.role==='primary')?.rows ?? '—'}</strong><small>Property records in manifest</small></article><article><label>Model status</label><strong>{health?.model_ready?'Ready':'Not trained'}</strong><small>Scheduled for Phase 03</small></article></div>{error&&<p role="alert" className="error">{error}. Check the Python launcher and retry.</p>}<section id="datasets" className="panel"><h2>Dataset inventory</h2><p>Integrity verified against the original file hashes. Reference datasets are not joined to property records.</p><div className="scroll"><table><thead><tr><th>File</th><th>Role</th><th>Rows</th><th>Columns</th><th>Integrity</th></tr></thead><tbody>{data.map(d=><tr key={d.name}><td>{d.name}</td><td>{d.role}</td><td>{d.rows}</td><td>{d.columns}</td><td><span className={d.status==='verified'?'good':'warning'}>{d.status}</span></td></tr>)}</tbody></table></div></section><section id="roadmap" className="panel"><h2>Development roadmap</h2><p>Foundation is the current milestone. All remaining phases are planned, not completed.</p><div className="phases">{phases.map((p,i)=><div key={p}><span>{String(i+2).padStart(2,'0')}</span>{p}<small>Planned</small></div>)}</div></section><footer>Educational system · No live market valuation or production SLA</footer></main></div>;
}
