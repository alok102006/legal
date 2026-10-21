import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Building2, 
  Calendar, 
  Sparkles, 
  ShieldAlert,
  Loader2,
  FileText,
  AlertCircle,
  CheckCircle2,
  Copy,
  Check,
  Download,
  Scale
} from 'lucide-react';
import { getContract, generateSuggestion } from '../api';
import { ContractDetail as ContractDetailType, Clause } from '@/api/types';
import Button from '@/design-system/components/Button';
import Card from '@/design-system/components/Card';
import RiskBadge from '@/design-system/components/RiskBadge';
import Skeleton from '@/design-system/components/Skeleton';
import { Badge } from '@/design-system/components/Badge';

export const ContractDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [contract, setContract] = useState<ContractDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Clause details
  const [selectedClause, setSelectedClause] = useState<Clause | null>(null);
  const [generatingSuggest, setGeneratingSuggest] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Filters
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [searchText, setSearchText] = useState('');

  const fetchContractDetails = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getContract(id);
      setContract(data);
      // Auto-select first high-risk clause if available
      const highRisk = data.clauses.find(c => c.risk_score >= 70);
      if (highRisk) {
        setSelectedClause(highRisk);
      } else if (data.clauses.length > 0) {
        setSelectedClause(data.clauses[0]);
      }
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Failed to retrieve contract analysis.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContractDetails();
  }, [id]);

  const handleGenerateSuggestion = async () => {
    if (!contract || !selectedClause) return;
    setGeneratingSuggest(true);
    try {
      const suggestion = await generateSuggestion(contract.id, selectedClause.id);
      
      const updatedClauses = contract.clauses.map(c => {
        if (c.id === selectedClause.id) {
          const updated = {
            ...c,
            suggestions: [suggestion, ...c.suggestions]
          };
          setSelectedClause(updated);
          return updated;
        }
        return c;
      });

      setContract({
        ...contract,
        clauses: updatedClauses
      });
    } catch (err) {
      console.error(err);
    } finally {
      setGeneratingSuggest(false);
    }
  };

  const handleCopySuggestion = (text: string, sid: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(sid);
    setTimeout(() => setCopiedId(null), 2000);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton variant="line" count={2} className="w-1/3" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <Skeleton variant="table" count={5} />
          </div>
          <div className="lg:col-span-1">
            <Skeleton variant="card" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !contract) {
    return (
      <Card className="text-center py-16">
        <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
        <h4 className="text-lg font-bold text-white mb-2">Error Loading Audit</h4>
        <p className="text-xs text-slate-400 mb-6">{error || 'Agreement file not found.'}</p>
        <Button onClick={() => navigate('/')} variant="outline" size="sm">
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Dashboard
        </Button>
      </Card>
    );
  }

  // Filter logic
  const filteredClauses = contract.clauses.filter(c => {
    const textMatch = c.raw_text.toLowerCase().includes(searchText.toLowerCase()) || 
                      (c.summary?.toLowerCase().includes(searchText.toLowerCase()) ?? false);
    const filterMatch = riskFilter === 'all' || 
                        (riskFilter === 'risk' && c.risk_type !== 'none') || 
                        c.risk_type === riskFilter;
    return textMatch && filterMatch;
  });

  const highRiskCount = contract.clauses.filter(c => c.risk_score >= 70).length;

  return (
    <div className="space-y-6 pb-20">
      {/* Header breadcrumb & Navigation Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <button 
          onClick={() => navigate('/')}
          className="inline-flex items-center text-xs font-mono font-semibold text-slate-400 hover:text-white uppercase tracking-wider transition-colors outline-none cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Contracts Dashboard
        </button>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400">
            Total Clauses: <strong className="text-white">{contract.clauses.length}</strong>
          </span>
          {highRiskCount > 0 ? (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-red-950/80 text-red-300 border border-red-500/40 shadow-glow-ruby">
              {highRiskCount} Critical Redlines
            </span>
          ) : (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-500/40">
              Clean Agreement
            </span>
          )}
        </div>
      </div>

      {/* Document Overview Dossier */}
      <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-r from-[#0D1322] via-[#141C30] to-[#0D1322] p-6 shadow-glass-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-slate-400">
            <div className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400">
              <FileText className="w-4 h-4" />
            </div>
            <span className="text-[11px] font-mono font-semibold tracking-wider text-blue-300 uppercase">
              AI Redline & Negotiation Studio
            </span>
          </div>
          <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">{contract.title}</h2>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-slate-400">
            <span className="flex items-center gap-1.5 text-slate-300">
              <Building2 className="w-3.5 h-3.5 text-blue-400" />
              Counterparty: <strong className="text-white font-medium">{contract.counterparty_name}</strong>
            </span>
            <span className="flex items-center gap-1.5 font-mono text-[11px]">
              <Calendar className="w-3.5 h-3.5 text-slate-500" />
              Audited: {new Date(contract.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.print()}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5 mr-1" /> Export Audit Summary
          </Button>
        </div>
      </div>

      {/* Main Studio Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left column: Clause List & Filter Toolbar (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-4 rounded-xl bg-[#0D1322]/90 border border-white/[0.08] shadow-sm flex flex-col sm:flex-row gap-3 items-center justify-between">
            {/* Filter tags */}
            <div className="flex flex-wrap gap-1.5 w-full sm:w-auto">
              {[
                { label: 'All Clauses', val: 'all' },
                { label: 'Risk Flags', val: 'risk' },
                { label: 'Indemnity', val: 'indemnity' },
                { label: 'Liability', val: 'penalty' },
                { label: 'Termination', val: 'termination' },
              ].map(f => (
                <button
                  key={f.val}
                  onClick={() => setRiskFilter(f.val)}
                  className={`
                    px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all outline-none cursor-pointer
                    ${riskFilter === f.val 
                      ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50 shadow-glow-blue font-semibold' 
                      : 'bg-[#141C30] border border-white/10 text-slate-400 hover:text-slate-200 hover:border-white/20'}
                  `}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Local search */}
            <input
              type="text"
              placeholder="Search clause text..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="px-3 py-1.5 w-full sm:w-48 text-xs rounded-lg bg-[#090D16] border border-white/10 text-white placeholder:text-slate-500 outline-none focus:border-blue-500 transition-all"
            />
          </div>

          {/* List display */}
          <div className="space-y-3">
            {filteredClauses.length === 0 ? (
              <Card className="text-center py-12">
                <FileText className="w-12 h-12 text-slate-500 mx-auto mb-2" />
                <p className="text-xs text-slate-400 font-medium">No matching clauses found with active filters.</p>
              </Card>
            ) : (
              filteredClauses.map((clause) => {
                const isSelected = selectedClause?.id === clause.id;
                return (
                  <div
                    key={clause.id}
                    onClick={() => setSelectedClause(clause)}
                    className={`
                      p-4 rounded-xl border transition-all duration-150 cursor-pointer flex flex-col gap-2.5
                      ${isSelected 
                        ? 'bg-[#141C30] border-blue-500/60 shadow-glow-blue ring-1 ring-blue-500/40' 
                        : 'bg-[#0D1322]/80 border-white/[0.06] hover:border-white/20 hover:bg-[#141C30]/50'}
                    `}
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider">
                          Clause §{clause.clause_index + 1}
                        </span>
                        {clause.risk_type && clause.risk_type !== 'none' && (
                          <span className="px-2 py-0.5 rounded text-[9px] font-mono uppercase bg-white/10 text-slate-300 border border-white/10">
                            {clause.risk_type}
                          </span>
                        )}
                      </div>
                      <RiskBadge score={clause.risk_score} riskType={clause.risk_type} />
                    </div>

                    <p className="text-slate-300 text-xs font-normal line-clamp-3 leading-relaxed">
                      {clause.raw_text}
                    </p>

                    {clause.summary && (
                      <div className="text-[11px] text-slate-400 bg-[#090D16]/60 p-2 rounded-lg border border-white/[0.04] italic">
                        <span className="text-blue-400 not-italic font-semibold font-mono">Risk Summary: </span> 
                        {clause.summary}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right column: AI Redline Negotiation Copilot (5 cols) */}
        <div className="lg:col-span-5">
          {selectedClause ? (
            <div className="rounded-2xl border border-white/[0.08] bg-[#0D1322]/95 backdrop-blur-xl p-5 shadow-glass-card sticky top-20 space-y-5 flex flex-col">
              
              {/* Heading */}
              <div className="border-b border-white/[0.08] pb-3 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-mono font-bold text-blue-400 uppercase tracking-widest flex items-center gap-1.5">
                    <Scale className="w-3.5 h-3.5 text-blue-400" /> AI Clause Inspector
                  </span>
                  <RiskBadge score={selectedClause.risk_score} riskType={selectedClause.risk_type} />
                </div>
                <h3 className="text-sm font-bold text-white tracking-tight">
                  Clause §{selectedClause.clause_index + 1} Risk Diagnostic
                </h3>
              </div>

              {/* Raw segment */}
              <div className="space-y-1.5">
                <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                  Ingested Clause Text
                </h4>
                <div className="bg-[#090D16] p-3.5 rounded-xl text-xs font-mono text-slate-300 leading-relaxed border border-white/[0.06] max-h-48 overflow-y-auto">
                  {selectedClause.raw_text}
                </div>
              </div>

              {/* AI summary */}
              {selectedClause.summary && (
                <div className="space-y-1.5">
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                    Risk Breakdown & Statutory Exposure
                  </h4>
                  <div className="p-3 rounded-xl bg-[#141C30]/80 border border-amber-500/20 text-xs text-amber-200 leading-relaxed font-sans">
                    {selectedClause.summary}
                  </div>
                </div>
              )}

              {/* Suggestions Panel */}
              <div className="space-y-3 pt-3 border-t border-white/[0.08] flex flex-col">
                <div className="flex justify-between items-center">
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-300 font-bold flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
                    AI Redline Counter-Proposal
                  </h4>
                  {selectedClause.suggestions.length > 0 && (
                    <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-500/30">
                      RAG Grounded
                    </span>
                  )}
                </div>

                <div>
                  {selectedClause.suggestions.length > 0 ? (
                    <div className="space-y-3">
                      {selectedClause.suggestions.map((s) => (
                        <div key={s.id} className="bg-[#141C30] border border-blue-500/30 rounded-xl p-4 text-xs font-sans text-slate-200 leading-relaxed space-y-3 shadow-glow-blue">
                          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 border-b border-white/[0.06] pb-2">
                            <span>Indian Contract Act §73 Aligned</span>
                            <button
                              onClick={() => handleCopySuggestion(s.suggestion_text, s.id)}
                              className="flex items-center gap-1 text-blue-400 hover:text-blue-300 cursor-pointer"
                            >
                              {copiedId === s.id ? (
                                <>
                                  <Check className="w-3 h-3 text-emerald-400" />
                                  <span className="text-emerald-400">Copied!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3" />
                                  <span>Copy Redline</span>
                                </>
                              )}
                            </button>
                          </div>
                          
                          <div className="whitespace-pre-wrap font-sans text-xs text-slate-200 bg-[#090D16]/70 p-3 rounded-lg border border-white/[0.06]">
                            {s.suggestion_text}
                          </div>
                          
                          <span className="text-[9px] font-mono text-slate-500 block">
                            Generated on {new Date(s.created_at).toLocaleString('en-IN')}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-6 border border-dashed border-white/10 rounded-xl bg-[#090D16]/50 flex flex-col items-center justify-center p-4">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 mb-2">
                        <Sparkles className="w-5 h-5 animate-pulse" />
                      </div>
                      <p className="text-xs text-slate-400 font-medium mb-4 max-w-xs">
                        Draft a market-standard counter-clause with Indian liability caps and statutory precedents.
                      </p>
                      <Button
                        onClick={handleGenerateSuggestion}
                        isLoading={generatingSuggest}
                        variant="primary"
                        size="sm"
                        className="shadow-glow-blue text-xs font-semibold"
                      >
                        {!generatingSuggest && <Sparkles className="w-3.5 h-3.5 mr-1" />}
                        Generate AI Redline
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-[#0D1322]/80 border border-white/[0.08] rounded-2xl p-8 text-center flex flex-col items-center justify-center h-[240px]">
              <FileText className="w-8 h-8 text-slate-500 mb-2" />
              <p className="text-xs text-slate-400 font-medium">Select any clause to inspect risk breakdown and generate AI redline proposals.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
export default ContractDetail;

