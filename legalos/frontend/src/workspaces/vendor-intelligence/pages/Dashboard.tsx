import React, { useState, useEffect } from 'react';
import { 
  Search, 
  AlertOctagon, 
  CheckCircle, 
  Clock, 
  ShieldAlert, 
  History,
  Building,
  Calendar,
  AlertTriangle,
  MapPin,
  Activity,
  FileText,
  Tag,
  Copy,
  Globe,
  Zap,
  Check,
  ShieldCheck,
  Download
} from 'lucide-react';
import { Card } from '@/design-system/components/Card';
import { Button } from '@/design-system/components/Button';
import { Badge } from '@/design-system/components/Badge';
import { Skeleton } from '@/design-system/components/Skeleton';
import { verifyVendor, listVendorAudits } from '../api';
import { VendorCheck } from '@/api/types';

export const Dashboard: React.FC = () => {
  const [gstin, setGstin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VendorCheck | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'address' | 'raw'>('overview');
  const [history, setHistory] = useState<VendorCheck[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [copiedJson, setCopiedJson] = useState(false);

  const fetchHistory = async () => {
    try {
      const data = await listVendorAudits();
      setHistory(data);
    } catch (err: any) {
      console.error('Failed to load audit history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (gstin.trim().length !== 15) {
      setError('GSTIN must be exactly 15 characters.');
      return;
    }
    setError(null);
    setLoading(true);
    setResult(null);

    try {
      const data = await verifyVendor(gstin.trim());
      setResult(data);
      setActiveTab('overview');
      await fetchHistory();
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Failed to verify GSTIN. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getTrustScoreStyles = (check: VendorCheck) => {
    if (check.fraud_flagged) return {
      card: 'border-red-500/40 bg-gradient-to-b from-red-950/40 to-[#0D1322] shadow-glow-ruby',
      badge: 'bg-red-950/80 text-red-300 border-red-500/40',
      textColor: 'text-red-400'
    };
    const score = check.trust_score || 0;
    if (score >= 70) return {
      card: 'border-emerald-500/40 bg-gradient-to-b from-emerald-950/30 to-[#0D1322] shadow-glow-emerald',
      badge: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40',
      textColor: 'text-emerald-400'
    };
    if (score >= 40) return {
      card: 'border-amber-500/40 bg-gradient-to-b from-amber-950/30 to-[#0D1322] shadow-glow-amber',
      badge: 'bg-amber-950/80 text-amber-300 border-amber-500/40',
      textColor: 'text-amber-400'
    };
    return {
      card: 'border-red-500/40 bg-gradient-to-b from-red-950/30 to-[#0D1322] shadow-glow-ruby',
      badge: 'bg-red-950/80 text-red-300 border-red-500/40',
      textColor: 'text-red-400'
    };
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Header Banner */}
      <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-r from-[#0D1322] via-[#141C30] to-[#0D1322] p-6 md:p-8 shadow-glass-card flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[11px] font-mono">
            <Zap className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>Sandbox.co.in Live Statutory Verification</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Vendor Intelligence & GSTIN Fraud Shield
          </h2>
          <p className="text-slate-400 text-xs md:text-sm max-w-2xl leading-relaxed">
            Protect your company from Input Tax Credit (ITC) loss and statutory vendor non-compliance. Screen GSTIN records in real-time, audit filing frequencies, and maintain an immutable compliance log.
          </p>
        </div>

        <div className="flex-shrink-0 flex items-center gap-3">
          <div className="p-3 rounded-xl bg-[#090D16] border border-white/[0.08] text-right font-mono">
            <span className="text-[10px] text-slate-400 block uppercase">ITC Shield Status</span>
            <span className="text-sm font-bold text-emerald-400">100% Protected</span>
          </div>
        </div>
      </div>

      {/* Verification Cockpit Form */}
      <Card 
        title="Live GSTIN Statutory Verification" 
        subtitle="Search official Indian GSTIN records via Sandbox.co.in REST APIs"
      >
        <form onSubmit={handleVerify} className="space-y-4 max-w-2xl">
          <div>
            <label htmlFor="gstin" className="block text-xs font-mono uppercase tracking-wider text-slate-300 font-bold mb-2">
              Enter 15-character Indian GSTIN Number
            </label>
            <div className="relative rounded-xl shadow-inner">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <Search className="w-4 h-4" />
              </div>
              <input
                type="text"
                name="gstin"
                id="gstin"
                className="block w-full pl-10 pr-3.5 py-3 bg-[#090D16] border border-white/15 rounded-xl focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-sm font-mono text-white tracking-widest placeholder:text-slate-500 uppercase outline-none transition-all"
                placeholder="e.g. 29AABCU9603R1ZM"
                value={gstin}
                onChange={(e) => setGstin(e.target.value.toUpperCase())}
                maxLength={15}
                disabled={loading}
              />
            </div>
            {error && <p className="mt-2 text-xs text-red-400 font-mono font-medium">{error}</p>}
          </div>

          <div className="flex flex-wrap gap-3 pt-1">
            <Button 
              type="submit" 
              variant="primary" 
              size="md"
              isLoading={loading} 
              disabled={gstin.length !== 15}
              className="font-semibold text-xs shadow-glow-blue"
            >
              Verify Statutory Registry
            </Button>
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => {
                setGstin('27AAAAA1111A1Z1');
                setError(null);
              }}
              disabled={loading}
              className="text-xs font-mono"
            >
              Load Flagged / Cancelled GSTIN Demo
            </Button>
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => {
                setGstin('29AABCU9603R1ZM');
                setError(null);
              }}
              disabled={loading}
              className="text-xs font-mono"
            >
              Load Active Enterprise GSTIN Demo
            </Button>
          </div>
        </form>
      </Card>

      {/* Loading Skeleton */}
      {loading && (
        <Card title="Querying Live Statutory Registry..." subtitle="Authenticating token with Sandbox.co.in...">
          <div className="space-y-4">
            <Skeleton className="h-6 w-1/4" />
            <Skeleton className="h-24 w-full" />
            <div className="grid grid-cols-2 gap-4">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
          </div>
        </Card>
      )}

      {/* Verification Result Dossier */}
      {result && (
        <div className={`rounded-2xl border p-6 backdrop-blur-xl transition-all duration-300 ${getTrustScoreStyles(result).card}`}>
          <div className="md:flex md:items-start md:justify-between gap-6">
            <div className="space-y-4 flex-1">
              <div>
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-blue-400" />
                  Statutory Verification Audit Dossier
                </span>
                <h3 className="text-xl md:text-2xl font-bold text-white mt-1 flex items-center gap-2 tracking-tight">
                  <Building className="w-6 h-6 text-blue-400 shrink-0" />
                  {result.company_name}
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-[#090D16]/80 border border-white/[0.06] rounded-xl">
                  <span className="text-[10px] text-slate-400 block font-mono font-bold uppercase">GSTIN Identifier</span>
                  <span className="text-xs font-mono font-bold text-blue-300 tracking-wider mt-0.5 block">
                    {result.gstin}
                  </span>
                </div>

                <div className="p-3 bg-[#090D16]/80 border border-white/[0.06] rounded-xl">
                  <span className="text-[10px] text-slate-400 block font-mono font-bold uppercase">Registration Date</span>
                  <span className="text-xs font-mono font-semibold text-slate-200 mt-0.5 block">
                    {result.registration_date ? new Date(result.registration_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
                  </span>
                </div>

                <div className="p-3 bg-[#090D16]/80 border border-white/[0.06] rounded-xl">
                  <span className="text-[10px] text-slate-400 block font-mono font-bold uppercase">Registry Status</span>
                  <span className={`text-xs font-bold font-mono mt-0.5 flex items-center gap-1.5 ${result.is_valid ? 'text-emerald-400' : 'text-red-400'}`}>
                    <span className={`w-2 h-2 rounded-full ${result.is_valid ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                    {result.is_valid ? 'Active Taxpayer' : 'Suspended / Cancelled'}
                  </span>
                </div>
              </div>

              {/* Tab Selector */}
              <div className="border-b border-white/[0.08] mt-6 mb-4 flex gap-6">
                <button
                  type="button"
                  onClick={() => setActiveTab('overview')}
                  className={`pb-3 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                    activeTab === 'overview'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Building className="w-3.5 h-3.5" />
                  Company Details
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('address')}
                  className={`pb-3 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                    activeTab === 'address'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <MapPin className="w-3.5 h-3.5" />
                  Address & Activities
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('raw')}
                  className={`pb-3 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                    activeTab === 'raw'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  Raw Registry JSON
                </button>
              </div>

              {/* Tab Content */}
              <div className="mt-4 min-h-[140px]">
                {activeTab === 'overview' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 bg-[#090D16]/70 border border-white/[0.06] rounded-xl">
                      <span className="text-[10px] font-mono text-slate-400 block font-bold uppercase">Legal Name (lgnm)</span>
                      <span className="text-xs font-semibold text-white mt-1 block">
                        {result.raw_mock_response?.lgnm || result.raw_mock_response?.legalName || result.company_name || 'N/A'}
                      </span>
                    </div>

                    <div className="p-3 bg-[#090D16]/70 border border-white/[0.06] rounded-xl">
                      <span className="text-[10px] font-mono text-slate-400 block font-bold uppercase">Trade Name (tradeNam)</span>
                      <span className="text-xs font-semibold text-white mt-1 block">
                        {result.raw_mock_response?.tradeNam || result.raw_mock_response?.tradeName || 'N/A'}
                      </span>
                    </div>

                    <div className="p-3 bg-[#090D16]/70 border border-white/[0.06] rounded-xl">
                      <span className="text-[10px] font-mono text-slate-400 block font-bold uppercase">Constitution of Business</span>
                      <span className="text-xs font-semibold text-slate-300 mt-1 block">
                        {result.raw_mock_response?.ctb || result.raw_mock_response?.constitutionOfBusiness || 'N/A'}
                      </span>
                    </div>

                    <div className="p-3 bg-[#090D16]/70 border border-white/[0.06] rounded-xl">
                      <span className="text-[10px] font-mono text-slate-400 block font-bold uppercase">Taxpayer Type</span>
                      <span className="text-xs font-semibold text-slate-300 mt-1 block">
                        {result.raw_mock_response?.dty || result.raw_mock_response?.taxpayerType || 'N/A'}
                      </span>
                    </div>

                    <div className="p-3 bg-[#090D16]/70 border border-white/[0.06] rounded-xl">
                      <span className="text-[10px] font-mono text-slate-400 block font-bold uppercase">State Jurisdiction</span>
                      <span className="text-xs font-semibold text-slate-300 mt-1 block">
                        {result.raw_mock_response?.stj ? (
                          result.raw_mock_response?.stjCd ? `${result.raw_mock_response.stj} (${result.raw_mock_response.stjCd})` : result.raw_mock_response.stj
                        ) : 'N/A'}
                      </span>
                    </div>

                    <div className="p-3 bg-[#090D16]/70 border border-white/[0.06] rounded-xl">
                      <span className="text-[10px] font-mono text-slate-400 block font-bold uppercase">Central Jurisdiction</span>
                      <span className="text-xs font-semibold text-slate-300 mt-1 block">
                        {result.raw_mock_response?.ctj ? (
                          result.raw_mock_response?.ctjCd ? `${result.raw_mock_response.ctj} (${result.raw_mock_response.ctjCd})` : result.raw_mock_response.ctj
                        ) : 'N/A'}
                      </span>
                    </div>
                  </div>
                )}

                {activeTab === 'address' && (
                  <div className="space-y-3">
                    <div className="p-4 bg-[#090D16]/80 border border-white/[0.06] rounded-xl space-y-2">
                      <div className="flex items-center gap-2 text-blue-400 font-mono font-bold text-xs uppercase tracking-wider">
                        <MapPin className="w-3.5 h-3.5" />
                        Principal Place of Business Address
                      </div>
                      <p className="text-xs font-mono text-slate-300 leading-relaxed bg-[#141C30]/50 p-3 rounded-lg border border-white/[0.04]">
                        {(() => {
                          const addr = result.raw_mock_response?.pradr?.addr || result.raw_mock_response?.principalAddress?.addr;
                          if (!addr) return 'No registered principal address found.';
                          return [
                            addr.flno ? `Floor ${addr.flno}` : '',
                            addr.bno ? `Bldg No. ${addr.bno}` : '',
                            addr.bnm ? addr.bnm : '',
                            addr.st ? addr.st : '',
                            addr.loc ? addr.loc : '',
                            addr.dst ? addr.dst : '',
                            addr.stcd ? addr.stcd : '',
                            addr.pncd ? `PIN: ${addr.pncd}` : ''
                          ].filter(Boolean).join(', ');
                        })()}
                      </p>
                    </div>
                  </div>
                )}

                {activeTab === 'raw' && (
                  <div className="space-y-2">
                    <div className="flex justify-between items-center bg-[#141C30] p-2.5 rounded-t-xl border-t border-x border-white/[0.08]">
                      <span className="text-xs font-mono text-slate-400">Sandbox.co.in Direct API Response</span>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(JSON.stringify(result.raw_mock_response, null, 2));
                          setCopiedJson(true);
                          setTimeout(() => setCopiedJson(false), 2000);
                        }}
                        className="text-xs font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1 cursor-pointer"
                      >
                        {copiedJson ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        <span>{copiedJson ? 'Copied!' : 'Copy JSON'}</span>
                      </button>
                    </div>
                    <pre className="text-xs font-mono text-slate-300 bg-[#090D16] p-4 rounded-b-xl border border-white/[0.08] overflow-x-auto max-h-[300px] leading-relaxed">
                      {JSON.stringify(result.raw_mock_response, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              {/* Critical Alert Banner if Flagged */}
              {result.fraud_flagged && (
                <div className="p-4 bg-red-950/70 border border-red-500/40 rounded-xl flex gap-3 text-red-300 mt-4 shadow-glow-ruby">
                  <ShieldAlert className="w-5 h-5 text-red-400 flex-shrink-0" />
                  <div>
                    <h4 className="font-bold text-xs uppercase tracking-wider font-mono">Input Tax Credit (ITC) Risk Flagged</h4>
                    <p className="text-xs mt-1 text-red-200 leading-relaxed font-sans">
                      {result.raw_mock_response?.reason || 'Vendor GSTIN is cancelled or suspended. Claiming ITC against this invoice violates Section 16 of CGST Act.'}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Trust Score Gauge Card */}
            <div className="mt-6 md:mt-0 p-6 rounded-2xl border border-white/[0.08] bg-[#090D16]/90 flex flex-col items-center justify-center text-center w-full md:w-52 shadow-glass-card">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">Statutory Trust Score</span>
              <span className={`text-5xl font-black font-mono my-2 ${getTrustScoreStyles(result).textColor}`}>
                {result.trust_score}
              </span>
              <span className="text-[10px] font-mono text-slate-400 mb-3">out of 100</span>
              <span className={`text-[10px] font-mono font-bold tracking-wider uppercase px-2.5 py-1 rounded-full border ${getTrustScoreStyles(result).badge}`}>
                {result.fraud_flagged ? 'Critical Risk' : (result.trust_score || 0) >= 70 ? 'High Trust / Safe' : 'Caution Required'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Audit History Log */}
      <Card title="Vendor Audit Trail & Immutable Log" subtitle="History of all executed statutory vendor audits.">
        {historyLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-10 text-slate-500 flex flex-col items-center justify-center">
            <History className="w-10 h-10 text-slate-600 mb-2" />
            <p className="text-xs font-mono text-slate-400">No vendor verification history available.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/[0.06]">
              <thead>
                <tr className="bg-[#090D16]/60">
                  <th className="px-5 py-3 text-left text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">GSTIN</th>
                  <th className="px-5 py-3 text-left text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">Company Legal Name</th>
                  <th className="px-5 py-3 text-left text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="px-5 py-3 text-center text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">Trust Score</th>
                  <th className="px-5 py-3 text-left text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">Audit Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {history.map((item) => (
                  <tr key={item.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5 whitespace-nowrap text-xs font-mono font-bold text-blue-400 tracking-wider">
                      {item.gstin}
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-xs font-medium text-slate-200">
                      {item.company_name}
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-xs">
                      {item.fraud_flagged ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-red-950/80 text-red-300 border border-red-500/30">
                          <ShieldAlert className="w-3 h-3 text-red-400" />
                          Fraud / Cancelled
                        </span>
                      ) : item.is_valid ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/30">
                          <CheckCircle className="w-3 h-3 text-emerald-400" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-white/10 text-slate-300">
                          Suspended
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-center text-xs font-mono font-bold">
                      <span className={item.fraud_flagged ? 'text-red-400' : (item.trust_score || 0) >= 70 ? 'text-emerald-400' : 'text-amber-400'}>
                        {item.trust_score}/100
                      </span>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-xs font-mono text-slate-400">
                      {new Date(item.checked_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
export default Dashboard;
