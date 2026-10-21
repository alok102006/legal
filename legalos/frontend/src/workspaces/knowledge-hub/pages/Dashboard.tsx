import React, { useState, useEffect, useRef } from 'react';
import { 
  Building2, 
  Search, 
  Plus, 
  CheckCircle2, 
  AlertTriangle, 
  Sparkles, 
  FileText, 
  Send, 
  MapPin, 
  ShieldCheck, 
  Calendar, 
  Tag, 
  Copy, 
  Check, 
  Trash2, 
  BookOpen, 
  Loader2, 
  UploadCloud,
  FileSpreadsheet,
  FileCode,
  FileCheck,
  File,
  Layers,
  RefreshCw,
  Bot,
  User,
  Shield,
  AlertCircle,
  CheckCircle,
  Lightbulb,
  X,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { 
  RegisteredCompany, 
  CompanyProfilePreview, 
  GroundTruthExcerpt,
  RiskAnalysis,
  previewCompanyGstin, 
  registerCompany, 
  getRegisteredCompanies, 
  deleteRegisteredCompany, 
  uploadCompanyDocumentFile, 
  deleteCompanyDocument,
  askKnowledgeAI 
} from '@/api/knowledge';

// Helper component for rich, readable markdown chat formatting
const FormattedChatMessage: React.FC<{ content: string }> = ({ content }) => {
  const blocks = content.split(/\n\n+/);

  return (
    <div className="space-y-2.5 font-sans leading-relaxed text-xs text-slate-800">
      {blocks.map((block, bIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        // Code block
        if (trimmed.startsWith('```')) {
          const lines = trimmed.split('\n');
          const lang = lines[0].replace('```', '').trim() || 'text';
          const codeText = lines.slice(1, lines[lines.length - 1]?.startsWith('```') ? -1 : undefined).join('\n');
          return (
            <div key={bIdx} className="my-2 rounded-lg bg-slate-900 text-slate-100 p-3 font-mono text-[11px] overflow-x-auto border border-slate-800 shadow-inner relative">
              {lang && (
                <span className="absolute top-2 right-2 text-[9px] uppercase font-bold text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                  {lang}
                </span>
              )}
              <pre className="whitespace-pre">{codeText || trimmed.replace(/```[a-z]*/g, '')}</pre>
            </div>
          );
        }

        // Headings
        if (trimmed.startsWith('### ')) {
          return <h4 key={bIdx} className="font-bold text-sm text-slate-900 mt-2 mb-1">{formatInline(trimmed.replace(/^###\s+/, ''))}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={bIdx} className="font-bold text-base text-slate-900 mt-3 mb-1">{formatInline(trimmed.replace(/^##\s+/, ''))}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={bIdx} className="font-bold text-lg text-slate-900 mt-3 mb-1">{formatInline(trimmed.replace(/^#\s+/, ''))}</h2>;
        }

        // Bullet Lists
        const lines = trimmed.split('\n');
        const isBulletList = lines.every(l => /^\s*[-*•]\s+/.test(l));
        const isNumberedList = lines.every(l => /^\s*\d+\.\s+/.test(l));

        if (isBulletList) {
          return (
            <ul key={bIdx} className="list-disc list-inside space-y-1 pl-1 text-slate-700">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>
                  {formatInline(l.replace(/^\s*[-*•]\s+/, ''))}
                </li>
              ))}
            </ul>
          );
        }

        if (isNumberedList) {
          return (
            <ol key={bIdx} className="list-decimal list-inside space-y-1 pl-1 text-slate-700">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>
                  {formatInline(l.replace(/^\s*\d+\.\s+/, ''))}
                </li>
              ))}
            </ol>
          );
        }

        // Paragraph
        return (
          <p key={bIdx} className="text-slate-700 leading-relaxed">
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {lIdx > 0 && <br />}
                {formatInline(line)}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
};

function formatInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={idx} className="italic text-slate-800">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={idx} className="font-mono text-[11px] bg-slate-200/80 text-indigo-900 px-1.5 py-0.5 rounded border border-slate-300/50">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}


// ---------------------------------------------------------------------------
// Risk Score Gauge (SVG, no library needed)
// ---------------------------------------------------------------------------
const RiskGauge: React.FC<{ score: number }> = ({ score }) => {
  const r = 54;
  const circumference = Math.PI * r; // half circle
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 70 ? '#ef4444' : score >= 40 ? '#f59e0b' : '#22c55e';
  const label = score >= 70 ? 'High Risk' : score >= 40 ? 'Medium Risk' : 'Low Risk';

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="128" height="80" viewBox="0 0 128 80">
        {/* Track */}
        <path d="M 10,64 A 54,54 0 0,1 118,64" fill="none" stroke="#e2e8f0" strokeWidth="12" strokeLinecap="round" />
        {/* Fill */}
        <path
          d="M 10,64 A 54,54 0 0,1 118,64"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1.2s ease-out' }}
        />
        <text x="64" y="58" textAnchor="middle" fontSize="22" fontWeight="bold" fill={color}>{score}</text>
        <text x="64" y="72" textAnchor="middle" fontSize="9" fill="#94a3b8">/ 100</text>
      </svg>
      <span className="text-xs font-bold" style={{ color }}>{label}</span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Risk Radar Modal
// ---------------------------------------------------------------------------
const RiskRadarModal: React.FC<{ risk: RiskAnalysis; docTitle: string; onClose: () => void }> = ({ risk, docTitle, onClose }) => {
  const [openSection, setOpenSection] = useState<string | null>('critical');
  const toggle = (s: string) => setOpenSection(prev => prev === s ? null : s);

  const SectionHeader: React.FC<{ id: string; label: string; count: number; color: string; icon: React.ReactNode }> = ({ id, label, count, color, icon }) => (
    <button
      onClick={() => toggle(id)}
      className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer ${openSection === id ? `${color} shadow-sm` : 'bg-slate-50 border-slate-200 hover:bg-slate-100'}`}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm font-bold text-slate-800">{label}</span>
        <span className="text-[10px] font-bold bg-white/70 text-slate-700 px-2 py-0.5 rounded-full">{count}</span>
      </div>
      {openSection === id ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
    </button>
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="sticky top-0 bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between z-10 rounded-t-2xl">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-rose-500 to-orange-500 text-white rounded-xl shadow-md">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">AI Risk & Compliance Radar</h3>
              <p className="text-[11px] text-slate-500 truncate max-w-xs">{docTitle}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Score + Classification */}
          <div className="flex flex-col sm:flex-row items-center gap-6 p-5 bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl border border-slate-200">
            <RiskGauge score={risk.risk_score} />
            <div className="flex-1 space-y-2">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Document Classification</span>
                <span className="inline-flex items-center gap-1.5 mt-1 px-3 py-1.5 bg-indigo-100 text-indigo-800 text-sm font-bold rounded-xl border border-indigo-200">
                  <Tag className="w-3.5 h-3.5" />
                  {risk.classification}
                </span>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                This document was automatically classified and scanned for legal risks, compliance gaps, and protective clauses using LegalOS AI.
              </p>
            </div>
          </div>

          {/* Critical Clauses */}
          <div className="space-y-2">
            <SectionHeader id="critical" label="Critical Clauses" count={risk.critical_clauses.length} color="bg-rose-50 border-rose-200" icon={<AlertCircle className="w-4 h-4 text-rose-600" />} />
            {openSection === 'critical' && (
              <div className="space-y-2 pl-2">
                {risk.critical_clauses.length === 0
                  ? <p className="text-xs text-slate-500 pl-3">No critical clauses detected.</p>
                  : risk.critical_clauses.map((c, i) => (
                    <div key={i} className="p-3 bg-rose-50 border border-rose-200 rounded-xl">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase ${c.severity === 'HIGH' ? 'bg-rose-600 text-white' : 'bg-amber-500 text-white'}`}>{c.severity}</span>
                        <span className="text-xs font-bold text-slate-800">{c.clause}</span>
                      </div>
                      <p className="text-[11px] text-rose-700 leading-relaxed">{c.reason}</p>
                    </div>
                  ))
                }
              </div>
            )}
          </div>

          {/* Compliance Gaps */}
          <div className="space-y-2">
            <SectionHeader id="gaps" label="Compliance Gaps" count={risk.compliance_gaps.length} color="bg-amber-50 border-amber-200" icon={<AlertTriangle className="w-4 h-4 text-amber-600" />} />
            {openSection === 'gaps' && (
              <div className="space-y-2 pl-2">
                {risk.compliance_gaps.length === 0
                  ? <p className="text-xs text-slate-500 pl-3">No compliance gaps detected.</p>
                  : risk.compliance_gaps.map((g, i) => (
                    <div key={i} className="p-3 bg-amber-50 border border-amber-200 rounded-xl">
                      <span className="text-xs font-bold text-amber-800 block mb-0.5">{g.gap}</span>
                      <p className="text-[11px] text-amber-700 leading-relaxed">{g.detail}</p>
                    </div>
                  ))
                }
              </div>
            )}
          </div>

          {/* Strengths */}
          <div className="space-y-2">
            <SectionHeader id="strengths" label="Strengths" count={risk.strengths.length} color="bg-emerald-50 border-emerald-200" icon={<CheckCircle className="w-4 h-4 text-emerald-600" />} />
            {openSection === 'strengths' && (
              <div className="space-y-2 pl-2">
                {risk.strengths.length === 0
                  ? <p className="text-xs text-slate-500 pl-3">No strengths identified.</p>
                  : risk.strengths.map((s, i) => (
                    <div key={i} className="flex items-start gap-2 p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />
                      <p className="text-[11px] text-emerald-800 leading-relaxed">{s}</p>
                    </div>
                  ))
                }
              </div>
            )}
          </div>

          {/* Suggested Fixes */}
          {risk.suggested_fixes.length > 0 && (
            <div className="space-y-2">
              <SectionHeader id="fixes" label="Suggested Fixes" count={risk.suggested_fixes.length} color="bg-indigo-50 border-indigo-200" icon={<Lightbulb className="w-4 h-4 text-indigo-600" />} />
              {openSection === 'fixes' && (
                <div className="space-y-2 pl-2">
                  {risk.suggested_fixes.map((f, i) => (
                    <div key={i} className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl">
                      <span className="text-xs font-bold text-indigo-800 block mb-1">Re: {f.issue}</span>
                      <p className="text-[11px] text-indigo-700 leading-relaxed italic">"{f.fix}"</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};


export const KnowledgeDashboard: React.FC = () => {
  const [companies, setCompanies] = useState<RegisteredCompany[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Registration Modal State
  const [showModal, setShowModal] = useState<boolean>(false);
  const [gstinInput, setGstinInput] = useState<string>('27AAPCA1234B1ZV');
  const [previewing, setPreviewing] = useState<boolean>(false);
  const [registering, setRegistering] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<CompanyProfilePreview | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);

  // Document File Upload Modal State
  const [showDocModal, setShowDocModal] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState<string>('');
  const [docCategory, setDocCategory] = useState<string>('Corporate Policy');
  const [uploadingDoc, setUploadingDoc] = useState<boolean>(false);
  const [docUploadError, setDocUploadError] = useState<string | null>(null);
  const [analysing, setAnalysing] = useState<boolean>(false); // Risk analysis in progress
  
  // Document Deletion State
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);

  // Risk Radar Modal State
  const [riskModalDoc, setRiskModalDoc] = useState<{ risk: RiskAnalysis; title: string } | null>(null);

  // AI Q&A Chat State
  const [question, setQuestion] = useState<string>('');
  const [asking, setAsking] = useState<boolean>(false);
  const [selectedDocScope, setSelectedDocScope] = useState<string>('all');
  const [docSearchQuery, setDocSearchQuery] = useState<string>('');
  const [docTypeFilter, setDocTypeFilter] = useState<'ALL' | 'PDF' | 'DOCX' | 'CSV' | 'EXCEL'>('ALL');
  const [chatHistory, setChatHistory] = useState<Array<{
    sender: 'user' | 'ai';
    text: string;
    sources?: string[];
    excerpts?: GroundTruthExcerpt[];
    timestamp?: string;
  }>>([]); 
  const [copiedMsgIdx, setCopiedMsgIdx] = useState<number | null>(null);

  const [copied, setCopied] = useState<boolean>(false);
  const chatEndRef = useRef<HTMLDivElement>(null);


  useEffect(() => {
    fetchCompanies();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, asking]);

  const fetchCompanies = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getRegisteredCompanies();
      setCompanies(data);
      if (data.length > 0 && !selectedCompanyId) {
        setSelectedCompanyId(data[0].id);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load registered companies.');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    const cleanGstin = gstinInput.trim().toUpperCase();
    if (cleanGstin.length !== 15) {
      setModalError('GSTIN must be exactly 15 characters.');
      return;
    }
    try {
      setPreviewing(true);
      setModalError(null);
      const data = await previewCompanyGstin(cleanGstin);
      setPreviewData(data);
    } catch (err: any) {
      setModalError(err?.response?.data?.detail || 'Failed to fetch GSTIN profile from Sandbox API.');
    } finally {
      setPreviewing(false);
    }
  };

  const handleRegister = async () => {
    const cleanGstin = gstinInput.trim().toUpperCase();
    if (cleanGstin.length !== 15) {
      setModalError('GSTIN must be exactly 15 characters.');
      return;
    }
    try {
      setRegistering(true);
      setModalError(null);
      const newComp = await registerCompany(cleanGstin);
      await fetchCompanies();
      setSelectedCompanyId(newComp.id);
      setShowModal(false);
      setPreviewData(null);
      setGstinInput('');
    } catch (err: any) {
      setModalError(err?.response?.data?.detail || 'Failed to register company.');
    } finally {
      setRegistering(false);
    }
  };

  const handleDeleteCompany = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to unregister ${name}?\n\nThis will remove all associated documents, storage files, and vector embeddings.`)) return;
    try {
      await deleteRegisteredCompany(id);
      const updated = companies.filter(c => c.id !== id);
      setCompanies(updated);
      if (selectedCompanyId === id) {
        setSelectedCompanyId(updated.length > 0 ? updated[0].id : null);
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to delete company.');
    }
  };

  const handleDeleteDocument = async (docId: string, docTitle: string) => {
    if (!window.confirm(`Are you sure you want to delete "${docTitle}"?\n\nThis will permanently delete the document from physical storage, database, and Qdrant vector index.`)) {
      return;
    }
    try {
      setDeletingDocId(docId);
      await deleteCompanyDocument(docId);
      await fetchCompanies();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to delete document from everywhere.');
    } finally {
      setDeletingDocId(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
      setDocTitle(nameWithoutExt);
      setDocUploadError(null);
    }
  };

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompanyId || !selectedFile) {
      setDocUploadError('Please select a file to upload.');
      return;
    }
    try {
      setUploadingDoc(true);
      setDocUploadError(null);
      await uploadCompanyDocumentFile(
        selectedCompanyId,
        selectedFile,
        docTitle.trim() || selectedFile.name,
        docCategory
      );
      setUploadingDoc(false);
      setAnalysing(true); // show analysis spinner after upload
      await fetchCompanies();
      setAnalysing(false);
      setShowDocModal(false);
      setSelectedFile(null);
      setDocTitle('');
    } catch (err: any) {
      setDocUploadError(err?.response?.data?.detail || 'Failed to parse and upload document.');
    } finally {
      setUploadingDoc(false);
      setAnalysing(false);
    }
  };

  const handleAskAI = async (promptText?: string) => {
    const q = promptText || question;
    if (!q.trim() || asking) return;

    const userMsg = q.trim();
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    setQuestion('');
    setChatHistory(prev => [...prev, { sender: 'user', text: userMsg, timestamp: timeStr }]);
    
    try {
      setAsking(true);
      const docScopeId = selectedDocScope !== 'all' ? selectedDocScope : undefined;
      const res = await askKnowledgeAI(userMsg, selectedCompanyId || undefined, docScopeId);
      setChatHistory(prev => [
        ...prev, 
        { 
          sender: 'ai', 
          text: res.answer, 
          sources: res.sources, 
          excerpts: res.ground_truth_excerpts,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } catch (err: any) {
      setChatHistory(prev => [
        ...prev, 
        { 
          sender: 'ai', 
          text: 'Apologies, unable to answer your query right now. Please try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setAsking(false);
    }
  };

  const copyMessageText = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgIdx(idx);
    setTimeout(() => setCopiedMsgIdx(null), 2000);
  };

  const selectedCompany = companies.find(c => c.id === selectedCompanyId);

  const filteredDocs = (selectedCompany?.documents || []).filter(d => {
    const q = docSearchQuery.trim().toLowerCase();
    const matchesSearch = !q ||
      d.title.toLowerCase().includes(q) ||
      (d.file_name && d.file_name.toLowerCase().includes(q)) ||
      (d.summary && d.summary.toLowerCase().includes(q));
    const matchesType = docTypeFilter === 'ALL' || d.file_type?.toUpperCase() === docTypeFilter;
    return matchesSearch && matchesType;
  });
  const copyGstin = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getFileIcon = (fileType?: string) => {
    const t = fileType?.toUpperCase() || '';
    if (t === 'CSV' || t === 'EXCEL' || t === 'XLSX' || t === 'XLS') {
      return <FileSpreadsheet className="w-5 h-5 text-emerald-600" />;
    }
    if (t === 'PDF') {
      return <FileText className="w-5 h-5 text-rose-600" />;
    }
    if (t === 'DOCX' || t === 'DOC') {
      return <FileCheck className="w-5 h-5 text-blue-600" />;
    }
    return <File className="w-5 h-5 text-indigo-600" />;
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Top Banner Header */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-6 md:p-8 shadow-xl border border-slate-800 relative overflow-hidden">
        <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-3">
              <span className="p-2 bg-indigo-600/30 text-indigo-400 rounded-lg border border-indigo-500/30">
                <BookOpen className="w-6 h-6" />
              </span>
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
                Knowledge Hub & Ground Truth Vault
              </h1>
            </div>
            <p className="text-slate-300 text-sm mt-2 max-w-2xl">
              Register Indian corporate entities via 15-character GSTIN, upload ground truth documents (PDF, Word, CSV, Excel), and run AI Q&A strictly grounded in your files.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setShowModal(true);
                setPreviewData(null);
                setModalError(null);
              }}
              className="flex items-center gap-2 bg-gradient-to-r from-indigo-500 to-blue-600 hover:from-indigo-600 hover:to-blue-700 text-white px-5 py-2.5 rounded-xl font-semibold shadow-lg hover:shadow-indigo-500/25 transition-all text-sm cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Register Company via GSTIN</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Layout */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-slate-200 shadow-sm">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin mb-4" />
          <p className="text-slate-600 font-medium">Loading Knowledge Hub entities...</p>
        </div>
      ) : error ? (
        <div className="p-6 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl flex items-center gap-4">
          <AlertTriangle className="w-6 h-6 text-rose-600 flex-shrink-0" />
          <div>
            <h4 className="font-bold">Error Loading Knowledge Hub</h4>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      ) : companies.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-2xl p-12 text-center border border-dashed border-slate-300 shadow-sm max-w-2xl mx-auto">
          <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-indigo-100 shadow-sm">
            <Building2 className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-2">No Companies Registered Yet</h3>
          <p className="text-slate-500 text-sm mb-6 max-w-md mx-auto">
            Get started by entering your 15-character GSTIN. LegalOS will query the Sandbox API to profile your company status, jurisdiction, and address automatically.
          </p>
          <button
            onClick={() => {
              setShowModal(true);
              setPreviewData(null);
              setModalError(null);
            }}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-semibold shadow-md transition-all text-sm cursor-pointer"
          >
            <Plus className="w-5 h-5" />
            <span>Register First Company Now</span>
          </button>
        </div>
      ) : (
        /* Company Details + AI Hub View */
        <div className="space-y-8">
          {/* Company Switcher Tabs */}
          <div className="flex items-center gap-3 overflow-x-auto pb-2 scrollbar-none">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider whitespace-nowrap">Registered Entities:</span>
            {companies.map((comp) => {
              const isSelected = comp.id === selectedCompanyId;
              return (
                <button
                  key={comp.id}
                  onClick={() => setSelectedCompanyId(comp.id)}
                  className={`
                    flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all whitespace-nowrap cursor-pointer border
                    ${isSelected 
                      ? 'bg-slate-900 text-white border-slate-900 shadow-md scale-[1.02]' 
                      : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50'}
                  `}
                >
                  <Building2 className={`w-4 h-4 ${isSelected ? 'text-indigo-400' : 'text-slate-400'}`} />
                  <span>{comp.legal_name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${isSelected ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-500'}`}>
                    {comp.gstin.slice(0, 5)}...
                  </span>
                </button>
              );
            })}
          </div>

          {selectedCompany && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column: Detailed Company Profile + Vault (2 Cols) */}
              <div className="lg:col-span-2 space-y-6">
                {/* Hero Profile Card */}
                <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200 shadow-sm relative overflow-hidden">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-slate-100 pb-6">
                    <div>
                      <div className="flex items-center gap-3 flex-wrap">
                        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">{selectedCompany.legal_name}</h2>
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${selectedCompany.status.toLowerCase() === 'active' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}`}>
                          <span className={`w-2 h-2 rounded-full ${selectedCompany.status.toLowerCase() === 'active' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                          {selectedCompany.status} Taxpayer
                        </span>
                      </div>
                      {selectedCompany.trade_name && (
                        <p className="text-slate-500 text-sm mt-1">Trade Name: <span className="font-medium text-slate-700">{selectedCompany.trade_name}</span></p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDeleteCompany(selectedCompany.id, selectedCompany.legal_name)}
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                        title="Unregister Company & Delete All Documents"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>

                  {/* Badges Bar */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-6 border-b border-slate-100">
                    <div>
                      <span className="text-xs text-slate-400 font-semibold block uppercase">GSTIN Identifier</span>
                      <div className="flex items-center gap-1.5 mt-1 font-mono text-sm font-bold text-slate-800 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200 w-fit">
                        <span>{selectedCompany.gstin}</span>
                        <button onClick={() => copyGstin(selectedCompany.gstin)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                          {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 font-semibold block uppercase">Entity Constitution</span>
                      <span className="text-sm font-semibold text-slate-800 block mt-1">{selectedCompany.entity_type || 'Private Limited'}</span>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 font-semibold block uppercase">Registration Date</span>
                      <span className="text-sm font-semibold text-slate-800 block mt-1">{selectedCompany.registration_date || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 font-semibold block uppercase">Taxpayer Scheme</span>
                      <span className="text-sm font-semibold text-slate-800 block mt-1">{selectedCompany.taxpayer_type || 'Regular'}</span>
                    </div>
                  </div>

                  {/* Profile Details Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6">
                    {/* Jurisdiction Card */}
                    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                      <div className="flex items-center gap-2 mb-3 text-indigo-700 font-bold text-sm">
                        <ShieldCheck className="w-4 h-4" />
                        <span>Tax Jurisdiction & Offices</span>
                      </div>
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-slate-500">State Jurisdiction:</span>
                          <span className="font-semibold text-slate-800">{selectedCompany.state_jurisdiction || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Center Jurisdiction:</span>
                          <span className="font-semibold text-slate-800">{selectedCompany.center_jurisdiction || 'N/A'}</span>
                        </div>
                      </div>
                    </div>

                    {/* Address Card */}
                    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                      <div className="flex items-center gap-2 mb-3 text-indigo-700 font-bold text-sm">
                        <MapPin className="w-4 h-4" />
                        <span>Principal Place of Business</span>
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed font-medium">
                        {selectedCompany.principal_address?.formatted || 'Registered Business Address'}
                      </p>
                    </div>
                  </div>

                  {/* Nature of Business */}
                  {selectedCompany.nature_of_business && selectedCompany.nature_of_business.length > 0 && (
                    <div className="mt-6 pt-6 border-t border-slate-100">
                      <span className="text-xs text-slate-400 font-semibold block uppercase mb-2">Registered Business Activities</span>
                      <div className="flex flex-wrap gap-2">
                        {selectedCompany.nature_of_business.map((act, i) => (
                          <span key={i} className="inline-flex items-center gap-1 px-3 py-1 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-lg text-xs font-semibold">
                            <Tag className="w-3 h-3 text-indigo-500" />
                            {act}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Corporate Knowledge Vault (Ground Truth Document Uploader & Manager) */}
                <div className="bg-white rounded-2xl p-6 md:p-8 border border-slate-200 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-bold text-slate-900">Corporate Knowledge Vault</h3>
                        <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          {selectedCompany.documents.length} Ground Truth {selectedCompany.documents.length === 1 ? 'Doc' : 'Docs'} Active
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">Upload PDF, Word, CSV, or Excel files. AI Grounding extracts text and indexes it into Qdrant vector DB.</p>
                    </div>
                    <button
                      onClick={() => {
                        setShowDocModal(true);
                        setSelectedFile(null);
                        setDocTitle('');
                        setDocUploadError(null);
                      }}
                      className="inline-flex items-center gap-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2.5 rounded-xl transition-all shadow-md cursor-pointer"
                    >
                      <UploadCloud className="w-4 h-4" />
                      <span>Upload Ground Truth File</span>
                    </button>
                  </div>

                  {/* Analysis in progress banner */}
                  {analysing && (
                    <div className="mb-4 p-3 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center gap-3 animate-pulse">
                      <Loader2 className="w-4 h-4 text-indigo-600 animate-spin flex-shrink-0" />
                      <div>
                        <p className="text-xs font-bold text-indigo-800">🔍 AI Risk Radar Analysing Document...</p>
                        <p className="text-[10px] text-indigo-600">Scanning for critical clauses, compliance gaps, and contract strengths. This takes 5–10 seconds.</p>
                      </div>
                    </div>
                  )}

                  {/* Document Search & Filter Bar */}
                  {selectedCompany.documents.length > 0 && (
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                      <div className="relative flex-1">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          value={docSearchQuery}
                          onChange={(e) => setDocSearchQuery(e.target.value)}
                          placeholder="Search documents by title, file name or summary..."
                          className="w-full pl-9 pr-3 py-1.5 text-xs bg-white rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
                        />
                      </div>
                      <div className="flex items-center gap-1 overflow-x-auto">
                        {(['ALL', 'PDF', 'DOCX', 'CSV', 'EXCEL'] as const).map((ft) => (
                          <button
                            key={ft}
                            onClick={() => setDocTypeFilter(ft)}
                            className={`px-2.5 py-1 text-[10px] font-bold rounded-lg transition-all cursor-pointer ${
                              docTypeFilter === ft
                                ? 'bg-indigo-600 text-white shadow-xs'
                                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                            }`}
                          >
                            {ft}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {filteredDocs.length === 0 && selectedCompany.documents.length === 0 ? (
                    <div className="p-8 text-center bg-slate-50 rounded-xl border border-dashed border-slate-300 space-y-3">
                      <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto border border-indigo-100">
                        <UploadCloud className="w-6 h-6" />
                      </div>
                      <h4 className="text-sm font-bold text-slate-800">No Ground Truth Files Uploaded Yet</h4>
                      <p className="text-xs text-slate-500 max-w-sm mx-auto">
                        Upload employee policies, NDAs, tax filings, or financial spreadsheets (.pdf, .docx, .csv, .xlsx). The AI Assistant will use these files as strict facts to answer your queries.
                      </p>
                    </div>
                  ) : filteredDocs.length === 0 ? (
                    <div className="p-8 text-center bg-slate-50 rounded-xl border border-dashed border-slate-300 space-y-2">
                      <Search className="w-6 h-6 text-slate-400 mx-auto" />
                      <p className="text-xs font-semibold text-slate-700">No documents match your search or filter</p>
                      <button
                        onClick={() => { setDocSearchQuery(''); setDocTypeFilter('ALL'); }}
                        className="text-xs text-indigo-600 hover:underline cursor-pointer"
                      >
                        Reset filters
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {filteredDocs.map((doc) => {
                        const risk = doc.risk_analysis;
                        const riskColor = !risk ? '' : risk.risk_score >= 70
                          ? 'bg-rose-100 text-rose-700 border-rose-300'
                          : risk.risk_score >= 40
                          ? 'bg-amber-100 text-amber-700 border-amber-300'
                          : 'bg-emerald-100 text-emerald-700 border-emerald-300';
                        return (
                        <div key={doc.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-slate-50 transition-all flex items-start gap-3 relative group">
                          <div className="p-2.5 bg-white rounded-xl border border-slate-200 shadow-sm flex-shrink-0">
                            {getFileIcon(doc.file_type)}
                          </div>
                          <div className="flex-1 min-w-0 pr-7">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-[9px] uppercase font-bold tracking-wider text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100">
                                {doc.document_category}
                              </span>
                              {doc.file_type && (
                                <span className="text-[9px] uppercase font-mono font-bold text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">
                                  {doc.file_type}
                                </span>
                              )}
                              {/* Risk Score Badge */}
                              {risk && (
                                <button
                                  onClick={() => setRiskModalDoc({ risk, title: doc.title })}
                                  className={`inline-flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full border cursor-pointer hover:shadow-sm transition-all ${riskColor}`}
                                  title="View AI Risk Radar"
                                >
                                  <Shield className="w-2.5 h-2.5" />
                                  Risk: {risk.risk_score}
                                </button>
                              )}
                            </div>
                            <h4 className="text-sm font-bold text-slate-900 truncate mt-1">{doc.title}</h4>
                            {doc.file_name && (
                              <p className="text-[11px] font-mono text-slate-400 truncate">{doc.file_name}</p>
                            )}
                            {doc.summary && (
                              <p className="text-xs text-slate-600 line-clamp-2 mt-1 bg-white p-2 rounded border border-slate-200/60 leading-relaxed font-sans">
                                {doc.summary}
                              </p>
                            )}
                            {/* Risk classification tag */}
                            {risk?.classification && (
                              <span className="inline-flex items-center gap-1 mt-1.5 text-[9px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                                <Tag className="w-2.5 h-2.5" />
                                {risk.classification}
                              </span>
                            )}
                          </div>
                          
                          {/* Delete document button */}
                          <button
                            onClick={() => handleDeleteDocument(doc.id, doc.title)}
                            disabled={deletingDocId === doc.id}
                            className="absolute top-3.5 right-3.5 p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                            title="Delete Document completely from Disk, PostgreSQL & Qdrant"
                          >
                            {deletingDocId === doc.id ? (
                              <Loader2 className="w-4 h-4 text-rose-600 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: AI Q&A Assistant Ground Truth Panel (1 Col) */}
              <div className="lg:col-span-1">
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm sticky top-6 flex flex-col h-[700px]">
                  {/* Chat Header */}
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 bg-gradient-to-br from-indigo-600 to-blue-600 text-white rounded-xl shadow-md">
                        <Sparkles className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">Ground Truth AI Assistant</h3>
                        <p className="text-[10px] text-slate-500">Strictly grounded in uploaded files</p>
                      </div>
                    </div>
                    {chatHistory.length > 0 && (
                      <button
                        onClick={() => setChatHistory([])}
                        className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                        title="Clear Chat History"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* Suggested Quick Prompts */}
                  <div className="py-2.5 border-b border-slate-100 space-y-1.5">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Quick Knowledge Queries:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        'What does our uploaded policy say?',
                        'Summarize company business type',
                        'What state jurisdiction governs us?'
                      ].map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleAskAI(prompt)}
                          disabled={asking}
                          className="text-[11px] bg-slate-50 hover:bg-indigo-50 hover:text-indigo-700 text-slate-600 px-2.5 py-1 rounded-lg transition-colors text-left cursor-pointer border border-slate-200"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Chat Messages Stream */}
                  <div className="flex-1 overflow-y-auto py-4 space-y-4 pr-1 scrollbar-thin scrollbar-thumb-slate-200">
                    {chatHistory.length === 0 ? (
                      <div className="text-center py-12 text-slate-400">
                        <div className="w-12 h-12 bg-indigo-50 text-indigo-500 rounded-2xl flex items-center justify-center mx-auto mb-3 border border-indigo-100">
                          <Bot className="w-6 h-6" />
                        </div>
                        <p className="text-xs font-semibold text-slate-700">Ask any question about your files</p>
                        <p className="text-[11px] text-slate-400 mt-1 max-w-xs mx-auto leading-relaxed">
                          The AI reads your uploaded PDF, DOCX, CSV, or Excel files and cites exact excerpts as ground truth.
                        </p>
                      </div>
                    ) : (
                      chatHistory.map((msg, index) => (
                        <div
                          key={index}
                          className={`flex gap-2.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                          {msg.sender === 'ai' && (
                            <div className="w-7 h-7 bg-indigo-600 text-white rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                              <Bot className="w-4 h-4" />
                            </div>
                          )}

                          <div
                            className={`p-3.5 rounded-2xl max-w-[88%] relative group transition-all ${
                              msg.sender === 'user'
                                ? 'bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-tr-none shadow-sm text-xs'
                                : 'bg-slate-50 text-slate-800 rounded-tl-none border border-slate-200 shadow-sm'
                            }`}
                          >
                            {/* Copy button for AI response */}
                            {msg.sender === 'ai' && (
                              <button
                                onClick={() => copyMessageText(msg.text, index)}
                                className="absolute top-2 right-2 p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
                                title="Copy answer"
                              >
                                {copiedMsgIdx === index ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            )}

                            {msg.sender === 'user' ? (
                              <p className="whitespace-pre-wrap font-sans text-xs text-slate-100">{msg.text}</p>
                            ) : msg.text.toLowerCase().includes('do not contain information') || msg.text.toLowerCase().includes('no direct matching text excerpts') ? (
                              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 space-y-1.5">
                                <div className="flex items-center gap-1.5 font-bold text-xs text-amber-800">
                                  <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                                  <span>No matching content in uploaded documents</span>
                                </div>
                                <p className="text-xs text-amber-700 leading-relaxed font-sans">
                                  The uploaded documents do not contain information to answer this question. Try uploading additional files or rephrasing your question.
                                </p>
                              </div>
                            ) : (
                              <FormattedChatMessage content={msg.text} />
                            )}
                            
                            {/* Ground Truth Excerpts Box - only shown when excerpts exist and content is found */}
                            {!msg.text.toLowerCase().includes('do not contain information') &&
                             !msg.text.toLowerCase().includes('no direct matching text excerpts') &&
                             msg.excerpts && msg.excerpts.length > 0 && (
                              <div className="mt-3 pt-3 border-t border-slate-200/80 space-y-2">
                                <span className="text-[10px] font-bold text-indigo-700 uppercase tracking-wider block">Ground Truth Document Excerpts:</span>
                                {msg.excerpts.map((ex, i) => (
                                  <div key={i} className="p-2.5 bg-white rounded-xl border border-slate-200 text-[11px] text-slate-700 shadow-xs">
                                    <span className="font-bold text-indigo-600 block mb-0.5">📄 {ex.document_title} {ex.file_name ? `(${ex.file_name})` : ''}</span>
                                    <p className="text-slate-600 line-clamp-3 italic leading-relaxed font-serif">"{ex.excerpt}"</p>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Sources tags */}
                            {msg.sources && msg.sources.length > 0 && (
                              <div className="pt-2 mt-2 border-t border-slate-200 text-[10px] text-slate-500 font-medium flex items-center gap-1.5 flex-wrap">
                                <Layers className="w-3 h-3 text-indigo-500" />
                                <span className="font-semibold text-slate-600">Sources:</span>
                                {msg.sources.map((src, sIdx) => (
                                  <span key={sIdx} className="bg-slate-200/80 text-slate-700 px-1.5 py-0.5 rounded font-mono text-[9px]">
                                    {src}
                                  </span>
                                ))}
                              </div>
                            )}

                            {msg.timestamp && (
                              <span className={`block text-[9px] mt-1.5 text-right ${msg.sender === 'user' ? 'text-indigo-200' : 'text-slate-400'}`}>
                                {msg.timestamp}
                              </span>
                            )}
                          </div>

                          {msg.sender === 'user' && (
                            <div className="w-7 h-7 bg-slate-800 text-slate-200 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                              <User className="w-4 h-4" />
                            </div>
                          )}
                        </div>
                      ))
                    )}

                    {asking && (
                      <div className="flex items-center gap-2.5 text-xs text-indigo-700 font-semibold bg-indigo-50/80 p-3 rounded-xl border border-indigo-100 animate-pulse">
                        <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                        <span>Querying Qdrant & generating grounded response...</span>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Scoped Document Selector (Phase 3.1) */}
                  {selectedCompany?.documents && selectedCompany.documents.length > 0 && (
                    <div className="pt-2 pb-1 flex items-center gap-2 text-[11px] border-t border-slate-100">
                      <span className="font-semibold text-slate-500 whitespace-nowrap">Ask about:</span>
                      <select
                        value={selectedDocScope}
                        onChange={(e) => setSelectedDocScope(e.target.value)}
                        className="w-full text-xs py-1 px-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 truncate"
                      >
                        <option value="all">All Documents ({selectedCompany.documents.length})</option>
                        {selectedCompany.documents.map((d) => (
                          <option key={d.id} value={d.id}>
                            📄 {d.title}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Input Box */}
                  <form onSubmit={(e) => { e.preventDefault(); handleAskAI(); }} className="pt-2 border-t border-slate-100 flex gap-2">
                    <input
                      type="text"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="Ask questions about your uploaded docs..."
                      className="flex-1 text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50"
                      disabled={asking}
                    />
                    <button
                      type="submit"
                      disabled={asking || !question.trim()}
                      className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white p-2.5 rounded-xl shadow-md transition-all cursor-pointer flex-shrink-0"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </form>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Registration Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-xl w-full p-6 md:p-8 space-y-6 relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2.5">
                <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                  <Building2 className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-lg font-bold text-slate-900">Register Company via GSTIN</h3>
                  <p className="text-xs text-slate-500">Live Sandbox API profiling & audit trail storage</p>
                </div>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {modalError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  15-Character GSTIN Number
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    maxLength={15}
                    value={gstinInput}
                    onChange={(e) => setGstinInput(e.target.value.toUpperCase())}
                    placeholder="e.g. 27AAPCA1234B1ZV"
                    className="flex-1 font-mono text-sm px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 uppercase tracking-wider"
                  />
                  <button
                    type="button"
                    onClick={handlePreview}
                    disabled={previewing || gstinInput.trim().length !== 15}
                    className="flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white px-4 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer"
                  >
                    {previewing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    <span>{previewing ? 'Querying API...' : 'Fetch Sandbox Profile'}</span>
                  </button>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">Try standard 15-char GSTINs like <code className="text-indigo-600 font-mono">27AAPCA1234B1ZV</code> or <code className="text-indigo-600 font-mono">07AAACB1111C1Z5</code>.</p>
              </div>

              {/* Sandbox Preview Result Box */}
              {previewData && (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 animate-fadeIn">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-indigo-700 uppercase tracking-wider">Sandbox API Live Result</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${previewData.status.toLowerCase() === 'active' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                      {previewData.status}
                    </span>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">{previewData.legal_name}</h4>
                    <p className="text-xs text-slate-500">{previewData.entity_type} • Reg Date: {previewData.registration_date}</p>
                  </div>
                  <div className="text-xs text-slate-600 space-y-1 pt-2 border-t border-slate-200/60">
                    <p><span className="font-semibold text-slate-700">Jurisdiction:</span> {previewData.state_jurisdiction}</p>
                    <p><span className="font-semibold text-slate-700">Address:</span> {previewData.principal_address?.formatted}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRegister}
                disabled={registering || gstinInput.trim().length !== 15}
                className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-xs font-semibold shadow-md cursor-pointer"
              >
                {registering ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                <span>{registering ? 'Saving Profile...' : 'Confirm & Save Profile'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* File Upload Knowledge Document Modal */}
      {showDocModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full p-6 md:p-8 space-y-5 relative">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                  <UploadCloud className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Upload Ground Truth File</h3>
                  <p className="text-xs text-slate-500">PDF, Word, CSV, Excel, TXT or Markdown</p>
                </div>
              </div>
              <button onClick={() => setShowDocModal(false)} className="text-slate-400 font-bold p-1 cursor-pointer">✕</button>
            </div>

            {docUploadError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{docUploadError}</span>
              </div>
            )}

            <form onSubmit={handleUploadDocument} className="space-y-4">
              {/* File Dropzone Input */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Select Ground Truth Document
                </label>
                <div className="relative border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-2xl p-6 text-center bg-slate-50 hover:bg-indigo-50/40 transition-all cursor-pointer">
                  <input
                    type="file"
                    required
                    accept=".pdf,.docx,.doc,.csv,.xlsx,.xls,.txt,.md"
                    onChange={handleFileChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  {selectedFile ? (
                    <div className="flex items-center justify-center gap-3">
                      <div className="p-2 bg-white rounded-lg shadow-sm">
                        {getFileIcon(selectedFile.name.split('.').pop())}
                      </div>
                      <div className="text-left">
                        <p className="text-xs font-bold text-slate-800">{selectedFile.name}</p>
                        <p className="text-[10px] text-slate-400">{(selectedFile.size / 1024).toFixed(1)} KB • Click to change</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <UploadCloud className="w-8 h-8 text-indigo-500 mx-auto" />
                      <p className="text-xs font-semibold text-slate-700">Click or drag & drop document file here</p>
                      <p className="text-[10px] text-slate-400">Supported: .pdf, .docx, .csv, .xlsx, .txt, .md</p>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Document Title
                </label>
                <input
                  type="text"
                  required
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                  placeholder="e.g. Employee Policy 2026 / Vendor Rates Sheet"
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Category
                </label>
                <select
                  value={docCategory}
                  onChange={(e) => setDocCategory(e.target.value)}
                  className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 bg-white"
                >
                  <option value="Corporate Policy">Corporate Policy</option>
                  <option value="Employee Handbook">Employee Handbook</option>
                  <option value="Financial & Tax Sheet">Financial & Tax Sheet</option>
                  <option value="Compliance Certificate">Compliance Certificate</option>
                  <option value="Board Resolution">Board Resolution</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button 
                  type="button" 
                  onClick={() => setShowDocModal(false)} 
                  className="px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={uploadingDoc || !selectedFile} 
                  className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-xs font-semibold shadow-md cursor-pointer"
                >
                  {uploadingDoc ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  <span>{uploadingDoc ? 'Parsing & Indexing File...' : 'Upload & Parse Ground Truth'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Risk Radar Modal — rendered on top of everything */}
      {riskModalDoc && (
        <RiskRadarModal
          risk={riskModalDoc.risk}
          docTitle={riskModalDoc.title}
          onClose={() => setRiskModalDoc(null)}
        />
      )}
    </div>
  );
};

export default KnowledgeDashboard;
