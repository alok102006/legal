import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Calendar, 
  Plus, 
  Trash2, 
  Loader2, 
  Building2, 
  Sparkles, 
  UploadCloud, 
  ShieldAlert, 
  ShieldCheck,
  CheckCircle,
  AlertCircle,
  FileText,
  Clock,
  ChevronRight,
  X,
  RefreshCw,
  Info
} from 'lucide-react';
import { 
  listTasks, 
  createTask, 
  updateTask, 
  deleteTask, 
  initStatutoryTasks, 
  uploadComplianceFile, 
  listAnalyses, 
  getAnalysisDetails,
  initStatutoryTasksByGstin
} from '../api';
import { ComplianceTask, ComplianceDocumentAnalysis } from '@/api/types';

export const Dashboard: React.FC = () => {
  const [tasks, setTasks] = useState<ComplianceTask[]>([]);
  const [analyses, setAnalyses] = useState<ComplianceDocumentAnalysis[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [loadingAnalyses, setLoadingAnalyses] = useState(true);
  
  // Selection/Input states
  const [selectedBusinessType, setSelectedBusinessType] = useState('private_limited');
  const [isInitializing, setIsInitializing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // GSTIN onboarding states
  const [gstinInput, setGstinInput] = useState('');
  const [showManualSetup, setShowManualSetup] = useState(false);
  const [setupFeedback, setSetupFeedback] = useState<{ companyName: string; constitution: string; count: number } | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);

  // Handle statutory calendar initialization by GSTIN
  const handleInitializeByGstin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (gstinInput.trim().length !== 15) {
      setSetupError("Please enter a valid 15-character Indian GSTIN.");
      return;
    }

    setIsInitializing(true);
    setSetupError(null);
    setSetupFeedback(null);

    try {
      const response = await initStatutoryTasksByGstin(gstinInput.trim());
      setTasks(response.tasks);
      setSetupFeedback({
        companyName: response.company_name,
        constitution: response.constitution,
        count: response.tasks.length
      });
      setGstinInput('');
    } catch (err: any) {
      console.error("Failed to initialize tasks by GSTIN:", err);
      setSetupError(err.response?.data?.detail || "GSTIN lookup failed. Please double-check the number or try manual setup.");
    } finally {
      setIsInitializing(false);
    }
  };

  // Manual Task Drawer state
  const [showTaskDrawer, setShowTaskDrawer] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskCategory, setNewTaskCategory] = useState('tax');
  const [newTaskDueDate, setNewTaskDueDate] = useState('');
  const [newTaskDesc, setNewTaskDesc] = useState('');
  const [newTaskPenalty, setNewTaskPenalty] = useState('');
  const [isCreatingTask, setIsCreatingTask] = useState(false);

  // Analysis Details Drawer state
  const [selectedAnalysis, setSelectedAnalysis] = useState<ComplianceDocumentAnalysis | null>(null);
  const [showAnalysisDrawer, setShowAnalysisDrawer] = useState(false);
  const [loadingAnalysisDetail, setLoadingAnalysisDetail] = useState(false);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Load Initial Data
  const loadData = async () => {
    try {
      setLoadingTasks(true);
      const fetchedTasks = await listTasks();
      setTasks(fetchedTasks);
    } catch (err) {
      console.error("Error fetching compliance tasks:", err);
    } finally {
      setLoadingTasks(false);
    }

    try {
      setLoadingAnalyses(true);
      const fetchedAnalyses = await listAnalyses();
      setAnalyses(fetchedAnalyses);
    } catch (err) {
      console.error("Error fetching compliance analyses:", err);
    } finally {
      setLoadingAnalyses(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Handle statutory generation
  const handleInitialize = async () => {
    setIsInitializing(true);
    try {
      const generated = await initStatutoryTasks(selectedBusinessType);
      setTasks(generated);
    } catch (err) {
      console.error("Failed to initialize compliance tasks:", err);
    } finally {
      setIsInitializing(false);
    }
  };

  // Toggle task status
  const handleToggleTask = async (taskId: string, currentStatus: string) => {
    const nextStatus = currentStatus === 'completed' ? 'pending' : 'completed';
    // Optimistic UI update
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: nextStatus } : t));

    try {
      await updateTask(taskId, { status: nextStatus });
    } catch (err) {
      console.error("Failed to update task status:", err);
      // Revert UI on error
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: currentStatus as any } : t));
    }
  };


  // Delete task
  const handleDeleteTask = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      setTasks(prev => prev.filter(t => t.id !== taskId));
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  // Create custom manual task
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    setIsCreatingTask(true);
    try {
      const created = await createTask({
        title: newTaskTitle,
        category: newTaskCategory,
        due_date: newTaskDueDate || null,
        description: newTaskDesc || null,
        penalty_desc: newTaskPenalty || null
      });
      setTasks(prev => [created, ...prev]);
      // Reset form
      setNewTaskTitle('');
      setNewTaskCategory('tax');
      setNewTaskDueDate('');
      setNewTaskDesc('');
      setNewTaskPenalty('');
      setShowTaskDrawer(false);
    } catch (err) {
      console.error("Failed to create task:", err);
    } finally {
      setIsCreatingTask(false);
    }
  };

  // File Upload handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setIsUploading(true);
    setUploadError(null);

    try {
      // 1. Upload to API
      const stubAnalysis = await uploadComplianceFile(file);
      // Prepend stub to analyses list
      setAnalyses(prev => [stubAnalysis, ...prev]);

      // 2. Poll for updates periodically until processed
      pollAnalysis(stubAnalysis.id);
    } catch (err: any) {
      console.error("Upload failed:", err);
      setUploadError(err.response?.data?.detail || "Failed to upload and analyze document.");
      setIsUploading(false);
    }
  };

  // Poll utility for document analysis
  const pollAnalysis = async (id: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const details = await getAnalysisDetails(id);
        // Check if authority has been populated (i.e. finished processing)
        if (details.authority !== 'Processing...' || attempts > 15) {
          clearInterval(interval);
          setAnalyses(prev => prev.map(a => a.id === id ? details : a));
          
          // Re-fetch tasks since analysis auto-creates them
          const freshTasks = await listTasks();
          setTasks(freshTasks);
          setIsUploading(false);
        }
      } catch (err) {
        console.error("Polling error:", err);
        clearInterval(interval);
        setIsUploading(false);
      }
    }, 2500);
  };

  // Open Analysis Drawer
  const handleViewAnalysis = async (analysis: ComplianceDocumentAnalysis) => {
    setSelectedAnalysis(analysis);
    setShowAnalysisDrawer(true);
    setLoadingAnalysisDetail(true);
    try {
      const details = await getAnalysisDetails(analysis.id);
      setSelectedAnalysis(details);
    } catch (err) {
      console.error("Error loading analysis details:", err);
    } finally {
      setLoadingAnalysisDetail(false);
    }
  };

  // Computed metrics
  const pendingTasks = tasks.filter(t => t.status !== 'completed');
  const overdueTasksCount = pendingTasks.filter(t => {
    if (!t.due_date) return false;
    return new Date(t.due_date) < new Date() && t.status !== 'completed';
  }).length;

  const taxTasksCount = tasks.filter(t => t.category === 'tax').length;
  const corporateTasksCount = tasks.filter(t => t.category === 'corporate').length;

  const filteredTasks = tasks.filter(t => {
    const matchesCategory = categoryFilter === 'all' || t.category === categoryFilter;
    const matchesStatus = statusFilter === 'all' || 
      (statusFilter === 'pending' && t.status !== 'completed') || 
      (statusFilter === 'completed' && t.status === 'completed');
    return matchesCategory && matchesStatus;
  });

  return (
    <div className="space-y-6 pb-20 relative">
      {/* Title & Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h3 className="text-2xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
            <Activity className="w-7 h-7 text-blue-600 animate-pulse" />
            Compliance Center & Calendar
          </h3>
          <p className="text-slate-500 text-sm mt-1">
            Automate statutory calendars, parse tax notices and certificates using AI, and manage SME compliance deadlines.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={loadData}
            className="p-2 text-slate-500 hover:text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:shadow transition"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowTaskDrawer(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg text-sm shadow-sm transition hover:shadow-md"
          >
            <Plus className="w-4 h-4" />
            Add Task
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider block">Pending Tasks</span>
            <span className="text-2xl font-extrabold text-slate-800 mt-1 block">{pendingTasks.length}</span>
          </div>
          <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-lg flex items-center justify-center">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider block">Overdue Filings</span>
            <span className={`text-2xl font-extrabold mt-1 block ${overdueTasksCount > 0 ? 'text-rose-600' : 'text-slate-800'}`}>
              {overdueTasksCount}
            </span>
          </div>
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${overdueTasksCount > 0 ? 'bg-rose-50 text-rose-600' : 'bg-slate-50 text-slate-400'}`}>
            <AlertCircle className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider block">Tax Compliance</span>
            <span className="text-2xl font-extrabold text-slate-800 mt-1 block">{taxTasksCount}</span>
          </div>
          <div className="w-10 h-10 bg-amber-50 text-amber-600 rounded-lg flex items-center justify-center">
            <Calendar className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider block">Corporate Filings</span>
            <span className="text-2xl font-extrabold text-slate-800 mt-1 block">{corporateTasksCount}</span>
          </div>
          <div className="w-10 h-10 bg-emerald-50 text-emerald-600 rounded-lg flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Grid: Checklist & Document Upload */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Compliance Calendar / Checklist */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Statutory calendar setup card if task list is empty */}
          {tasks.length === 0 && !loadingTasks && (
            <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 text-white p-8 rounded-2xl border border-slate-800 shadow-xl relative overflow-hidden">
              <div className="absolute right-0 bottom-0 opacity-5 pointer-events-none">
                <Sparkles className="w-64 h-64 text-blue-400" />
              </div>
              
              <div className="max-w-2xl relative z-10 space-y-4">
                <div className="flex items-center gap-2">
                  <span className="bg-blue-600/90 text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full border border-blue-500/30">
                    ✨ Frictionless Setup
                  </span>
                  {showManualSetup && (
                    <span className="bg-slate-800 text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full border border-slate-700">
                      Manual Selection
                    </span>
                  )}
                </div>

                {!showManualSetup ? (
                  // GSTIN AUTO SETUP
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-2xl font-extrabold tracking-tight">Auto-Configure Compliance Calendar</h4>
                      <p className="text-slate-400 text-xs mt-1.5 leading-relaxed">
                        Don't know about compliance? No problem! Just enter your company's 15-character GSTIN. Our system automatically fetches your official business name and constitution to build a personalized compliance schedule in 1 click.
                      </p>
                    </div>

                    <form onSubmit={handleInitializeByGstin} className="flex flex-col sm:flex-row gap-2 mt-4 max-w-lg">
                      <input
                        type="text"
                        placeholder="Enter 15-character GSTIN (e.g. 27AAAAA1111A1Z1)"
                        value={gstinInput}
                        onChange={(e) => setGstinInput(e.target.value.toUpperCase())}
                        maxLength={15}
                        disabled={isInitializing}
                        className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-500 font-mono tracking-wider text-white"
                      />
                      <button
                        type="submit"
                        disabled={isInitializing || gstinInput.trim().length !== 15}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold px-6 py-3 rounded-xl shadow-sm hover:shadow transition flex items-center justify-center gap-2 whitespace-nowrap"
                      >
                        {isInitializing ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Fetching...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4" />
                            Configure Calendar
                          </>
                        )}
                      </button>
                    </form>

                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => {
                          setShowManualSetup(true);
                          setSetupError(null);
                        }}
                        className="text-slate-400 hover:text-white text-xs font-semibold underline transition"
                      >
                        Or setup manually by choosing your business type
                      </button>
                    </div>
                  </div>
                ) : (
                  // MANUAL BUSINESS TYPE SETUP
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-2xl font-extrabold tracking-tight">Manual Compliance Setup</h4>
                      <p className="text-slate-400 text-xs mt-1.5 leading-relaxed">
                        Select your business entity structure to generate the default statutory tax and legal deadlines for FY 2026-27.
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 mt-4">
                      <select
                        value={selectedBusinessType}
                        onChange={(e) => setSelectedBusinessType(e.target.value)}
                        className="bg-slate-900 text-xs font-semibold px-4 py-3 rounded-xl border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 text-white cursor-pointer"
                      >
                        <option value="private_limited">Private Limited Company</option>
                        <option value="llp">Limited Liability Partnership (LLP)</option>
                        <option value="partnership">Partnership Firm</option>
                        <option value="sole_proprietorship">Sole Proprietorship / Individual</option>
                      </select>
                      <button
                        onClick={handleInitialize}
                        disabled={isInitializing}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold px-6 py-3 rounded-xl shadow transition flex items-center justify-center gap-2"
                      >
                        {isInitializing ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5" />
                            Initialize Manual Calendar
                          </>
                        )}
                      </button>
                    </div>

                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => {
                          setShowManualSetup(false);
                          setSetupError(null);
                        }}
                        className="text-slate-400 hover:text-white text-xs font-semibold underline transition"
                      >
                        ← Back to automated GSTIN configuration
                      </button>
                    </div>
                  </div>
                )}

                {/* Error Banner */}
                {setupError && (
                  <div className="bg-rose-950/50 border border-rose-800 rounded-xl p-3.5 text-xs text-rose-300 flex items-start gap-2 max-w-lg mt-2">
                    <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
                    <span>{setupError}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Success Onboarding Feedback Toast/Alert */}
          {setupFeedback && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 shadow-sm space-y-2 mb-6 animate-fadeIn">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-6 h-6 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <h5 className="font-extrabold text-sm text-slate-800">Compliance Calendar Populated!</h5>
                  <p className="text-slate-600 text-xs leading-relaxed mt-0.5">
                    We verified details for <strong className="text-slate-900 font-extrabold">{setupFeedback.companyName}</strong> ({setupFeedback.constitution}). We have successfully generated <strong className="text-slate-900 font-extrabold">{setupFeedback.count} statutory compliance obligations</strong> for your business profile.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <span className="bg-emerald-100 text-emerald-800 text-[10px] px-2.5 py-0.5 rounded font-bold border border-emerald-200 uppercase tracking-wide">
                      {setupFeedback.constitution}
                    </span>
                    <button 
                      onClick={() => setSetupFeedback(null)}
                      className="text-slate-400 hover:text-slate-600 text-xs font-semibold pl-2 border-l border-slate-200"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Checklist Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            {/* Table Header Filter controls */}
            <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex flex-wrap items-center justify-between gap-4">
              <h4 className="font-bold text-slate-800 text-sm">Compliance Checklist</h4>
              <div className="flex items-center gap-2">
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="bg-white text-xs font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 cursor-pointer"
                >
                  <option value="all">All Categories</option>
                  <option value="tax">Tax Compliance</option>
                  <option value="corporate">Corporate (MCA)</option>
                  <option value="labor">Labor (PF/ESI)</option>
                  <option value="license">Licenses & Permits</option>
                  <option value="other">Other</option>
                </select>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-white text-xs font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 cursor-pointer"
                >
                  <option value="all">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
            </div>

            {/* Tasks list */}
            {loadingTasks ? (
              <div className="p-10 text-center flex flex-col items-center justify-center text-slate-400">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600 mb-2" />
                <span className="text-xs font-medium">Loading compliance calendar...</span>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="p-12 text-center text-slate-400 flex flex-col items-center justify-center">
                <CheckCircle className="w-12 h-12 text-slate-300 mb-2" />
                <h5 className="font-bold text-slate-700 text-sm">No tasks found</h5>
                <p className="text-slate-400 text-xs mt-1">
                  There are no compliance tasks matching the current filters.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {filteredTasks.map((task) => {
                  const isCompleted = task.status === 'completed';
                  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && !isCompleted;
                  
                  // Category badges styling
                  const categoryStyles: Record<string, string> = {
                    tax: "bg-amber-50 text-amber-700 border-amber-200",
                    corporate: "bg-emerald-50 text-emerald-700 border-emerald-200",
                    labor: "bg-indigo-50 text-indigo-700 border-indigo-200",
                    license: "bg-purple-50 text-purple-700 border-purple-200",
                    other: "bg-slate-50 text-slate-600 border-slate-200"
                  };

                  return (
                    <div 
                      key={task.id}
                      className={`p-4 flex items-start gap-4 transition hover:bg-slate-50/50 ${isCompleted ? 'bg-slate-50/20' : ''}`}
                    >
                      {/* Checkbox wrapper */}
                      <button
                        onClick={() => handleToggleTask(task.id, task.status)}
                        className={`mt-1 w-5 h-5 flex items-center justify-center rounded border transition focus:outline-none ${
                          isCompleted 
                            ? 'bg-blue-600 border-blue-600 text-white' 
                            : 'border-slate-300 hover:border-blue-500 bg-white'
                        }`}
                        aria-label={`Mark task ${task.title} as ${isCompleted ? 'pending' : 'completed'}`}
                      >
                        {isCompleted && <span className="text-[10px]">✔</span>}
                      </button>

                      {/* Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h5 className={`font-semibold text-sm ${isCompleted ? 'line-through text-slate-400' : 'text-slate-800'}`}>
                            {task.title}
                          </h5>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${categoryStyles[task.category] || categoryStyles.other}`}>
                            {task.category.toUpperCase()}
                          </span>
                          {isOverdue && (
                            <span className="bg-rose-50 text-rose-700 border border-rose-200 text-[10px] px-2 py-0.5 rounded-full font-bold">
                              OVERDUE
                            </span>
                          )}
                        </div>

                        {task.description && (
                          <p className={`text-xs mt-1 leading-relaxed ${isCompleted ? 'text-slate-400' : 'text-slate-500'}`}>
                            {task.description}
                          </p>
                        )}

                        {task.penalty_desc && !isCompleted && (
                          <div className="flex items-center gap-1 mt-1.5 text-[10px] text-rose-500 font-bold">
                            <AlertCircle className="w-3.5 h-3.5" />
                            Risk: {task.penalty_desc}
                          </div>
                        )}

                        {/* Metadata dates */}
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2.5 text-[10px] text-slate-400 font-medium">
                          {task.due_date && (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3 text-slate-400" />
                              Due Date: {new Date(task.due_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                            </span>
                          )}
                          {task.document_id && (
                            <span className="flex items-center gap-1 text-blue-500 font-semibold cursor-pointer hover:underline">
                              <FileText className="w-3 h-3" />
                              Parsed from Upload
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Quick delete button */}
                      <button
                        onClick={() => handleDeleteTask(task.id)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition"
                        title="Delete task"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Column: Compliance Document Parser */}
        <div className="space-y-6">
          
          {/* Upload card */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <h4 className="font-bold text-slate-800 text-sm mb-1 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-blue-600" />
              Document Intelligence
            </h4>
            <p className="text-slate-400 text-xs leading-relaxed mb-4">
              Upload active business licenses, certificates, tax assessments, or notices. The AI extracts valid periods, compliance rules, and adds task deadlines automatically.
            </p>

            <label className={`
              border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition
              ${isUploading ? 'bg-slate-50 border-blue-400' : 'bg-slate-50/50 hover:bg-slate-50 border-slate-200 hover:border-blue-500'}
            `}>
              <input 
                type="file" 
                className="hidden" 
                onChange={handleFileUpload} 
                disabled={isUploading}
                accept=".pdf,.docx,.txt,.md"
              />
              {isUploading ? (
                <>
                  <Loader2 className="w-8 h-8 text-blue-600 animate-spin mb-2" />
                  <span className="text-xs font-bold text-slate-700">Analyzing Document...</span>
                  <span className="text-[10px] text-slate-400 mt-1">AI is parsing and extracting action dates...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-8 h-8 text-slate-400 mb-2" />
                  <span className="text-xs font-bold text-slate-700">Upload Regulatory File</span>
                  <span className="text-[10px] text-slate-400 mt-1">PDF, DOCX, TXT up to 10MB</span>
                </>
              )}
            </label>

            {uploadError && (
              <div className="mt-3 bg-rose-50 border border-rose-100 rounded-lg p-3 text-[10px] font-semibold text-rose-600 flex items-start gap-1.5">
                <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{uploadError}</span>
              </div>
            )}
          </div>

          {/* List of scanned documents */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-100 bg-slate-50/50">
              <h4 className="font-bold text-slate-800 text-xs tracking-wider uppercase">Scanned Certificates & Notices</h4>
            </div>

            {loadingAnalyses ? (
              <div className="p-6 text-center text-slate-400 text-xs">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600 inline mr-1.5" />
                Loading index...
              </div>
            ) : analyses.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-xs flex flex-col items-center justify-center">
                <FileText className="w-8 h-8 text-slate-200 mb-1" />
                No documents uploaded yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                {analyses.map((ana) => {
                  const isProcessing = ana.authority === 'Processing...';
                  let badgeColor = "bg-emerald-50 text-emerald-700 border-emerald-200";
                  if (ana.status === 'expired') badgeColor = "bg-rose-50 text-rose-700 border-rose-200";
                  if (ana.status === 'warning') badgeColor = "bg-amber-50 text-amber-700 border-amber-200";
                  if (ana.status === 'needs_action') badgeColor = "bg-blue-50 text-blue-700 border-blue-200";

                  return (
                    <div 
                      key={ana.id}
                      onClick={() => !isProcessing && handleViewAnalysis(ana)}
                      className={`p-3.5 flex items-center justify-between gap-3 text-left transition ${isProcessing ? 'opacity-65 cursor-not-allowed' : 'hover:bg-slate-50 cursor-pointer'}`}
                    >
                      <div className="min-w-0">
                        <h6 className="font-bold text-xs text-slate-700 truncate leading-snug">
                          {ana.document_type}
                        </h6>
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400 font-medium">
                          <span>{ana.authority}</span>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {isProcessing ? (
                          <span className="flex items-center gap-1 bg-slate-50 text-slate-500 border border-slate-200 text-[9px] px-1.5 py-0.5 rounded font-bold">
                            <Loader2 className="w-2.5 h-2.5 animate-spin" />
                            ANALYZING
                          </span>
                        ) : (
                          <>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded border font-extrabold tracking-wider uppercase ${badgeColor}`}>
                              {ana.status.replace('_', ' ')}
                            </span>
                            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </div>
      </div>

      {/* COMPONENT: Manual Add Task Drawer (Slide Over) */}
      {showTaskDrawer && (
        <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity" onClick={() => setShowTaskDrawer(false)}></div>
          
          <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md transform transition bg-white shadow-2xl flex flex-col h-full">
              
              {/* Header */}
              <div className="px-6 py-5 bg-slate-900 text-white flex items-center justify-between">
                <h4 className="font-bold text-base flex items-center gap-2">
                  <Plus className="w-5 h-5 text-blue-400" />
                  Add Compliance Task
                </h4>
                <button 
                  onClick={() => setShowTaskDrawer(false)}
                  className="p-1 hover:bg-slate-800 rounded transition text-slate-400 hover:text-white focus:outline-none"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleCreateTask} className="flex-1 overflow-y-auto p-6 space-y-4">
                <div>
                  <label htmlFor="task-title" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Task Title *</label>
                  <input
                    id="task-title"
                    type="text"
                    required
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    placeholder="e.g. GST Annual Audit Return"
                    className="w-full text-sm px-3.5 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="task-category" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Category</label>
                    <select
                      id="task-category"
                      value={newTaskCategory}
                      onChange={(e) => setNewTaskCategory(e.target.value)}
                      className="w-full text-sm px-3.5 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50 cursor-pointer"
                    >
                      <option value="tax">Tax Compliance</option>
                      <option value="corporate">Corporate (MCA)</option>
                      <option value="labor">Labor (PF/ESI)</option>
                      <option value="license">License & Permit</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="task-due-date" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Due Date</label>
                    <input
                      id="task-due-date"
                      type="date"
                      value={newTaskDueDate}
                      onChange={(e) => setNewTaskDueDate(e.target.value)}
                      className="w-full text-sm px-3.5 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50 cursor-pointer"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="task-desc" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Description</label>
                  <textarea
                    id="task-desc"
                    rows={3}
                    value={newTaskDesc}
                    onChange={(e) => setNewTaskDesc(e.target.value)}
                    placeholder="Provide details on the filing, portal to use, or requirements..."
                    className="w-full text-sm px-3.5 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50"
                  />
                </div>

                <div>
                  <label htmlFor="task-penalty" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Late Fee / Penalty Description</label>
                  <input
                    id="task-penalty"
                    type="text"
                    value={newTaskPenalty}
                    onChange={(e) => setNewTaskPenalty(e.target.value)}
                    placeholder="e.g. INR 200/day after due date"
                    className="w-full text-sm px-3.5 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50"
                  />
                </div>

                <div className="pt-4">
                  <button
                    type="submit"
                    disabled={isCreatingTask}
                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 rounded-lg shadow-sm transition disabled:opacity-50"
                  >
                    {isCreatingTask ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Saving Task...
                      </>
                    ) : (
                      'Create Task'
                    )}
                  </button>
                </div>
              </form>

            </div>
          </div>
        </div>
      )}

      {/* COMPONENT: Document Intelligence Drawer (Slide Over) */}
      {showAnalysisDrawer && selectedAnalysis && (
        <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity" onClick={() => setShowAnalysisDrawer(false)}></div>
          
          <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-lg transform transition bg-white shadow-2xl flex flex-col h-full">
              
              {/* Header */}
              <div className="px-6 py-5 bg-slate-900 text-white flex items-center justify-between">
                <div className="min-w-0">
                  <h4 className="font-bold text-base truncate flex items-center gap-2">
                    <FileText className="w-5 h-5 text-blue-400" />
                    Document Analysis Summary
                  </h4>
                  <span className="text-[10px] text-slate-400 mt-1 block">Parsed on: {new Date(selectedAnalysis.created_at).toLocaleDateString('en-IN')}</span>
                </div>
                <button 
                  onClick={() => setShowAnalysisDrawer(false)}
                  className="p-1 hover:bg-slate-800 rounded transition text-slate-400 hover:text-white focus:outline-none"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Content */}
              {loadingAnalysisDetail ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-400 p-10">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-600 mb-2" />
                  <span className="text-xs font-semibold">Loading document intelligence...</span>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  
                  {/* Status Banner */}
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-start gap-3">
                    {selectedAnalysis.status === 'active' ? (
                      <ShieldCheck className="w-7 h-7 text-emerald-600 flex-shrink-0" />
                    ) : (
                      <ShieldAlert className="w-7 h-7 text-amber-500 flex-shrink-0" />
                    )}
                    <div>
                      <h5 className="font-bold text-xs uppercase tracking-wider text-slate-500">Document Classification</h5>
                      <h6 className="font-extrabold text-sm text-slate-800 mt-0.5">{selectedAnalysis.document_type}</h6>
                      <div className="mt-2 flex items-center gap-2">
                        <span className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded border ${
                          selectedAnalysis.status === 'active' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' :
                          selectedAnalysis.status === 'expired' ? 'bg-rose-50 text-rose-700 border-rose-100' : 'bg-amber-50 text-amber-700 border-amber-100'
                        }`}>
                          {selectedAnalysis.status.replace('_', ' ')}
                        </span>
                        {selectedAnalysis.identifier_number && (
                          <span className="text-[10px] text-slate-500 font-semibold bg-white border px-2 py-0.5 rounded shadow-sm">
                            Ref: {selectedAnalysis.identifier_number}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Metadata fields */}
                  <div className="grid grid-cols-2 gap-4 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                    <div>
                      <span className="text-[10px] text-slate-400 font-bold block uppercase">Authority</span>
                      <span className="text-xs font-semibold text-slate-700 mt-0.5 block">{selectedAnalysis.authority}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 font-bold block uppercase">Validity Period</span>
                      <span className="text-xs font-semibold text-slate-700 mt-0.5 block">
                        {selectedAnalysis.issue_date ? new Date(selectedAnalysis.issue_date).toLocaleDateString('en-IN') : 'N/A'} to {' '}
                        {selectedAnalysis.expiry_date ? new Date(selectedAnalysis.expiry_date).toLocaleDateString('en-IN') : 'Permanent'}
                      </span>
                    </div>
                  </div>

                  {/* AI Risk Assessment */}
                  {selectedAnalysis.risk_assessment && (
                    <div className="bg-rose-50/50 border border-rose-100 p-4 rounded-xl space-y-1.5">
                      <h5 className="font-bold text-xs uppercase tracking-wider text-rose-700 flex items-center gap-1">
                        <ShieldAlert className="w-4 h-4" />
                        AI Regulatory Risk Audit
                      </h5>
                      <p className="text-slate-600 text-xs leading-relaxed font-medium">
                        {selectedAnalysis.risk_assessment}
                      </p>
                    </div>
                  )}

                  {/* AI Extracted Action Items */}
                  <div>
                    <h5 className="font-bold text-slate-700 text-xs tracking-wider uppercase mb-3 flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-blue-600" />
                      Extracted Compliance Action Items
                    </h5>

                    {(!selectedAnalysis.extracted_actions || selectedAnalysis.extracted_actions.length === 0) ? (
                      <p className="text-xs text-slate-400 italic">No specific follow-up actions required by this certificate.</p>
                    ) : (
                      <div className="space-y-3">
                        {selectedAnalysis.extracted_actions.map((act: any, idx: number) => (
                          <div 
                            key={idx}
                            className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm space-y-1.5 hover:border-blue-400 transition"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <h6 className="font-bold text-xs text-slate-800 leading-snug">{act.title}</h6>
                              {act.due_date && (
                                <span className="bg-blue-50 text-blue-700 text-[9px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap">
                                  Due: {new Date(act.due_date).toLocaleDateString('en-IN')}
                                </span>
                              )}
                            </div>
                            <p className="text-slate-500 text-[11px] leading-relaxed">{act.description}</p>
                            {act.penalty_desc && (
                              <div className="text-[10px] text-rose-500 font-bold bg-rose-50/50 border border-rose-100 rounded px-2 py-1 inline-block">
                                Penalty: {act.penalty_desc}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 text-[10px] font-semibold text-slate-500 flex items-start gap-1.5 mt-5">
                      <Info className="w-4 h-4 flex-shrink-0 text-slate-400 mt-0.5" />
                      <span>Note: These action items have been automatically generated as live, checkable tasks in your main checklist view.</span>
                    </div>
                  </div>

                </div>
              )}

            </div>
          </div>
        </div>
      )}

    </div>
  );
};
export default Dashboard;
