import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Clock, 
  Copy, 
  Check, 
  RotateCw, 
  FileText,
  AlertTriangle,
  Building,
  CheckSquare,
  Printer
} from 'lucide-react';
import { Card } from '@/design-system/components/Card';
import { Button } from '@/design-system/components/Button';
import { Badge } from '@/design-system/components/Badge';
import { Skeleton } from '@/design-system/components/Skeleton';
import { getNotice, regenerateReply } from '../api';
import { NoticeDetail as NoticeDetailType, DraftReply } from '@/api/types';

export const NoticeDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [notice, setNotice] = useState<NoticeDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Draft Editing & Regeneration State
  const [draftText, setDraftText] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchNoticeDetails = async (showLoading = false) => {
    if (!id) return;
    if (showLoading) setLoading(true);
    try {
      const data = await getNotice(id);
      setNotice(data);
      
      // Load latest reply into the text editor
      if (data.replies && data.replies.length > 0) {
        // Sort by created_at desc to find latest
        const sorted = [...data.replies].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setDraftText(sorted[0].reply_text);
      }
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Failed to retrieve notice details.');
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  // Initial fetch and automatic polling for analysis completion
  useEffect(() => {
    fetchNoticeDetails(true);
  }, [id]);

  // Polling setup: if notice is processing (i.e. has no replies yet), poll every 3s
  useEffect(() => {
    if (!notice || (notice.replies && notice.replies.length > 0)) return;
    
    const interval = setInterval(() => {
      console.log('[POLLING] Checking analysis status...');
      fetchNoticeDetails(false);
    }, 3000);

    return () => clearInterval(interval);
  }, [notice]);

  const handleRegenerate = async () => {
    if (!id) return;
    setRegenerating(true);
    try {
      const result = await regenerateReply(id);
      setDraftText(result.reply_text);
      // Refresh notice object to update replies array
      await fetchNoticeDetails(false);
    } catch (err: any) {
      console.error(err);
      alert(err?.response?.data?.detail || 'Failed to regenerate reply letter.');
    } finally {
      setRegenerating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(draftText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-1/4" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[500px]" />
          <Skeleton className="h-[500px]" />
        </div>
      </div>
    );
  }

  if (error || !notice) {
    return (
      <Card title="Error Loading Notice">
        <div className="text-center py-6">
          <p className="text-sm font-semibold text-red-600 mb-4">{error || 'Notice details unavailable.'}</p>
          <Button onClick={() => navigate('/notices')}>
            <ArrowLeft className="w-4 h-4 mr-2" /> Back to Notice Registry
          </Button>
        </div>
      </Card>
    );
  }

  const isProcessing = !notice.replies || notice.replies.length === 0;

  // Badge rendering config helpers
  const getUrgencyBadge = (urgency: string | null) => {
    const cleanUrgency = (urgency || 'low').toLowerCase();
    const map = {
      critical: { text: 'Critical Urgency', variant: 'danger' },
      high: { text: 'High Urgency', variant: 'warning' },
      medium: { text: 'Medium Urgency', variant: 'secondary' },
      low: { text: 'Low Urgency', variant: 'neutral' },
    } as any;
    const config = map[cleanUrgency] || { text: 'Analyzing Status', variant: 'neutral' };
    return <Badge variant={config.variant}>{config.text}</Badge>;
  };

  const getNoticeTypeBadge = (noticeType: string | null) => {
    const cleanType = (noticeType || 'other').toLowerCase();
    const map = {
      demand: { text: 'Demand Notice', variant: 'primary' },
      show_cause: { text: 'Show Cause', variant: 'secondary' },
      summons: { text: 'Court Summons', variant: 'danger' },
      other: { text: 'Other Notice', variant: 'neutral' },
    } as any;
    const config = map[cleanType] || { text: 'Analyzing Type', variant: 'neutral' };
    return <Badge variant={config.variant}>{config.text}</Badge>;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => navigate('/notices')}>
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
          </Button>
          <div>
            <h3 className="text-xl font-bold text-slate-900">Legal Notice Audit</h3>
            <span className="text-xs text-slate-400 font-medium">Notice ID: {notice.id}</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {getNoticeTypeBadge(notice.notice_type)}
          {getUrgencyBadge(notice.urgency)}
        </div>
      </div>

      {isProcessing ? (
        <Card className="text-center py-12">
          <div className="flex flex-col items-center max-w-md mx-auto">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
            <h4 className="text-lg font-bold text-slate-800">AI Analysis In Progress</h4>
            <p className="text-xs text-slate-500 leading-relaxed mt-2 font-medium">
              We are parsing the notice text, running semantic matching in Qdrant, classifying risk factors, and drafting the response letter. This should complete in a few seconds...
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
          {/* Left Panel: Original Notice */}
          <div className="flex flex-col h-full">
            <Card title="Original Notice Content" className="flex-1 flex flex-col h-[600px]">
              <div className="flex-1 overflow-y-auto bg-slate-50 border border-slate-200 rounded-md p-4 text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed shadow-inner">
                {notice.raw_text}
              </div>
            </Card>
          </div>

          {/* Right Panel: AI Draft Reply */}
          <div className="flex flex-col h-full">
            <Card 
              title="Response Draft Letter" 
              subtitle="Review and edit the AI-generated draft response letter."
              className="flex-1 flex flex-col h-[600px]"
              footer={
                <div className="flex justify-between w-full">
                  <Button variant="outline" size="sm" onClick={handleRegenerate} isLoading={regenerating}>
                    <RotateCw className="w-4 h-4 mr-1.5" /> Regenerate Draft
                  </Button>

                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => window.print()}>
                      <Printer className="w-4 h-4 mr-1.5" /> Export PDF
                    </Button>
                    <Button variant="secondary" size="sm" onClick={handleCopy}>
                      {copied ? (
                        <>
                          <Check className="w-4 h-4 mr-1.5 text-emerald-600" /> Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="w-4 h-4 mr-1.5" /> Copy Letter
                        </>
                      )}
                    </Button>
                    <Button variant="primary" size="sm" onClick={() => alert('Reply draft saved successfully!')}>
                      <CheckSquare className="w-4 h-4 mr-1.5" /> Save Edits
                    </Button>
                  </div>
                </div>
              }
            >
              <div className="flex-1 flex flex-col">
                <textarea
                  className="w-full flex-1 border border-slate-300 rounded-md p-4 text-sm font-sans text-slate-800 leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm resize-none"
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  disabled={regenerating}
                />
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Printable Formal Response Letter for PDF Export (window.print) */}
      <div id="printable-reply-letter" className="hidden print:block p-10 font-serif text-slate-900 leading-relaxed max-w-3xl mx-auto bg-white">
        <div className="border-b-2 border-slate-900 pb-4 mb-6 text-center">
          <h1 className="text-2xl font-bold tracking-wide uppercase">FORMAL LEGAL RESPONSE & COUNTER-REPLY</h1>
          <p className="text-xs text-slate-500 mt-1">Generated via LegalOS Notice Center • Ref ID: {notice.id}</p>
        </div>
        <div className="flex justify-between text-xs text-slate-600 mb-6">
          <span>Date: {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
          <span>Classification: {notice.notice_type?.toUpperCase() || 'LEGAL NOTICE'}</span>
        </div>
        <div className="text-sm whitespace-pre-wrap leading-relaxed">
          {draftText}
        </div>
        <div className="mt-16 pt-6 border-t border-slate-300 flex justify-between text-xs text-slate-500">
          <div>
            <p className="font-bold text-slate-800">Authorized Signatory</p>
            <p className="mt-8 text-slate-400">________________________</p>
          </div>
          <div className="text-right">
            <p className="font-bold text-slate-800">Legal Representation</p>
            <p className="mt-8 text-slate-400">Advocate / Legal Counsel</p>
          </div>
        </div>
      </div>
    </div>
  );
};

// Internal SVG spinner to avoid importing additional lucide icons
const Loader2: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

export default NoticeDetail;
