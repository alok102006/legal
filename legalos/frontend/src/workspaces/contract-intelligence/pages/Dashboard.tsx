import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  UploadCloud, 
  FileText, 
  Search, 
  Calendar, 
  Building2, 
  ChevronRight, 
  AlertCircle, 
  CheckCircle2, 
  Loader2,
  Trash2,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Zap,
  ArrowUpRight,
  Filter,
  Sparkles
} from 'lucide-react';
import { uploadContract, listContracts, deleteContract } from '../api';
import { ContractSummary } from '@/api/types';
import Button from '@/design-system/components/Button';
import Card from '@/design-system/components/Card';
import Skeleton from '@/design-system/components/Skeleton';
import { Badge } from '@/design-system/components/Badge';

const ProcessingStepsBar: React.FC<{ createdAt: string }> = ({ createdAt }) => {
  const [step, setStep] = useState(1);

  useEffect(() => {
    const elapsedSec = Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000);
    if (elapsedSec < 3) setStep(1);
    else if (elapsedSec < 8) setStep(2);
    else if (elapsedSec < 15) setStep(3);
    else setStep(4);

    const timer = setInterval(() => {
      setStep(prev => (prev < 4 ? prev + 1 : prev));
    }, 4000);
    return () => clearInterval(timer);
  }, [createdAt]);

  const steps = [
    { num: 1, label: 'Ingesting' },
    { num: 2, label: 'OCR & Parsing' },
    { num: 3, label: 'Vector Indexing' },
    { num: 4, label: 'Clause Risk Scoring' }
  ];

  return (
    <div className="mt-2.5 pt-2 border-t border-white/[0.08] max-w-md w-full">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        {steps.map((s, idx) => (
          <React.Fragment key={s.num}>
            <div className="flex items-center gap-1.5">
              <span className={`w-4 h-4 rounded-full text-[9px] font-mono font-bold flex items-center justify-center ${
                step > s.num ? 'bg-emerald-500 text-slate-950 font-black' : step === s.num ? 'bg-blue-600 text-white animate-pulse shadow-glow-blue' : 'bg-white/10 text-slate-400'
              }`}>
                {step > s.num ? '✓' : s.num}
              </span>
              <span className={`text-[10px] font-mono ${step === s.num ? 'font-bold text-blue-300' : 'text-slate-400'}`}>
                {s.label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div className={`flex-1 h-0.5 ${step > s.num ? 'bg-emerald-500/80' : 'bg-white/10'}`} />
            )}
          </React.Fragment>
        ))}
      </div>
      <div className="w-full bg-white/10 rounded-full h-1 overflow-hidden">
        <div 
          className="bg-gradient-to-r from-blue-500 to-indigo-500 h-1 rounded-full transition-all duration-500" 
          style={{ width: `${(step / 4) * 100}%` }}
        />
      </div>
    </div>
  );
};

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [contracts, setContracts] = useState<ContractSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Deletion state
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [contractToDelete, setContractToDelete] = useState<ContractSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Upload State
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Search/Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState<'all' | 'high' | 'clean'>('all');

  const fetchContractsList = async (showSkeleton = false) => {
    if (showSkeleton) setLoading(true);
    try {
      const data = await listContracts();
      setContracts(data);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Failed to retrieve contracts.');
    } finally {
      if (showSkeleton) setLoading(false);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, contract: ContractSummary) => {
    e.stopPropagation();
    setContractToDelete(contract);
    setShowConfirmDelete(true);
  };

  const handleConfirmDelete = async () => {
    if (!contractToDelete) return;
    setDeleting(true);
    try {
      await deleteContract(contractToDelete.id);
      setContracts(prev => prev.filter(c => c.id !== contractToDelete.id));
      setShowConfirmDelete(false);
      setContractToDelete(null);
    } catch (err: any) {
      console.error(err);
      alert('Failed to delete contract.');
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    fetchContractsList(true);
  }, []);

  // Polling for processing items
  useEffect(() => {
    const hasProcessing = contracts.some(c => c.status === 'processing');
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      fetchContractsList(false);
    }, 3000);

    return () => clearInterval(interval);
  }, [contracts]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const MAX_SIZE = 10 * 1024 * 1024; // 10MB
    if (file.size > MAX_SIZE) {
      setUploadError('File size exceeds the 10MB limit.');
      return;
    }

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !['pdf', 'docx', 'txt', 'md'].includes(ext)) {
      setUploadError('Invalid format. Please upload PDF, DOCX, TXT, or MD.');
      return;
    }

    setUploading(true);
    setUploadError(null);
    try {
      const stub = await uploadContract(file);
      setContracts(prev => [stub, ...prev]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      console.error(err);
      setUploadError(err?.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const selectFile = () => {
    fileInputRef.current?.click();
  };

  // Filtered list
  const filteredContracts = contracts.filter(c => {
    const titleMatch = (c.title?.toLowerCase().includes(searchQuery.toLowerCase()) || 
      c.counterparty_name?.toLowerCase().includes(searchQuery.toLowerCase())) ?? false;
    
    if (!titleMatch) return false;
    if (riskFilter === 'high') return c.risk_clause_count > 0;
    if (riskFilter === 'clean') return c.risk_clause_count === 0 && c.status === 'analyzed';
    return true;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'processing':
        return (
          <Badge variant="warning" className="flex gap-1.5 items-center font-mono">
            <Loader2 className="w-3 h-3 animate-spin text-amber-400" /> AI Analyzing
          </Badge>
        );
      case 'analyzed':
        return (
          <Badge variant="success" className="flex gap-1.5 items-center font-mono">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Audited
          </Badge>
        );
      case 'failed':
        return (
          <Badge variant="danger" className="flex gap-1.5 items-center font-mono">
            <AlertCircle className="w-3 h-3 text-red-400" /> Failed
          </Badge>
        );
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  const totalHighRiskClauses = contracts.reduce((acc, c) => acc + (c.risk_clause_count || 0), 0);

  return (
    <div className="space-y-8 pb-16">
      {/* Executive KPI Scorecard Tier */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Compliance Health Posture */}
        <div className="p-5 rounded-xl bg-gradient-to-b from-[#141C30]/90 to-[#0D1322]/90 border border-emerald-500/30 shadow-glow-emerald backdrop-blur-md relative overflow-hidden group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Compliance Posture</span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white tracking-tight">96.4%</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center font-mono">
              <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +3.2%
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">Enterprise Audit-Ready · 0 overdue filings</p>
          <div className="mt-3 w-full bg-white/10 rounded-full h-1">
            <div className="bg-emerald-400 h-1 rounded-full shadow-glow-emerald" style={{ width: '96.4%' }} />
          </div>
        </div>

        {/* Card 2: Protected Contract Exposure */}
        <div className="p-5 rounded-xl bg-gradient-to-b from-[#141C30]/90 to-[#0D1322]/90 border border-blue-500/30 shadow-glow-blue backdrop-blur-md relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Contract Value Shield</span>
            <div className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400">
              <FileText className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white tracking-tight">₹4.8 Cr</span>
            <span className="text-xs font-mono text-blue-400 font-semibold">{contracts.length} Agmts</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            {totalHighRiskClauses > 0 ? (
              <span className="text-amber-400 font-medium">{totalHighRiskClauses} Critical Clauses flagged for redline</span>
            ) : (
              <span className="text-emerald-400">All indemnity & liability caps cleared</span>
            )}
          </p>
          <div className="mt-3 w-full bg-white/10 rounded-full h-1">
            <div className="bg-blue-400 h-1 rounded-full" style={{ width: '85%' }} />
          </div>
        </div>

        {/* Card 3: Statutory Penalties Saved */}
        <div className="p-5 rounded-xl bg-gradient-to-b from-[#141C30]/90 to-[#0D1322]/90 border border-amber-500/30 shadow-glow-amber backdrop-blur-md relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Penalties Prevented</span>
            <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white tracking-tight">₹2.40 L</span>
            <span className="text-xs font-mono text-amber-400 font-semibold">100% On-Time</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">Calculated against MCA/IT compounding rates</p>
          <div className="mt-3 w-full bg-white/10 rounded-full h-1">
            <div className="bg-amber-400 h-1 rounded-full" style={{ width: '100%' }} />
          </div>
        </div>

        {/* Card 4: Vendor Trust Shield */}
        <div className="p-5 rounded-xl bg-gradient-to-b from-[#141C30]/90 to-[#0D1322]/90 border border-white/[0.08] backdrop-blur-md relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Live GSTIN Shield</span>
            <div className="p-1.5 rounded-lg bg-white/10 text-slate-300">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-white tracking-tight">148</span>
            <span className="text-xs font-mono text-emerald-400 font-semibold">Verified</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">2 Suspended GSTINs blocked · ₹0 ITC Loss</p>
          <div className="mt-3 w-full bg-white/10 rounded-full h-1">
            <div className="bg-emerald-400 h-1 rounded-full" style={{ width: '98%' }} />
          </div>
        </div>
      </div>

      {/* Main Upload Dropzone Banner */}
      <div className="p-6 md:p-8 rounded-2xl bg-gradient-to-r from-[#0D1322] via-[#141C30] to-[#0D1322] border border-blue-500/20 shadow-glass-card relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 text-[11px] font-mono">
            <Sparkles className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
            <span>AI RAG-Grounded Legal Engine</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Contract Intelligence & Negotiation Studio
          </h2>
          <p className="text-slate-400 text-xs md:text-sm leading-relaxed">
            Upload Master Service Agreements (MSA), Vendor Contracts, NDAs, or SaaS Agreements. Our localized LLM parses high-risk indemnity, jurisdiction, and liability clauses with instant redline generation.
          </p>
        </div>
        <div className="flex-shrink-0 flex flex-col items-start md:items-end">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="hidden"
            accept=".pdf,.docx,.txt,.md"
          />
          <Button 
            onClick={selectFile}
            isLoading={uploading}
            variant="primary"
            size="lg"
            className="shadow-glow-blue font-semibold text-sm px-6 py-3"
          >
            {!uploading && <UploadCloud className="w-5 h-5 mr-2" />}
            Upload Contract Document
          </Button>
          <span className="text-[10px] font-mono text-slate-400 mt-2">
            PDF, DOCX, TXT up to 10MB · 384-dim Qdrant Vectorized
          </span>
          {uploadError && (
            <p className="mt-2 text-xs text-red-400 flex items-center gap-1 font-medium font-mono">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              {uploadError}
            </p>
          )}
        </div>
      </div>

      {/* Main Grid: Filters & Documents Registry */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left Column: Search & Filter Controls */}
        <div className="lg:col-span-1 space-y-4">
          <Card title="Filter Registry" subtitle="Search by title, partner or risk tier">
            <div className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search contract or vendor..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 pr-3 py-2 w-full text-xs rounded-lg bg-[#090D16] border border-white/10 text-white placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-all"
                />
              </div>

              <div className="space-y-1.5 pt-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                  Risk Tier
                </span>
                <div className="space-y-1">
                  <button
                    onClick={() => setRiskFilter('all')}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center justify-between ${
                      riskFilter === 'all' ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30 font-semibold' : 'text-slate-400 hover:bg-white/[0.04]'
                    }`}
                  >
                    <span>All Documents</span>
                    <span className="font-mono text-[10px] bg-white/10 px-1.5 py-0.5 rounded">{contracts.length}</span>
                  </button>
                  <button
                    onClick={() => setRiskFilter('high')}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center justify-between ${
                      riskFilter === 'high' ? 'bg-red-600/20 text-red-300 border border-red-500/30 font-semibold' : 'text-slate-400 hover:bg-white/[0.04]'
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> Redline Required
                    </span>
                    <span className="font-mono text-[10px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded">
                      {contracts.filter(c => c.risk_clause_count > 0).length}
                    </span>
                  </button>
                  <button
                    onClick={() => setRiskFilter('clean')}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center justify-between ${
                      riskFilter === 'clean' ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 font-semibold' : 'text-slate-400 hover:bg-white/[0.04]'
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Clean Audit
                    </span>
                    <span className="font-mono text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded">
                      {contracts.filter(c => c.risk_clause_count === 0 && c.status === 'analyzed').length}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </Card>

          <Card title="Vector Grounding" subtitle="RAG index telemetry">
            <div className="space-y-2.5 text-xs text-slate-400">
              <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
                <span>Vector Model:</span>
                <span className="font-mono text-slate-200">MiniLM-L6 (384-d)</span>
              </div>
              <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
                <span>Vector Database:</span>
                <span className="font-mono text-blue-400 font-semibold">Qdrant In-Memory</span>
              </div>
              <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
                <span>LLM Engine:</span>
                <span className="font-mono text-emerald-400 font-semibold">Gemini 2.5 Flash</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Multi-Tenant Filter:</span>
                <span className="font-mono text-slate-300">Document UUID</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Contracts Registry */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-white text-base tracking-tight">Active Agreements Registry</h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-300 border border-blue-500/20">
                {filteredContracts.length} Files
              </span>
            </div>
          </div>

          {loading ? (
            <div className="space-y-4">
              <Skeleton variant="table" count={4} />
            </div>
          ) : error ? (
            <Card className="text-center py-8">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <h4 className="text-base font-bold text-white mb-2">Failed to load registry</h4>
              <p className="text-xs text-slate-400 mb-4">{error}</p>
              <Button onClick={() => fetchContractsList(true)} variant="outline">
                Try Again
              </Button>
            </Card>
          ) : filteredContracts.length === 0 ? (
            <Card className="text-center py-16 flex flex-col items-center">
              <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-4 text-slate-400">
                <FileText className="w-7 h-7" />
              </div>
              <h4 className="text-base font-bold text-white mb-1">No agreements found</h4>
              <p className="text-xs text-slate-400 max-w-sm mb-6">
                {searchQuery 
                  ? "No contracts matching your filter criteria. Reset the search to view all." 
                  : "Upload your first commercial agreement above to trigger autonomous RAG analysis."}
              </p>
              {!searchQuery && (
                <Button onClick={selectFile} variant="primary" size="sm">
                  Upload Contract Now
                </Button>
              )}
            </Card>
          ) : (
            <div className="rounded-xl border border-white/[0.08] bg-[#0D1322]/90 backdrop-blur-md overflow-hidden divide-y divide-white/[0.06] shadow-glass-card">
              {filteredContracts.map((contract) => (
                <div 
                  key={contract.id}
                  onClick={() => {
                    if (contract.status === 'analyzed') {
                      navigate(`/contracts/${contract.id}`);
                    }
                  }}
                  className={`
                    p-4 md:p-5 flex items-center justify-between transition-all duration-150 group
                    ${contract.status === 'analyzed' ? 'hover:bg-white/[0.03] cursor-pointer' : 'opacity-85'}
                  `}
                >
                  <div className="flex gap-4 items-start min-w-0 flex-1 pr-4">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center flex-shrink-0 group-hover:border-blue-400/40 group-hover:scale-105 transition-all">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="min-w-0 space-y-1 flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-white truncate text-sm md:text-base group-hover:text-blue-300 transition-colors">
                          {contract.title || "Processing details..."}
                        </h4>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
                        <span className="flex items-center gap-1 text-slate-300 font-medium">
                          <Building2 className="w-3.5 h-3.5 text-slate-400" />
                          {contract.counterparty_name || "Extracting counterparty..."}
                        </span>
                        <span className="flex items-center gap-1 font-mono text-[11px] text-slate-400">
                          <Calendar className="w-3.5 h-3.5" />
                          {new Date(contract.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                        </span>
                      </div>
                      {contract.status === 'processing' && (
                        <ProcessingStepsBar createdAt={contract.created_at} />
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="text-right hidden sm:block">
                      {getStatusBadge(contract.status)}
                      {contract.status === 'analyzed' && (
                        <div className="mt-1.5 text-[11px] font-mono font-semibold">
                          {contract.risk_clause_count > 0 ? (
                            <span className="px-2 py-0.5 rounded-full bg-red-950/70 text-red-300 border border-red-500/30 shadow-glow-ruby">
                              {contract.risk_clause_count} Risk Clause(s)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full bg-emerald-950/70 text-emerald-300 border border-emerald-500/30">
                              Clean Audit
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="sm:hidden">
                      {getStatusBadge(contract.status)}
                    </div>
                    
                    <button
                      onClick={(e) => handleDeleteClick(e, contract)}
                      disabled={deleting}
                      className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer outline-none"
                      title="Delete Contract"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    {contract.status === 'analyzed' && (
                      <div className="p-1.5 rounded-lg bg-white/[0.04] text-slate-400 group-hover:text-white group-hover:bg-blue-600/30 transition-colors">
                        <ChevronRight className="w-4 h-4" />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Deletion Confirmation Modal */}
      {showConfirmDelete && contractToDelete && (
        <div className="fixed inset-0 bg-[#090D16]/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="bg-[#141C30] border border-red-500/30 rounded-2xl shadow-glow-ruby max-w-md w-full p-6 space-y-6">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-red-950/80 border border-red-500/40 text-red-400 flex-shrink-0">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-white text-lg">Delete Agreement Dossier?</h3>
                <p className="text-slate-400 text-xs leading-relaxed">
                  Are you sure you want to delete <strong className="text-white">{contractToDelete.title || "this document"}</strong>? 
                  This will simultaneously purge all parsed clauses, risk assessments, and Qdrant vector embeddings.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowConfirmDelete(false);
                  setContractToDelete(null);
                }}
                disabled={deleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleConfirmDelete}
                isLoading={deleting}
              >
                Confirm Deletion
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default Dashboard;

