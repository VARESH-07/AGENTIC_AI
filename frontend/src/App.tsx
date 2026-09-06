import { useState, useEffect, useRef, useCallback } from 'react'
import { ReactFlow, Controls, Background, applyNodeChanges, applyEdgeChanges, type Node, type Edge, type NodeChange, type EdgeChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import axios from 'axios'
import { Play, FileCode2, Network, Terminal, ShieldAlert, CheckCircle2, AlertTriangle, Layers, X, Info, Plus, GitBranch, FolderOpen, Loader2, RefreshCw } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const API_BASE = 'http://localhost:8000/api/v1'

interface Repo {
  id: string
  name: string
  path: string
  analysis_status: string
}

interface EvidenceItem {
  type: string
  summary: string
  details?: any
}

interface ImpactChain {
  target: string
  chain: string[]
  affected_functions: string[]
  affected_files: string[]
}

interface RiskAssessment {
  level: string
  score: number
  reasons: string[]
}

interface RootCause {
  status: string
  explanation: string
  confidence: string
}

interface InvestigationResult {
  query: string
  target: string
  impact: ImpactChain
  root_cause: RootCause
  risk: RiskAssessment
  evidence: EvidenceItem[]
  affected_files: string[]
  affected_functions: string[]
  trace: string[]
}

interface FunctionImpactResult {
  analysis_type: string
  repository_id: string
  target: string
  impact: ImpactChain
  risk: RiskAssessment
  tests: any[]
}

interface RippleImpactResult {
  analysis_type: string
  repository_id: string
  repository: string
  target_module: string
  affected_modules: string[]
  affected_functions: string[]
  affected_tests: string[]
  impact_chain: string[]
  risk: string
  risk_score: number
  reasons: string[]
  reason?: string
}

function App() {
  const [repos, setRepos] = useState<Repo[]>([])
  const [activeRepo, setActiveRepo] = useState<Repo | null>(null)
  
  // Graph State
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [selectedNode, setSelectedNode] = useState<any | null>(null)
  
  // Chat & Investigation State
  const [messages, setMessages] = useState<{type: string, content: string}[]>([])
  const [input, setInput] = useState("")
  const [investigationResult, setInvestigationResult] = useState<InvestigationResult | null>(null)
  const [isInvestigating, setIsInvestigating] = useState(false)

  // Direct Node Analysis States
  const [functionImpactResult, setFunctionImpactResult] = useState<FunctionImpactResult | null>(null)
  const [rippleImpactResult, setRippleImpactResult] = useState<RippleImpactResult | null>(null)
  const [activeAnalysisType, setActiveAnalysisType] = useState<'function' | 'ripple' | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<string | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  // Import Modal State
  const [isImportOpen, setIsImportOpen] = useState(false)
  const [importType, setImportType] = useState<'url' | 'path'>('url')
  const [importGitUrl, setImportGitUrl] = useState('')
  const [importLocalPath, setImportLocalPath] = useState('')
  const [isImporting, setIsImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  
  const wsRef = useRef<WebSocket | null>(null)
  const chatContainerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages, functionImpactResult, rippleImpactResult, analysisStatus, analysisError])

  useEffect(() => {
    fetchRepos()
  }, [])

  const fetchRepos = async () => {
    try {
      const res = await axios.get(`${API_BASE}/repositories`)
      setRepos(res.data)
      if (res.data.length > 0 && !activeRepo) {
        selectRepo(res.data[0])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setImportError(null)
    setIsImporting(true)

    try {
      const payload = importType === 'url' 
        ? { git_url: importGitUrl } 
        : { path: importLocalPath }

      const res = await axios.post(`${API_BASE}/repositories`, payload)
      const newRepo: Repo = res.data
      
      await fetchRepos()
      selectRepo(newRepo)
      setIsImportOpen(false)
      setImportGitUrl('')
      setImportLocalPath('')
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Failed to import repository"
      setImportError(msg)
    } finally {
      setIsImporting(false)
    }
  }

  const loadGraph = async (repoId: string, highlightNodes: string[] = [], highlightType: 'function' | 'ripple' = 'function') => {
    try {
      const res = await axios.get(`${API_BASE}/repositories/${repoId}/graph`)
      const rawNodes = res.data.nodes || []
      const fetchedNodes = rawNodes.map((n: any, index: number) => {
        const isImpacted = highlightNodes.some(h => 
          h === n.label || h === n.id || h === n.name || h === n.file_path || (n.file_path && n.file_path.endsWith(h))
        )
        const isModule = ['FILE', 'MODULE', 'PACKAGE'].includes(String(n.type).toUpperCase())

        let bg = isModule ? '#8b5cf6' : n.type === 'CLASS' ? '#3b82f6' : '#10b981'
        let border = 'none'
        let boxShadow = 'none'

        if (isImpacted) {
          if (highlightType === 'function') {
            bg = '#ef4444'
            border = '2px solid #fca5a5'
            boxShadow = '0 0 15px rgba(239, 68, 68, 0.6)'
          } else {
            bg = '#f59e0b'
            border = '2px solid #fde68a'
            boxShadow = '0 0 15px rgba(245, 158, 11, 0.7)'
          }
        }

        // Calculate sparse architectural grid positions (Modules -> Classes -> Functions)
        const typeStr = String(n.type || '').toUpperCase()
        let tier = 2
        if (['FILE', 'MODULE', 'PACKAGE'].includes(typeStr)) tier = 0
        else if (['CLASS', 'INTERFACE'].includes(typeStr)) tier = 1

        const sameTierNodes = rawNodes.filter((item: any) => {
          const t = String(item.type || '').toUpperCase()
          if (tier === 0) return ['FILE', 'MODULE', 'PACKAGE'].includes(t)
          if (tier === 1) return ['CLASS', 'INTERFACE'].includes(t)
          return !['FILE', 'MODULE', 'PACKAGE', 'CLASS', 'INTERFACE'].includes(t)
        })

        const itemIndexInTier = sameTierNodes.findIndex((item: any) => item.id === n.id)
        const colsPerRow = Math.max(3, Math.ceil(Math.sqrt(sameTierNodes.length * 1.8)))
        const col = itemIndexInTier >= 0 ? itemIndexInTier % colsPerRow : index % 4
        const row = itemIndexInTier >= 0 ? Math.floor(itemIndexInTier / colsPerRow) : Math.floor(index / 4)

        const posX = col * 380 + (row % 2 === 1 ? 50 : 0)
        const posY = tier * 320 + row * 220

        return {
          id: n.id,
          type: n.type,
          data: { 
            label: n.label, 
            name: n.name || n.label,
            qualified_name: n.qualified_name,
            type: n.type,
            repository_id: repoId,
            repository_name: activeRepo?.name || '',
            file_path: n.file_path || n.properties?.file_path,
            fullData: n 
          },
          position: { x: posX, y: posY },
          style: {
            background: bg,
            color: 'white',
            border: border,
            borderRadius: '8px',
            padding: '12px 18px',
            fontWeight: 500,
            fontSize: '13px',
            boxShadow: boxShadow
          }
        }
      })

      const fetchedEdges = res.data.edges.map((e: any, i: number) => ({
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: e.type,
        animated: true,
      }))
      setNodes(fetchedNodes)
      setEdges(fetchedEdges)
    } catch (e) {
      console.error(e)
    }
  }

  const clearAnalysisState = () => {
    setFunctionImpactResult(null)
    setRippleImpactResult(null)
    setActiveAnalysisType(null)
    setAnalysisStatus(null)
    setAnalysisError(null)
  }

  const handleClearAnalysis = () => {
    clearAnalysisState()
    if (activeRepo) {
      loadGraph(activeRepo.id)
    }
  }

  const selectRepo = (repo: Repo) => {
    setActiveRepo(repo)
    clearAnalysisState()
    loadGraph(repo.id)
    setMessages([])
    setInvestigationResult(null)
    setSelectedNode(null)
    
    if (wsRef.current) {
      wsRef.current.close()
    }
    
    // Connect WebSocket
    const ws = new WebSocket(`ws://localhost:8000/api/v1/investigate/${repo.id}`)
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setMessages(prev => [...prev, { type: data.type, content: data.message }])
      } catch (e) {
        console.error(e)
      }
    }
    wsRef.current = ws
  }

  // History State
  const [recentHistory, setRecentHistory] = useState<any[]>([])

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API_BASE}/investigations/history?limit=5`)
      setRecentHistory(res.data.investigations || [])
    } catch (e) {
      console.error(e)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !activeRepo) return
    const query = input
    setMessages(prev => [...prev, { type: 'user', content: query }])
    setInput("")
    setIsInvestigating(true)

    // Trigger structured HTTP Investigation API simultaneously
    try {
      const res = await axios.post(`${API_BASE}/investigate`, {
        repository_id: activeRepo.id,
        query: query
      })
      const resultData: InvestigationResult = res.data
      setInvestigationResult(resultData)
      
      if (resultData.affected_functions) {
        loadGraph(activeRepo.id, resultData.affected_functions, 'function')
      }
      fetchHistory()
    } catch (e) {
      console.error("API Investigation Error:", e)
    } finally {
      setIsInvestigating(false)
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(query)
    }
  }

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  )
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  const handleNodeClick = async (_: any, node: Node) => {
    const nodeData = node.data || {}
    const fullData = (nodeData.fullData as any) || node
    setSelectedNode(fullData)

    const repoId = activeRepo?.id
    if (!repoId) {
      setAnalysisError("Please select a repository.")
      return
    }

    // Clear previous impact results to ensure ONLY one active impact analysis is displayed
    setFunctionImpactResult(null)
    setRippleImpactResult(null)
    setAnalysisError(null)

    const nodeType = String(nodeData.type || fullData.type || '').toUpperCase()
    const nodeName = String(nodeData.name || nodeData.label || fullData.name || fullData.label || '')
    const filePath = nodeData.file_path || fullData.file_path || fullData.properties?.file_path

    const isModuleNode = ['FILE', 'MODULE', 'PACKAGE'].includes(nodeType)

    if (isModuleNode) {
      // Trigger RIPPLE IMPACT ANALYSIS for MODULE/FILE node
      setActiveAnalysisType('ripple')
      setAnalysisStatus("Analyzing ripple impact...")
      try {
        const res = await axios.post(`${API_BASE}/repositories/${repoId}/ripple-impact`, {
          repository_id: repoId,
          module: nodeName,
          target_module: nodeName,
          file_path: filePath
        })
        const data: RippleImpactResult = res.data
        setRippleImpactResult(data)
        const highlights = [...(data.affected_modules || []), ...(data.affected_functions || [])]
        loadGraph(repoId, highlights, 'ripple')
      } catch (err: any) {
        const msg = err.response?.data?.detail || err.message || "Impact analysis failed. Check the backend."
        setAnalysisError(msg)
      } finally {
        setAnalysisStatus(null)
      }
    } else {
      // Trigger FUNCTION IMPACT ANALYSIS for FUNCTION/METHOD node
      setActiveAnalysisType('function')
      setAnalysisStatus("Analyzing function impact...")
      try {
        const res = await axios.post(`${API_BASE}/repositories/${repoId}/function-impact`, {
          repository_id: repoId,
          target_symbol: nodeName,
          function: nodeName,
          file_path: filePath,
          symbol_id: node.id
        })
        const data: FunctionImpactResult = res.data
        setFunctionImpactResult(data)
        const highlights = data.impact?.affected_functions || []
        loadGraph(repoId, highlights, 'function')
      } catch (err: any) {
        const msg = err.response?.data?.detail || err.message || "Impact analysis failed. Check the backend."
        setAnalysisError(msg)
      } finally {
        setAnalysisStatus(null)
      }
    }
  }

  return (
    <div className="h-screen w-screen flex bg-slate-900 text-slate-100 overflow-hidden font-sans">
      
      {/* Sidebar */}
      <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-4 border-b border-slate-700 flex items-center justify-between">
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent flex items-center gap-2">
            <Network className="text-teal-400" />
            Ripple AI
          </h1>
        </div>

        <div className="p-3 border-b border-slate-700/60">
          <button
            onClick={() => setIsImportOpen(true)}
            className="w-full bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold py-2 px-3 rounded-lg flex items-center justify-center gap-2 shadow transition-all duration-200"
          >
            <Plus size={16} />
            Import Repository
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-6">
          <div>
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Repositories</h2>
            <div className="space-y-2">
              {repos.map(repo => (
                <button
                  key={repo.id}
                  onClick={() => selectRepo(repo)}
                  className={`w-full text-left p-3 rounded-lg flex items-center gap-3 transition-all duration-200 ${activeRepo?.id === repo.id ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'hover:bg-slate-700/50 text-slate-300 border border-transparent'}`}
                >
                  <FileCode2 size={18} />
                  <div className="truncate">
                    <div className="font-medium truncate">{repo.name}</div>
                    <div className="text-[10px] text-slate-500 truncate">{repo.analysis_status}</div>
                  </div>
                </button>
              ))}
              {repos.length === 0 && (
                <div className="text-sm text-slate-500 text-center py-4">No repos found.<br/>Click "+ Import Repository" above</div>
              )}
            </div>
          </div>

          {/* Recent Diagnoses Widget */}
          {recentHistory.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Recent Diagnoses</h2>
              <div className="space-y-2">
                {recentHistory.map((item, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-700/60 text-xs">
                    <div className="font-medium text-slate-200 truncate">{item.target}</div>
                    <div className="flex items-center justify-between mt-1 text-[10px]">
                      <span className={`px-1.5 py-0.5 rounded font-bold ${
                        item.risk === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                        item.risk === 'HIGH' ? 'bg-orange-500/20 text-orange-400' :
                        item.risk === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'
                      }`}>
                        {item.risk} ({item.risk_score})
                      </span>
                      <span className="text-slate-500">{item.timestamp ? item.timestamp.substring(11, 19) : ''}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Import Modal */}
      <AnimatePresence>
        {isImportOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 10 }}
              className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl relative"
            >
              <button
                onClick={() => setIsImportOpen(false)}
                className="absolute top-4 right-4 text-slate-400 hover:text-white"
              >
                <X size={20} />
              </button>

              <h3 className="text-lg font-bold text-slate-100 mb-1 flex items-center gap-2">
                <Plus className="text-teal-400" size={20} />
                Import Repository
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Clone a public Git repository or link a local project folder for AST analysis.
              </p>

              {/* Tab selector */}
              <div className="flex bg-slate-900 p-1 rounded-lg mb-4 text-xs font-semibold">
                <button
                  onClick={() => setImportType('url')}
                  className={`flex-1 py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-all ${
                    importType === 'url' ? 'bg-slate-700 text-teal-300 shadow' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <GitBranch size={14} /> Git URL
                </button>
                <button
                  onClick={() => setImportType('path')}
                  className={`flex-1 py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-all ${
                    importType === 'path' ? 'bg-slate-700 text-teal-300 shadow' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <FolderOpen size={14} /> Local Directory
                </button>
              </div>

              <form onSubmit={handleImportSubmit} className="space-y-4">
                {importType === 'url' ? (
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Git Repository URL
                    </label>
                    <input
                      type="url"
                      required
                      value={importGitUrl}
                      onChange={e => setImportGitUrl(e.target.value)}
                      placeholder="https://github.com/user/repo.git"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Absolute Folder Path
                    </label>
                    <input
                      type="text"
                      required
                      value={importLocalPath}
                      onChange={e => setImportLocalPath(e.target.value)}
                      placeholder="C:\Users\...\my-project"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
                    />
                  </div>
                )}

                {importError && (
                  <div className="p-2.5 rounded bg-red-500/20 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
                    <AlertTriangle size={14} className="shrink-0" />
                    <span>{importError}</span>
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsImportOpen(false)}
                    className="px-4 py-2 rounded-lg text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isImporting}
                    className="px-4 py-2 rounded-lg text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {isImporting ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      'Import & Analyze'
                    )}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {activeRepo ? (
          <>
            {/* Top Bar */}
            <div className="h-14 bg-slate-800/80 backdrop-blur-md border-b border-slate-700 flex items-center px-6 z-10 absolute top-0 left-0 right-0 justify-between">
              <div className="flex items-center">
                <span className="font-semibold text-slate-200">{activeRepo.name}</span>
                <span className="ml-3 px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-300">{activeRepo.path}</span>
              </div>

              <div className="flex items-center gap-3">
                {(functionImpactResult || rippleImpactResult || activeAnalysisType) && (
                  <button
                    onClick={handleClearAnalysis}
                    className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium px-3 py-1.5 rounded-lg flex items-center gap-1.5 border border-slate-600 shadow transition-all"
                  >
                    <RefreshCw size={14} /> Clear Analysis
                  </button>
                )}

                {functionImpactResult && (
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold flex items-center gap-1 ${
                    functionImpactResult.risk.level === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                    functionImpactResult.risk.level === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                    functionImpactResult.risk.level === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                    'bg-green-500/20 text-green-400 border border-green-500/30'
                  }`}>
                    <ShieldAlert size={14} /> Function Risk: {functionImpactResult.risk.level} ({functionImpactResult.risk.score}/100)
                  </span>
                )}

                {rippleImpactResult && (
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold flex items-center gap-1 ${
                    rippleImpactResult.risk === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                    rippleImpactResult.risk === 'HIGH' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                    rippleImpactResult.risk === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                    'bg-green-500/20 text-green-400 border border-green-500/30'
                  }`}>
                    <ShieldAlert size={14} /> Ripple Risk: {rippleImpactResult.risk} ({rippleImpactResult.risk_score}/100)
                  </span>
                )}

                {!functionImpactResult && !rippleImpactResult && investigationResult && (
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold flex items-center gap-1 ${
                    investigationResult.risk.level === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                    investigationResult.risk.level === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                    investigationResult.risk.level === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                    'bg-green-500/20 text-green-400 border border-green-500/30'
                  }`}>
                    <ShieldAlert size={14} /> Risk: {investigationResult.risk.level} ({investigationResult.risk.score}/100)
                  </span>
                )}
              </div>
            </div>

            {/* Content Area (Graph + Chat) */}
            <div className="flex-1 flex h-[calc(100vh-3.5rem)] mt-14 overflow-hidden">
              
              {/* Graph Area */}
              <div className="flex-1 h-full relative overflow-hidden">
                <ReactFlow 
                  nodes={nodes} 
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onNodeClick={handleNodeClick}
                  fitView
                >
                  <Background color="#334155" gap={16} />
                  <Controls className="bg-slate-800 border-slate-700 fill-slate-300" />
                </ReactFlow>

                {/* Node Click Modal Details Card */}
                {selectedNode && (
                  <div className="absolute bottom-4 left-4 bg-slate-800/95 border border-slate-700 rounded-xl p-4 w-96 shadow-2xl backdrop-blur-md z-20">
                    <div className="flex items-center justify-between border-b border-slate-700 pb-2 mb-2">
                      <div className="font-semibold text-blue-400 flex items-center gap-2">
                        <Info size={16} /> {selectedNode.label || selectedNode.name || 'Node Details'}
                      </div>
                      <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-200">
                        <X size={16} />
                      </button>
                    </div>
                    <div className="text-xs space-y-1.5 text-slate-300">
                      <div><span className="text-slate-500">ID:</span> {selectedNode.id}</div>
                      <div><span className="text-slate-500">Type:</span> <span className="bg-slate-700 px-1.5 py-0.5 rounded text-[10px]">{selectedNode.type}</span></div>
                      {selectedNode.repository && (
                        <div><span className="text-slate-500">Repo:</span> <span className="text-teal-300">{selectedNode.repository}</span></div>
                      )}
                      {selectedNode.properties?.file_path && (
                        <div><span className="text-slate-500">File:</span> {selectedNode.properties.file_path}</div>
                      )}
                      {selectedNode.properties?.line_start && (
                        <div><span className="text-slate-500">Line:</span> {selectedNode.properties.line_start}</div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Chat & Analysis Results Area */}
              <div className="w-[440px] h-full border-l border-slate-700 bg-slate-800/90 backdrop-blur-xl flex flex-col shadow-2xl overflow-hidden">
                <div className="p-4 border-b border-slate-700 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal size={18} className="text-teal-400"/>
                    <h3 className="font-semibold text-slate-200">Ripple AI Workspace</h3>
                  </div>
                  {(functionImpactResult || rippleImpactResult) && (
                    <button 
                      onClick={handleClearAnalysis}
                      className="text-[11px] bg-slate-700 hover:bg-slate-600 text-slate-200 px-2.5 py-1 rounded flex items-center gap-1 transition-all"
                    >
                      <RefreshCw size={12} /> Clear Analysis
                    </button>
                  )}
                </div>
                
                <div ref={chatContainerRef} className="flex-1 overflow-y-scroll p-4 space-y-4 custom-scrollbar min-h-0">
                  
                  {/* Analysis Status / Loading Card */}
                  {analysisStatus && (
                    <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl text-blue-200 text-xs flex items-center gap-2">
                      <Loader2 size={16} className="animate-spin text-blue-400 shrink-0" />
                      <span>{analysisStatus}</span>
                    </motion.div>
                  )}

                  {/* Analysis Error Card */}
                  {analysisError && (
                    <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} className="p-3 bg-red-500/20 border border-red-500/30 rounded-xl text-red-200 text-xs flex items-center gap-2">
                      <AlertTriangle size={16} className="text-red-400 shrink-0" />
                      <span>{analysisError}</span>
                    </motion.div>
                  )}

                  {/* FUNCTION IMPACT ANALYSIS CARD */}
                  {functionImpactResult && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 mb-4">
                      <div className="bg-slate-900/90 border border-red-500/40 rounded-xl p-4 space-y-3 shadow-xl">
                        <div className="flex items-center justify-between border-b border-slate-700/80 pb-2">
                          <span className="text-xs font-bold uppercase text-red-400 flex items-center gap-1.5 tracking-wider">
                            <ShieldAlert size={16} /> FUNCTION IMPACT ANALYSIS
                          </span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            functionImpactResult.risk.level === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                            functionImpactResult.risk.level === 'HIGH' ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            Risk: {functionImpactResult.risk.level} ({functionImpactResult.risk.score}/100)
                          </span>
                        </div>

                        <div>
                          <div className="text-[11px] text-slate-400 uppercase font-semibold">Target Function</div>
                          <div className="text-sm font-mono font-bold text-slate-100">{functionImpactResult.target}</div>
                        </div>

                        {/* Affected Functions */}
                        {functionImpactResult.impact.affected_functions.length > 0 && (
                          <div>
                            <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">Affected Functions ({functionImpactResult.impact.affected_functions.length})</div>
                            <div className="flex flex-wrap gap-1">
                              {functionImpactResult.impact.affected_functions.map((fn, idx) => (
                                <span key={idx} className="bg-red-500/20 border border-red-500/30 text-red-200 font-mono text-[11px] px-2 py-0.5 rounded">
                                  {fn}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Affected Files */}
                        {functionImpactResult.impact.affected_files.length > 0 && (
                          <div>
                            <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">Affected Files ({functionImpactResult.impact.affected_files.length})</div>
                            <div className="flex flex-wrap gap-1">
                              {functionImpactResult.impact.affected_files.map((file, idx) => (
                                <span key={idx} className="bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[11px] px-2 py-0.5 rounded">
                                  {file}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Risk Evidence */}
                        {functionImpactResult.risk.reasons.length > 0 && (
                          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 space-y-1">
                            <div className="text-[11px] text-slate-400 font-semibold uppercase">Risk Reasons</div>
                            {functionImpactResult.risk.reasons.map((r, i) => (
                              <div key={i} className="text-xs text-slate-300 flex items-start gap-1.5">
                                <span className="text-red-400">•</span>
                                <span>{r}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}

                  {/* RIPPLE IMPACT ANALYSIS CARD */}
                  {rippleImpactResult && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 mb-4">
                      <div className="bg-slate-900/90 border border-amber-500/40 rounded-xl p-4 space-y-3 shadow-xl">
                        <div className="flex items-center justify-between border-b border-slate-700/80 pb-2">
                          <span className="text-xs font-bold uppercase text-amber-400 flex items-center gap-1.5 tracking-wider">
                            <Layers size={16} /> RIPPLE IMPACT ANALYSIS
                          </span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            rippleImpactResult.risk === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                            rippleImpactResult.risk === 'HIGH' ? 'bg-amber-500/20 text-amber-400' : 'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            Risk: {rippleImpactResult.risk} ({rippleImpactResult.risk_score}/100)
                          </span>
                        </div>

                        <div>
                          <div className="text-[11px] text-slate-400 uppercase font-semibold">Target Module / File</div>
                          <div className="text-sm font-mono font-bold text-amber-300">{rippleImpactResult.target_module}</div>
                        </div>

                        {/* Impact Chain */}
                        {rippleImpactResult.impact_chain && rippleImpactResult.impact_chain.length > 0 && (
                          <div>
                            <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">Impact Chain</div>
                            <div className="flex items-center flex-wrap gap-1 text-xs font-mono">
                              {rippleImpactResult.impact_chain.map((step, idx) => (
                                <span key={idx} className="flex items-center gap-1">
                                  <span className="bg-amber-500/20 border border-amber-500/30 text-amber-200 px-2 py-0.5 rounded text-[11px]">
                                    {step}
                                  </span>
                                  {idx < rippleImpactResult.impact_chain.length - 1 && <span className="text-slate-500">→</span>}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Affected Modules */}
                        {rippleImpactResult.affected_modules.length > 0 && (
                          <div>
                            <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">Affected Modules ({rippleImpactResult.affected_modules.length})</div>
                            <div className="flex flex-wrap gap-1">
                              {rippleImpactResult.affected_modules.map((mod, idx) => (
                                <span key={idx} className="bg-purple-500/20 border border-purple-500/30 text-purple-200 font-mono text-[11px] px-2 py-0.5 rounded">
                                  {mod}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Affected Functions */}
                        {rippleImpactResult.affected_functions.length > 0 && (
                          <div>
                            <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">Affected Functions ({rippleImpactResult.affected_functions.length})</div>
                            <div className="flex flex-wrap gap-1">
                              {rippleImpactResult.affected_functions.map((fn, idx) => (
                                <span key={idx} className="bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[11px] px-2 py-0.5 rounded">
                                  {fn}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Affected Tests */}
                        {rippleImpactResult.affected_tests && rippleImpactResult.affected_tests.length > 0 && (
                          <div>
                            <div className="text-[11px] text-slate-400 uppercase font-semibold mb-1">Affected Tests ({rippleImpactResult.affected_tests.length})</div>
                            <div className="flex flex-wrap gap-1">
                              {rippleImpactResult.affected_tests.map((test, idx) => (
                                <span key={idx} className="bg-teal-500/20 border border-teal-500/30 text-teal-300 font-mono text-[11px] px-2 py-0.5 rounded">
                                  {test}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Reasons */}
                        {rippleImpactResult.reasons && rippleImpactResult.reasons.length > 0 && (
                          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 space-y-1">
                            <div className="text-[11px] text-slate-400 font-semibold uppercase">Ripple Risk Reasons</div>
                            {rippleImpactResult.reasons.map((r, i) => (
                              <div key={i} className="text-xs text-slate-300 flex items-start gap-1.5">
                                <span className="text-amber-400">•</span>
                                <span>{r}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}

                  {/* Investigation Results Display Card (Chat Diagnoser) */}
                  {investigationResult && !functionImpactResult && !rippleImpactResult && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 mb-4">
                      
                      {/* Root Cause Card */}
                      <div className="bg-slate-900/80 border border-teal-500/30 rounded-xl p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold uppercase text-teal-400 flex items-center gap-1.5">
                            <CheckCircle2 size={14} /> Root Cause ({investigationResult.root_cause.status})
                          </span>
                          <span className="text-[10px] bg-teal-500/20 text-teal-300 px-2 py-0.5 rounded-full">
                            {investigationResult.root_cause.confidence} Confidence
                          </span>
                        </div>
                        <p className="text-xs text-slate-200 leading-relaxed">
                          {investigationResult.root_cause.explanation}
                        </p>
                      </div>

                      {/* Impact Chain Card */}
                      {investigationResult.impact.chain.length > 0 && (
                        <div className="bg-slate-900/80 border border-blue-500/30 rounded-xl p-3 space-y-2">
                          <div className="text-xs font-semibold text-blue-400 flex items-center gap-1.5">
                            <Layers size={14} /> Impact Chain
                          </div>
                          <div className="flex items-center flex-wrap gap-1 text-xs font-mono">
                            {investigationResult.impact.chain.map((step, idx) => (
                              <span key={idx} className="flex items-center gap-1">
                                <span className="bg-blue-500/20 border border-blue-500/30 text-blue-200 px-2 py-0.5 rounded text-[11px]">
                                  {step}
                                </span>
                                {idx < investigationResult.impact.chain.length - 1 && <span className="text-slate-500">→</span>}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Evidence List */}
                      {investigationResult.evidence.length > 0 && (
                        <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-3 space-y-2">
                          <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                            <AlertTriangle size={14} className="text-amber-400" /> Evidence Collected ({investigationResult.evidence.length})
                          </div>
                          <div className="space-y-1.5">
                            {investigationResult.evidence.map((ev, i) => (
                              <div key={i} className="text-xs bg-slate-800/80 border border-slate-700/60 p-2 rounded flex items-start gap-2">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-700 text-teal-300">
                                  {ev.type}
                                </span>
                                <span className="text-slate-300 leading-snug flex-1">{ev.summary}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                    </motion.div>
                  )}

                  {/* Messages Timeline */}
                  <AnimatePresence>
                    {messages.map((msg, i) => (
                      <motion.div 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        key={i} 
                        className={`p-3 rounded-lg text-sm border whitespace-pre-wrap break-words ${
                          msg.type === 'user' ? 'bg-blue-500/20 border-blue-500/30 text-blue-100 ml-8 rounded-tr-none' :
                          msg.type === 'action' ? 'bg-amber-500/10 border-amber-500/20 text-amber-200/80 font-mono text-xs mr-8' :
                          msg.type === 'thought' ? 'bg-slate-700/50 border-slate-600 text-slate-300 mr-8 italic' :
                          msg.type === 'error' ? 'bg-red-500/20 border-red-500/30 text-red-200 mr-8' :
                          msg.type === 'final' ? 'bg-teal-500/20 border-teal-500/30 text-teal-100 mr-8 rounded-tl-none' :
                          'bg-slate-700/30 border-slate-600 text-slate-400 text-xs text-center mx-12'
                        }`}
                      >
                        {msg.content}
                      </motion.div>
                    ))}
                  </AnimatePresence>

                  {messages.length === 0 && !investigationResult && !functionImpactResult && !rippleImpactResult && (
                    <div className="text-center text-slate-500 mt-10 text-sm">
                      Select a node in React Flow to analyze function impact or module ripple impact, or ask the agent to investigate a query.
                    </div>
                  )}
                </div>
                
                <div className="p-4 border-t border-slate-700 bg-slate-900/50">
                  <div className="flex gap-2">
                    <input 
                      type="text" 
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && sendMessage()}
                      placeholder="E.g., Why did changing process_payment() break checkout?"
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-slate-200"
                      disabled={isInvestigating}
                    />
                    <button 
                      onClick={sendMessage}
                      disabled={isInvestigating}
                      className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg p-2 transition-colors disabled:opacity-50"
                    >
                      <Play size={18} fill="currentColor"/>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500">
            <div className="text-center">
              <Network size={64} className="mx-auto mb-4 opacity-20" />
              <h2 className="text-xl">Select a repository to begin</h2>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
