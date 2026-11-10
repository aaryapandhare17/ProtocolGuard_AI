import { ShieldCheck, ArrowRight } from 'lucide-react';
import { useHealth } from './hooks/useHealth';
export default function App() {
  const status = useHealth();
  return <main><header><span className="brand"><ShieldCheck size={24} />ProtocolGuard AI</span><span className="badge" role="status">{status}</span></header><section><p className="eyebrow">SECURITY OPERATIONS</p><h1>Understand every session.</h1><p className="intro">Finite-state analysis, machine learning, and clear evidence. One connected view of banking security.</p><div className="panel"><ArrowRight size={22} /><div><h2>Application foundation ready</h2><p>Live monitoring and detector analytics will be added in upcoming features.</p></div></div><p className="footnote">Academic demonstration · Dummy financial data only</p></section></main>;
}
