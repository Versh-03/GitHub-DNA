import React, { useState, useMemo } from 'react';
import { Layers, Search, X } from 'lucide-react';

export default function DependencyGraph({ graph }) {
  const [searchTerm, setSearchTerm] = useState('');

  const rawNodes = useMemo(() => graph?.nodes || [], [graph]);
  const rawEdges = useMemo(() => graph?.edges || [], [graph]);

  // Remove duplicate edges, then apply the search filter
  const edges = useMemo(() => {
    const seen = new Set();
    const q = searchTerm.trim().toLowerCase();
    return rawEdges.filter(e => {
      const key = `${e.source}-->${e.target}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return !q || e.source.toLowerCase().includes(q) || e.target.toLowerCase().includes(q);
    });
  }, [rawEdges, searchTerm]);

  const isolatedCount = useMemo(() => {
    const connected = new Set();
    rawEdges.forEach(e => { connected.add(e.source); connected.add(e.target); });
    return rawNodes.filter(n => !connected.has(n.id)).length;
  }, [rawNodes, rawEdges]);

  return (
    <div className="bg-[#0d1322] border border-slate-800 rounded-xl overflow-hidden flex flex-col shadow-xl">
      <div className="border-b border-slate-800/90 bg-[#0a0f1c] px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-100 font-mono">Module Dependencies</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
            {rawNodes.length} modules • {rawEdges.length} import edges
          </span>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search module..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="bg-[#0b101d] border border-slate-700/80 rounded-md pl-8 pr-8 py-1.5 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500 w-56"
          />
          {searchTerm && (
            <button onClick={() => setSearchTerm('')} className="absolute right-2 top-2 text-slate-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="p-4 bg-[#080d18] min-h-[300px] max-h-[520px] overflow-y-auto">
        <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
          <span>{isolatedCount} modules have no internal imports or importers</span>
          <span className="font-mono">{edges.length} shown</span>
        </div>

        {edges.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
            {edges.map((edge, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded bg-slate-900/90 border border-slate-800 flex items-center justify-between hover:border-slate-700 transition-colors"
              >
                <span className="text-cyan-300 truncate max-w-[45%]" title={edge.source}>{edge.source}</span>
                <span className="text-slate-500 font-sans text-[10px] px-1 shrink-0">→ imports →</span>
                <span className="text-blue-400 truncate max-w-[45%]" title={edge.target}>{edge.target}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-slate-500 text-xs">
            {rawEdges.length === 0
              ? 'No internal cross-module imports were found.'
              : 'No modules match your search.'}
          </div>
        )}
      </div>
    </div>
  );
}
