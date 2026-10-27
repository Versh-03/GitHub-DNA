import React, { useState, useEffect } from 'react';
import { 
  GitBranch, Play, Shield, Terminal, CheckCircle2, AlertTriangle, 
  XCircle, FileCode, Layers, Search, Cpu, RefreshCw, ExternalLink,
  ChevronRight, Bug, Eye, FileText, Activity, HelpCircle, Copy, Check,
  Clock, AlertOctagon
} from 'lucide-react';
import DependencyGraph from './components/DependencyGraph';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [repoUrl, setRepoUrl] = useState('https://github.com/github-dna-demos/retail-core-sample');
  const [analyzing, setAnalyzing] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [activeTab, setActiveTab] = useState('overview'); // overview, activity, finding, tests, report
  const [serverHealth, setServerHealth] = useState(null);
  const [copied, setCopied] = useState(false);

  // Workflow state
  const [runId, setRunId] = useState(null);
  const [repoMeta, setRepoMeta] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [investigation, setInvestigation] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Poll server health on load
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then(r => r.json())
      .then(d => setServerHealth(d))
      .catch(() => setServerHealth({ status: 'offline', docker_available: false }));
  }, []);

  const handleAnalyze = async (urlToAnalyze = repoUrl) => {
    setAnalyzing(true);
    setErrorMessage(null);
    setInvestigation(null);
    try {
      const targetUrl = urlToAnalyze.includes('retail-core-sample') ? 'sample://retail-core' : urlToAnalyze;
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Analysis request failed');
      
      setRunId(data.run_id);
      setRepoMeta(data.repo);
      setAnalysis(data.analysis);
      setActiveTab('overview');
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleInvestigate = async (demoMode = false) => {
    if (!runId) return;
    setInvestigating(true);
    setErrorMessage(null);
    setActiveTab('activity');
    try {
      const res = await fetch(`${API_BASE}/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId, demo_mode: demoMode })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Investigation failed');
      }
      
      if (data.investigation) {
        setInvestigation(data.investigation);
        if (data.investigation.finding?.issue_found) {
          setActiveTab('finding');
        } else if (data.investigation.status === 'llm_unavailable' || data.investigation.status === 'investigation_incomplete') {
          setActiveTab('activity');
        }
      }
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setInvestigating(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'tests_passed':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><CheckCircle2 className="w-3.5 h-3.5" /> Fix Verified in Container Sandbox</span>;
      case 'tests_failed':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20"><XCircle className="w-3.5 h-3.5" /> Tests Failed Execution</span>;
      case 'fix_proposed':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20"><Bug className="w-3.5 h-3.5" /> Fix Proposed (Unverified)</span>;
      case 'potential_issue':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20"><AlertTriangle className="w-3.5 h-3.5" /> Potential Issue Detected</span>;
      case 'no_issue_found':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20"><CheckCircle2 className="w-3.5 h-3.5" /> No Defects Identified</span>;
      case 'verification_unavailable':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20"><HelpCircle className="w-3.5 h-3.5" /> Sandbox Unavailable</span>;
      case 'llm_unavailable':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30"><Clock className="w-3.5 h-3.5 text-amber-400" /> Groq Rate Limited</span>;
      case 'investigation_incomplete':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30"><AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Investigation Incomplete</span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300">Ready</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-200 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-[#0c101c]/90 backdrop-blur sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
            <GitBranch className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white font-mono">GitHub DNA</h1>
              <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/50">MVP</span>
            </div>
            <p className="text-xs text-slate-400">Agentic Python Repository Analysis & Verification</p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>LLM:</span>
            <span className="font-mono text-cyan-300 font-medium">Groq openai/gpt-oss-20b</span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
            <Shield className="w-3.5 h-3.5 text-blue-400" />
            <span>Sandbox:</span>
            <span className={`font-medium ${serverHealth?.docker_available ? 'text-emerald-400' : 'text-amber-400'}`}>
              {serverHealth?.docker_available ? 'Docker (Network Isolated)' : 'Subprocess'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Repo Input Box */}
        <section className="bg-[#0d1322] border border-slate-800/90 rounded-xl p-5 shadow-xl">
          <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center">
            <div className="relative flex-1">
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                className="w-full bg-[#080d19] border border-slate-700/80 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
              />
            </div>
            <button
              onClick={() => handleAnalyze()}
              disabled={analyzing || !repoUrl.trim()}
              className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium text-sm px-5 py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors shadow-lg shadow-cyan-600/20 cursor-pointer"
            >
              {analyzing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              {analyzing ? 'Analyzing AST...' : 'Analyze Repository'}
            </button>
            {runId && (
              <button
                onClick={() => handleInvestigate(false)}
                disabled={investigating}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-sm px-5 py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors shadow-lg shadow-blue-600/20 cursor-pointer"
              >
                {investigating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                {investigating ? 'Investigating...' : 'Start Agentic Investigation'}
              </button>
            )}
          </div>

          {/* Quick Preset Buttons */}
          <div className="mt-3.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span className="text-slate-500">Exhibition Presets:</span>
            <button
              onClick={() => {
                const url = 'https://github.com/github-dna-demos/retail-core-sample';
                setRepoUrl(url);
                handleAnalyze(url);
              }}
              className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-cyan-300 font-mono transition-colors border border-slate-700/50 cursor-pointer"
            >
              retail-core-sample (Logic Bug & Fix Demo)
            </button>
            <button
              onClick={() => {
                const url = 'https://github.com/pallets/click';
                setRepoUrl(url);
                handleAnalyze(url);
              }}
              className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-mono transition-colors border border-slate-700/50 cursor-pointer"
            >
              pallets/click (Large Production Codebase)
            </button>
          </div>

          {/* Rate Limit or Error Banner */}
          {errorMessage && (
            <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{errorMessage}</span>
            </div>
          )}

          {investigation?.status === 'llm_unavailable' && (
            <div className="mt-4 p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-start gap-3">
              <Clock className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <strong className="font-semibold text-amber-300 block mb-0.5">Groq Rate Limit Encountered</strong>
                <span>{investigation.note || 'The AI model reached rate limits or quota boundaries. Completed AST structural analysis is safely preserved below.'}</span>
              </div>
            </div>
          )}
        </section>

        {/* Workflow Progression Stepper */}
        {analysis && (
          <section className="bg-[#0b101c] border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between text-xs overflow-x-auto pb-1 gap-4">
              <div className="flex items-center gap-2 text-emerald-400 shrink-0">
                <CheckCircle2 className="w-4 h-4" />
                <span className="font-semibold">AST Ingestion</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />

              <div className={`flex items-center gap-2 shrink-0 ${
                investigation?.plan ? 'text-emerald-400 font-semibold' :
                investigation?.status === 'llm_unavailable' ? 'text-amber-400 font-semibold' :
                investigating ? 'text-cyan-400 animate-pulse' : 'text-slate-500'
              }`}>
                {investigation?.plan ? <CheckCircle2 className="w-4 h-4" /> :
                 investigation?.status === 'llm_unavailable' ? <Clock className="w-4 h-4 text-amber-400" /> :
                 <div className="w-2 h-2 rounded-full bg-current" />}
                <span>Planner Selected Target</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />

              <div className={`flex items-center gap-2 shrink-0 ${
                investigation?.finding ? 'text-emerald-400 font-semibold' :
                investigation?.status === 'llm_unavailable' ? 'text-amber-400' :
                investigating ? 'text-cyan-400 animate-pulse' : 'text-slate-500'
              }`}>
                {investigation?.finding ? <CheckCircle2 className="w-4 h-4" /> : <div className="w-2 h-2 rounded-full bg-current" />}
                <span>Tool-Using Investigation</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />

              <div className={`flex items-center gap-2 shrink-0 ${investigation?.stages?.tests_generated ? 'text-emerald-400 font-semibold' : 'text-slate-500'}`}>\n                {investigation?.stages?.tests_generated ? <CheckCircle2 className="w-4 h-4" /> : <div className="w-2 h-2 rounded-full bg-current" />}
                <span>Test Code Generated</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />

              <div className={`flex items-center gap-2 shrink-0 ${
                investigation?.stages?.fix_verified ? 'text-emerald-400 font-semibold' :
                investigation?.stages?.tests_executed ? 'text-rose-400 font-semibold' : 'text-slate-500'
              }`}>
                {investigation?.stages?.fix_verified ? <CheckCircle2 className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
                <span>Docker Sandbox Verification</span>
              </div>
            </div>
          </section>
        )}

        {/* Navigation Tabs */}
        {analysis && (
          <div className="flex border-b border-slate-800 space-x-1 text-sm font-medium">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-4 py-2.5 border-b-2 cursor-pointer flex items-center gap-2 transition-colors ${
                activeTab === 'overview'
                  ? 'border-cyan-500 text-cyan-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              Repository DNA ({analysis.stats.python_files} files)
            </button>

            <button
              onClick={() => setActiveTab('activity')}
              className={`px-4 py-2.5 border-b-2 cursor-pointer flex items-center gap-2 transition-colors ${
                activeTab === 'activity'
                  ? 'border-cyan-500 text-cyan-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-4 h-4" />
              Agent Workflow & Events
              {investigation?.events?.length > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">
                  {investigation.events.length}
                </span>
              )}
            </button>

            {investigation?.finding && (
              <button
                onClick={() => setActiveTab('finding')}
                className={`px-4 py-2.5 border-b-2 cursor-pointer flex items-center gap-2 transition-colors ${
                  activeTab === 'finding'
                    ? 'border-cyan-500 text-cyan-400 font-semibold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Bug className="w-4 h-4" />
                Finding & Proposed Patch
              </button>
            )}

            {investigation?.test_results && (
              <button
                onClick={() => setActiveTab('tests')}
                className={`px-4 py-2.5 border-b-2 cursor-pointer flex items-center gap-2 transition-colors ${
                  activeTab === 'tests'
                    ? 'border-cyan-500 text-cyan-400 font-semibold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Terminal className="w-4 h-4" />
                Container Verification
                {investigation.stages?.fix_verified ? (
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                ) : (
                  <span className="w-2 h-2 rounded-full bg-rose-400"></span>
                )}
              </button>
            )}

            {investigation && (
              <button
                onClick={() => setActiveTab('report')}
                className={`px-4 py-2.5 border-b-2 cursor-pointer flex items-center gap-2 transition-colors ${
                  activeTab === 'report'
                    ? 'border-cyan-500 text-cyan-400 font-semibold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-4 h-4" />
                Structured Audit Report
              </button>
            )}
          </div>
        )}

        {/* Tab 1: Overview & AST Analysis */}
        {analysis && activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-[#0d1322] border border-slate-800/80 rounded-xl p-4">
                <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Python Files</span>
                <p className="text-2xl font-bold font-mono text-cyan-400 mt-1">{analysis.stats.python_files}</p>
                <span className="text-[11px] text-slate-500">AST parsed cleanly</span>
              </div>
              <div className="bg-[#0d1322] border border-slate-800/80 rounded-xl p-4">
                <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Total Functions</span>
                <p className="text-2xl font-bold font-mono text-blue-400 mt-1">{analysis.stats.functions}</p>
                <span className="text-[11px] text-slate-500">Def & AsyncDef blocks</span>
              </div>
              <div className="bg-[#0d1322] border border-slate-800/80 rounded-xl p-4">
                <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Classes</span>
                <p className="text-2xl font-bold font-mono text-indigo-400 mt-1">{analysis.stats.classes}</p>
                <span className="text-[11px] text-slate-500">Object structures</span>
              </div>
              <div className="bg-[#0d1322] border border-slate-800/80 rounded-xl p-4">
                <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Internal Module Edges</span>
                <p className="text-2xl font-bold font-mono text-emerald-400 mt-1">{analysis.stats.internal_edges}</p>
                <span className="text-[11px] text-slate-500">Resolved dependencies</span>
              </div>
            </div>

            {/* Dependency Graph & Internal Modules */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <DependencyGraph graph={analysis.graph} files={analysis.files} />
              </div>

              {/* External Dependencies */}
              <div className="bg-[#0d1322] border border-slate-800 rounded-xl p-5 flex flex-col">
                <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                  <ExternalLink className="w-4 h-4 text-blue-400" />
                  External Dependencies ({analysis.external_imports.length})
                </h3>
                <div className="bg-[#080d18] border border-slate-800/80 rounded-lg p-3 flex-1 overflow-y-auto max-h-[520px]">
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.external_imports.map((pkg, idx) => (
                      <span key={idx} className="px-2 py-1 rounded bg-slate-800 text-slate-300 font-mono text-xs border border-slate-700/50">
                        {pkg}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Python Files List */}
            <div className="bg-[#0d1322] border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <FileCode className="w-4 h-4 text-cyan-400" />
                Discovered Python Files
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900/80 text-slate-400 uppercase font-mono border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">File Path</th>
                      <th className="py-2.5 px-3">Lines</th>
                      <th className="py-2.5 px-3">Functions</th>
                      <th className="py-2.5 px-3">Classes</th>
                      <th className="py-2.5 px-3">Imports</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {analysis.files.map((file, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-2 px-3 text-cyan-300 font-medium">{file.path}</td>
                        <td className="py-2 px-3 text-slate-400">{file.lines}</td>
                        <td className="py-2 px-3 text-blue-400">{file.functions.length}</td>
                        <td className="py-2 px-3 text-indigo-400">{file.classes.length}</td>
                        <td className="py-2 px-3 text-slate-500">{file.imports.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Agent Workflow & Activity */}
        {activeTab === 'activity' && (
          <div className="space-y-6">
            {/* Rate limit warning card if applicable */}
            {investigation?.status === 'llm_unavailable' && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs">
                <div className="flex items-center gap-2 mb-1.5 font-semibold text-amber-300">
                  <AlertOctagon className="w-4 h-4 text-amber-400" />
                  <span>Investigation Incomplete — LLM Rate Limit Enforced</span>
                </div>
                <p className="leading-relaxed text-slate-300">
                  {investigation.note}
                </p>
                {investigation.rate_limit?.message && (
                  <p className="mt-2 text-[11px] font-mono text-amber-300/80 bg-black/40 p-2 rounded border border-amber-500/20">
                    Provider response: {investigation.rate_limit.message}
                  </p>
                )}
              </div>
            )}

            {/* Planner Card */}
            {investigation?.plan && (
              <div className="bg-[#0d1322] border border-cyan-800/40 rounded-xl p-5 glow-cyan">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-cyan-950 text-cyan-400 uppercase tracking-wider font-mono">
                      Agent B: Planner
                    </span>
                    <h3 className="text-sm font-semibold text-white">Target Selection Decision</h3>
                  </div>
                  <span className="text-xs font-mono text-cyan-400 font-medium">{investigation.plan.file}</span>
                </div>
                <p className="text-xs text-slate-300 mb-2">
                  <span className="text-slate-500">Reasoning: </span>{investigation.plan.reason}
                </p>
                <p className="text-xs text-slate-400">
                  <span className="text-slate-500">Focus: </span>{investigation.plan.focus}
                </p>
              </div>
            )}

            {/* Live Events Stream */}
            <div className="bg-[#0d1322] border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-cyan-400" />
                  Agent Execution Trace & Tool Invocations
                </h3>
                <span className="text-xs text-slate-500 font-mono">
                  {investigation?.events?.length || 0} events recorded
                </span>
              </div>

              <div className="space-y-2.5 font-mono text-xs max-h-[500px] overflow-y-auto pr-1">
                {investigation?.events?.map((ev, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-[#080d18] border border-slate-800/80 flex items-start gap-3">
                    <span className="text-slate-500 text-[11px] shrink-0">{ev.time}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${
                      ev.agent === 'planner' ? 'bg-cyan-950 text-cyan-400 border border-cyan-800/50' :
                      ev.agent === 'investigator' ? 'bg-blue-950 text-blue-400 border border-blue-800/50' :
                      ev.agent === 'verifier' ? 'bg-indigo-950 text-indigo-400 border border-indigo-800/50' :
                      ev.agent === 'test_agent' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50' :
                      'bg-slate-800 text-slate-400'
                    }`}>
                      {ev.agent}
                    </span>
                    <span className="text-slate-300 font-semibold shrink-0 text-cyan-300">{ev.action}</span>
                    <span className="text-slate-400 break-all text-[11px]">{ev.detail}</span>
                  </div>
                ))}

                {investigating && (
                  <div className="p-3 rounded-lg bg-cyan-950/20 border border-cyan-800/30 text-cyan-300 flex items-center gap-2 text-xs">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Agent is actively inspecting repository AST and invoking tools...</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Finding & Proposed Patch */}
        {activeTab === 'finding' && investigation?.finding && (
          <div className="space-y-6">
            <div className="bg-[#0d1322] border border-slate-800 rounded-xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                      investigation.finding.severity === 'high' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                      investigation.finding.severity === 'medium' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    }`}>
                      {investigation.finding.severity} Severity
                    </span>
                    <span className="text-xs text-slate-400 font-mono">Confidence: {investigation.finding.confidence}</span>
                  </div>
                  <h2 className="text-lg font-bold text-white">{investigation.finding.title || 'Potential Defect Detected'}</h2>
                </div>

                {/* Grounding Verification Badge */}
                <div>
                  {investigation.finding.evidence_verified ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Grounding Verified: Verbatim Code in Repo
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Unconfirmed Quote
                    </span>
                  )}
                </div>
              </div>

              <div className="text-xs text-slate-300 leading-relaxed mb-6 bg-[#080d18] p-4 rounded-lg border border-slate-800">
                <span className="text-slate-500 font-semibold block mb-1">EXPLANATION & ANALYSIS:</span>
                {investigation.finding.explanation}
              </div>

              {/* Affected File & Evidence */}
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>File: <strong className="text-cyan-300">{investigation.finding.file}</strong></span>
                  <span>Lines: {investigation.finding.start_line} - {investigation.finding.end_line}</span>
                </div>

                <div className="bg-[#050811] rounded-lg border border-slate-800 overflow-hidden font-mono text-xs">
                  <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-slate-400">
                    <span>Quoted Buggy Source Evidence</span>
                    <button onClick={() => copyToClipboard(investigation.finding.evidence)} className="hover:text-white cursor-pointer">
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <pre className="p-4 text-rose-300 overflow-x-auto">
                    <code>{investigation.finding.evidence || '// No raw evidence snippet'}</code>
                  </pre>
                </div>

                {/* Proposed Fix */}
                {investigation.finding.proposed_fix && (
                  <div className="bg-[#050811] rounded-lg border border-slate-800 overflow-hidden font-mono text-xs">
                    <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-slate-400">
                      <span>Proposed Replacement Fix</span>
                      <button onClick={() => copyToClipboard(investigation.finding.proposed_fix)} className="hover:text-white cursor-pointer">
                        {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <pre className="p-4 text-emerald-300 overflow-x-auto">
                      <code>{investigation.finding.proposed_fix}</code>
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Container Verification */}
        {activeTab === 'tests' && investigation?.test_results && (
          <div className="space-y-6">
            <div className="bg-[#0d1322] border border-slate-800 rounded-xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Shield className="w-5 h-5 text-cyan-400" />
                    Isolated Docker Test Verification Results
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Untrusted repository code and test scripts executed inside <code className="text-cyan-300">python:3.12-slim</code> container with <code className="text-amber-300">--network none</code> and memory caps.
                  </p>
                </div>
                <div>{getStatusBadge(investigation.status)}</div>
              </div>

              {/* Execution Outputs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                {/* Baseline Run */}
                <div className="bg-[#080d18] border border-slate-800 rounded-lg p-4 font-mono text-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-slate-300">1. Baseline Run (Unpatched Repo)</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                      investigation.test_results.baseline.status === 'passed' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'
                    }`}>
                      {investigation.test_results.baseline.status} (exit {investigation.test_results.baseline.exit_code})
                    </span>
                  </div>
                  <pre className="p-3 bg-black/60 rounded text-slate-400 overflow-x-auto h-48 max-h-48 text-[11px] whitespace-pre-wrap">
                    {investigation.test_results.baseline.stdout || investigation.test_results.baseline.stderr || 'No stdout/stderr'}
                  </pre>
                </div>

                {/* Patched Run */}
                <div className="bg-[#080d18] border border-slate-800 rounded-lg p-4 font-mono text-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-slate-300">2. Patched Run (Fix Applied in Sandbox)</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                      investigation.test_results.patched.status === 'passed' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'
                    }`}>
                      {investigation.test_results.patched.status} (exit {investigation.test_results.patched.exit_code})
                    </span>
                  </div>
                  <pre className="p-3 bg-black/60 rounded text-slate-400 overflow-x-auto h-48 max-h-48 text-[11px] whitespace-pre-wrap">
                    {investigation.test_results.patched.stdout || investigation.test_results.patched.stderr || 'No stdout/stderr'}
                  </pre>
                </div>
              </div>

              {/* Generated Test Code */}
              <div className="mt-6 bg-[#050811] rounded-lg border border-slate-800 overflow-hidden font-mono text-xs">
                <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-slate-400">
                  <span>Generated Test Script (<code className="text-cyan-300">test_dna_verification.py</code>)</span>
                  <button onClick={() => copyToClipboard(investigation.test_results.test_code)} className="hover:text-white cursor-pointer">
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <pre className="p-4 text-cyan-300 overflow-x-auto">
                  <code>{investigation.test_results.test_code}</code>
                </pre>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Structured Final Report */}
        {activeTab === 'report' && investigation && (
          <div className="bg-[#0d1322] border border-slate-800 rounded-xl p-8 max-w-4xl mx-auto space-y-6">
            <div className="border-b border-slate-800 pb-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white font-mono">GitHub DNA Investigation Report</h2>
                <p className="text-xs text-slate-400 mt-1">Repository: {repoMeta?.url}</p>
              </div>
              <div>{getStatusBadge(investigation.status)}</div>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-4 rounded-lg bg-[#080d18] border border-slate-800">
                <h4 className="font-semibold text-slate-200 mb-2 uppercase tracking-wider text-[11px] text-cyan-400">Executive Summary</h4>
                <p className="text-slate-300 leading-relaxed">
                  {investigation.status === 'llm_unavailable' || investigation.status === 'investigation_incomplete' ? (
                    investigation.note
                  ) : (
                    'The automated GitHub DNA agent evaluated repository AST structure, selected high-risk modules through Planner reasoning, inspected candidate code with read/outline tools, and tested the proposed resolution inside an isolated Docker container with zero network access.'
                  )}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-[#080d18] border border-slate-800">
                  <h4 className="font-semibold text-slate-400 mb-2 uppercase tracking-wider text-[11px]">Workflow Stages</h4>
                  <ul className="space-y-1 font-mono text-[11px]">
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Potential Issue Detected:</span>
                      <strong className={investigation.stages?.potential_issue_detected ? 'text-emerald-400' : 'text-slate-500'}>
                        {String(investigation.stages?.potential_issue_detected)}
                      </strong>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Fix Proposed:</span>
                      <strong className={investigation.stages?.fix_proposed ? 'text-emerald-400' : 'text-slate-500'}>
                        {String(investigation.stages?.fix_proposed)}
                      </strong>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Tests Generated:</span>
                      <strong className={investigation.stages?.tests_generated ? 'text-emerald-400' : 'text-slate-500'}>
                        {String(investigation.stages?.tests_generated)}
                      </strong>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Tests Executed in Sandbox:</span>
                      <strong className={investigation.stages?.tests_executed ? 'text-emerald-400' : 'text-slate-500'}>
                        {String(investigation.stages?.tests_executed)}
                      </strong>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Fix Verified:</span>
                      <strong className={investigation.stages?.fix_verified ? 'text-emerald-400' : 'text-slate-500'}>
                        {String(investigation.stages?.fix_verified)}
                      </strong>
                    </li>
                  </ul>
                </div>

                <div className="p-4 rounded-lg bg-[#080d18] border border-slate-800">
                  <h4 className="font-semibold text-slate-400 mb-2 uppercase tracking-wider text-[11px]">Inspection Evidence</h4>
                  <ul className="space-y-1 font-mono text-[11px]">
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Target File:</span>
                      <span className="text-cyan-300 truncate max-w-[180px]">{investigation.finding?.file || investigation.plan?.file || 'N/A'}</span>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Line Span:</span>
                      <span>{investigation.finding?.start_line || 0} - {investigation.finding?.end_line || 0}</span>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Verbatim Match:</span>
                      <strong className={investigation.finding?.evidence_verified ? 'text-emerald-400' : 'text-amber-400'}>
                        {investigation.finding?.evidence_verified ? 'Yes (Verified)' : 'N/A'}
                      </strong>
                    </li>
                    <li className="flex items-center justify-between text-slate-300">
                      <span>Model Used:</span>
                      <span className="text-slate-400">{investigation.model}</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300/90 text-xs">
                <strong>Limitations & Exhibition Disclaimers:</strong>
                <p className="mt-1 leading-relaxed text-slate-400 text-[11px]">
                  Passing a focused unit test validates the specific condition tested, but does not guarantee the entire repository is defect-free. All proposed code modifications remain isolated within the sandbox and are never committed or pushed to the upstream GitHub repository.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
