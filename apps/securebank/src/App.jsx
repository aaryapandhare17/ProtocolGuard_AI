import { ShieldCheck, ArrowRight } from 'lucide-react';
import { useHealth } from './hooks/useHealth';
export default function App() {
  const status = useHealth();
  return <main><header><span className="brand"><ShieldCheck size={24} />SecureBank</span><span className="badge" role="status">{status}</span></header><section><p className="eyebrow">SECUREBANK · DEVELOPMENT</p><h1>Banking with security in mind.</h1><p className="intro">A simulated banking experience connected to ProtocolGuard AI for intelligent session monitoring.</p><div className="panel"><ArrowRight size={22} /><div><h2>Application foundation ready</h2><p>Authentication and banking actions will be added in upcoming features.</p></div></div><p className="footnote">Academic demonstration · Dummy financial data only</p></section></main>;
}
