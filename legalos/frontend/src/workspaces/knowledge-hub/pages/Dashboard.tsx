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
  User
} from 'lucide-react';
import { 
  RegisteredCompany, 
  CompanyProfilePreview, 
  GroundTruthExcerpt,
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
  
  // Document Deletion State
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);

  // AI Q&A Chat State
  const [question, setQuestion] = useState<string>('');
  const [asking, setAsking] = useState<boolean>(false);
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
      await fetchCompanies();
      setShowDocModal(false);
      setSelectedFile(null);
      setDocTitle('');
    } catch (err: any) {
      setDocUploadError(err?.response?.data?.detail || 'Failed to parse and upload document.');
    } finally {
      setUploadingDoc(false);
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
      const res = await askKnowledgeAI(userMsg, selectedCompanyId || undefined);
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

                  {selectedCompany.documents.length === 0 ? (
                    <div className="p-8 text-center bg-slate-50 rounded-xl border border-dashed border-slate-300 space-y-3">
                      <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto border border-indigo-100">
                        <UploadCloud className="w-6 h-6" />
                      </div>
                      <h4 className="text-sm font-bold text-slate-800">No Ground Truth Files Uploaded Yet</h4>
                      <p className="text-xs text-slate-500 max-w-sm mx-auto">
                        Upload employee policies, NDAs, tax filings, or financial spreadsheets (.pdf, .docx, .csv, .xlsx). The AI Assistant will use these files as strict facts to answer your queries.
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {selectedCompany.documents.map((doc) => (
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
                      ))}
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
                            ) : (
                              <FormattedChatMessage content={msg.text} />
                            )}
                            
                            {/* Ground Truth Excerpts Box */}
                            {msg.excerpts && msg.excerpts.length > 0 && (
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

                  {/* Input Box */}
                  <form onSubmit={(e) => { e.preventDefault(); handleAskAI(); }} className="pt-3 border-t border-slate-100 flex gap-2">
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
    </div>
  );
};

export default KnowledgeDashboard;
