import { useState, useEffect, useRef, useCallback } from 'react'
import { ReactFlow, Controls, Background, applyNodeChanges, applyEdgeChanges, type Node, type Edge, type NodeChange, type EdgeChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import axios from 'axios'
import { Play, FileCode2, Network, Terminal } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const API_BASE = 'http://localhost:8000/api/v1'

interface Repo {
  id: string
  name: string
  path: string
  analysis_status: string
}

function App() {
  const [repos, setRepos] = useState<Repo[]>([])
  const [activeRepo, setActiveRepo] = useState<Repo | null>(null)
  
  // Graph State
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  
  // Chat State
  const [messages, setMessages] = useState<{type: string, content: string}[]>([])
  const [input, setInput] = useState("")
  const wsRef = useRef<WebSocket | null>(null)
  const chatContainerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages])

  useEffect(() => {
    fetchRepos()
  }, [])

  const fetchRepos = async () => {
    try {
      const res = await axios.get(`${API_BASE}/repositories`)
      setRepos(res.data)
      if (res.data.length > 0) {
        selectRepo(res.data[0])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadGraph = async (repoId: string) => {
    try {
      const res = await axios.get(`${API_BASE}/repositories/${repoId}/graph`)
      const fetchedNodes = res.data.nodes.map((n: any) => ({
        id: n.id,
        data: { label: n.label },
        position: { x: Math.random() * 500, y: Math.random() * 500 },
        style: { background: n.type === 'CLASS' ? '#3b82f6' : '#10b981', color: 'white', border: 'none', borderRadius: '8px', padding: '10px' }
      }))
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

  const selectRepo = (repo: Repo) => {
    setActiveRepo(repo)
    loadGraph(repo.id)
    setMessages([])
    
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

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current) return
    setMessages(prev => [...prev, { type: 'user', content: input }])
    wsRef.current.send(input)
    setInput("")
  }

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  )
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  return (
    <div className="h-screen w-screen flex bg-slate-900 text-slate-100 overflow-hidden font-sans">
      
      {/* Sidebar */}
      <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-4 border-b border-slate-700">
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent flex items-center gap-2">
            <Network className="text-teal-400" />
            Ripple AI
          </h1>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
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
              <div className="text-sm text-slate-500 text-center py-4">No repos found.<br/>Run `setup_sample_repo.py`</div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {activeRepo ? (
          <>
            {/* Top Bar */}
            <div className="h-14 bg-slate-800/80 backdrop-blur-md border-b border-slate-700 flex items-center px-6 z-10 absolute top-0 left-0 right-0">
              <span className="font-semibold text-slate-200">{activeRepo.name}</span>
              <span className="ml-3 px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-300">{activeRepo.path}</span>
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
                  fitView
                >
                  <Background color="#334155" gap={16} />
                  <Controls className="bg-slate-800 border-slate-700 fill-slate-300" />
                </ReactFlow>
              </div>

              {/* Chat Area */}
              <div className="w-[420px] h-full border-l border-slate-700 bg-slate-800/90 backdrop-blur-xl flex flex-col shadow-2xl overflow-hidden">
                <div className="p-4 border-b border-slate-700 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal size={18} className="text-teal-400"/>
                    <h3 className="font-semibold text-slate-200">AI Detective</h3>
                  </div>
                  <span className="text-[11px] text-slate-400 bg-slate-700/60 px-2 py-0.5 rounded">Scrollable</span>
                </div>
                
                <div ref={chatContainerRef} className="flex-1 overflow-y-scroll p-4 space-y-4 custom-scrollbar min-h-0">
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
                  {messages.length === 0 && (
                    <div className="text-center text-slate-500 mt-10 text-sm">
                      Ask me to investigate a bug, analyze the impact of a PR, or explain a dependency chain.
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
                      placeholder="E.g., Why did test_authenticate fail?"
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-slate-200"
                    />
                    <button 
                      onClick={sendMessage}
                      className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg p-2 transition-colors"
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
