// @ts-nocheck
"use client";

import { useState, useRef, useEffect } from 'react';

// Basic types for A2UI schemas
type A2UIComponent = {
  type: string;
  title?: string;
  content?: string;
  price?: number;
  deepLink?: string;
  components?: A2UIComponent[];
};

type SessionInfo = {
  id: string;
  name: string;
};

export default function Home() {
  const [messages, setMessages] = useState<{role: string, text: string, components?: A2UIComponent[], logs?: string[]}[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [isLoaded, setIsLoaded] = useState(false);
  const [sessionList, setSessionList] = useState<SessionInfo[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    const list = localStorage.getItem('travel_planner_sessions');
    let loadedList: SessionInfo[] = [];
    if (list) {
      try { loadedList = JSON.parse(list); } catch (e) {}
    }
    setSessionList(loadedList);
    
    let activeSessionId = localStorage.getItem('travel_planner_active_session');
    
    // Migration from the old single-session state
    if (!activeSessionId && loadedList.length === 0) {
       const legacyMessages = localStorage.getItem('travel_planner_messages');
       const legacySession = localStorage.getItem('travel_planner_session_id');
       if (legacySession && legacyMessages) {
          activeSessionId = legacySession;
          loadedList = [{ id: legacySession, name: "Legacy Session" }];
          setSessionList(loadedList);
          localStorage.setItem('travel_planner_sessions', JSON.stringify(loadedList));
          localStorage.setItem(`tp_messages_${legacySession}`, legacyMessages);
       }
    }

    if (!activeSessionId && loadedList.length > 0) {
      activeSessionId = loadedList[0].id;
    }
    
    if (activeSessionId) {
       const msgs = localStorage.getItem(`tp_messages_${activeSessionId}`);
       if (msgs) {
         try { setMessages(JSON.parse(msgs)); } catch (e) { setMessages([]); }
       } else {
         setMessages([]);
       }
       setSessionId(activeSessionId);
       localStorage.setItem('travel_planner_active_session', activeSessionId);
    } else {
       createNewSession(loadedList);
    }
    
    setIsLoaded(true);
  }, []);

  const createNewSession = (currentList?: SessionInfo[]) => {
    const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    const newSession: SessionInfo = { id: newSessionId, name: `New Trip` };
    
    const listToUpdate = currentList || sessionList;
    const updated = [newSession, ...listToUpdate];
    
    setSessionList(updated);
    localStorage.setItem('travel_planner_sessions', JSON.stringify(updated));
    setSessionId(newSessionId);
    setMessages([]);
    localStorage.setItem(`tp_messages_${newSessionId}`, JSON.stringify([]));
    localStorage.setItem('travel_planner_active_session', newSessionId);
    setSidebarOpen(false);
  };

  const loadSession = (id: string) => {
    setSessionId(id);
    localStorage.setItem('travel_planner_active_session', id);
    const msgs = localStorage.getItem(`tp_messages_${id}`);
    if (msgs) {
      try { setMessages(JSON.parse(msgs)); } catch (e) { setMessages([]); }
    } else {
      setMessages([]);
    }
    setSidebarOpen(false);
  };

  useEffect(() => {
    if (isLoaded && sessionId) {
      localStorage.setItem(`tp_messages_${sessionId}`, JSON.stringify(messages));
      
      // Update name to reflect first message if it's default
      if (messages.length > 0 && messages[0].role === 'user') {
         setSessionList(prev => {
            const newList = [...prev];
            const idx = newList.findIndex(s => s.id === sessionId);
            if (idx >= 0 && newList[idx].name === 'New Trip') {
               newList[idx].name = messages[0].text.substring(0, 30) + (messages[0].text.length > 30 ? '...' : '');
               localStorage.setItem('travel_planner_sessions', JSON.stringify(newList));
            }
            return newList;
         });
      }
    }
    scrollToBottom();
  }, [messages, loading, isLoaded, sessionId]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    
    const userMessage = { role: 'user', text: input };
    setMessages(prev => [...prev, userMessage, { role: 'agent', text: '', logs: [] }]);
    setInput('');
    setLoading(true);

    try {
      const apiUrl = `/api/a2a/app`;
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "message/stream",
          id: `req-${Date.now()}`,
          params: {
            message: {
              message_id: `msg-${Date.now()}`,
              contextId: sessionId,
              role: "user",
              parts: [{ text: userMessage.text }]
            }
          }
        })
      });

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      
      let fullText = "";
      let a2uiComponents: A2UIComponent[] | undefined = undefined;
      let logsBuffer: string[] = [];
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || "";
        
        let shouldUpdateState = false;

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              
              if (data.result?.status?.message?.parts) {
                for (const part of data.result.status.message.parts) {
                   if (part.metadata?.adk_type === 'thought' && part.text) {
                     logsBuffer.push(`[Thinking] ${part.text.substring(0, 80)}...`);
                     shouldUpdateState = true;
                   } else if (part.metadata?.adk_type === 'function_call' && part.data) {
                     logsBuffer.push(`[Tool Call] \u2699\ufe0f Using ${part.data.name}`);
                     shouldUpdateState = true;
                   } else if (part.metadata?.adk_type === 'function_response' && part.data) {
                     logsBuffer.push(`[Result] \u2705 Function returned`);
                     shouldUpdateState = true;
                   } else if (!part.metadata?.adk_type && part.kind === 'text' && part.text) {
                     const trimmed = part.text.trim();
                     if (trimmed && !trimmed.startsWith('```json')) {
                       logsBuffer.push(`[Agent] ${trimmed.substring(0, 80)}${trimmed.length > 80 ? '...' : ''}`);
                       shouldUpdateState = true;
                     }
                   }
                }
              }

              let textPart = "";
              // Extract text from agent message part
              if (data.result?.status?.message?.role === 'agent' && data.result?.status?.message?.parts) {
                for (const part of data.result.status.message.parts) {
                  if (part.kind === 'text' && part.text && !part.metadata?.adk_type) {
                    textPart = part.text;
                  }
                }
              }
              // Also check artifact if available
              if (data.result?.artifact?.parts) {
                const artText = data.result.artifact.parts.find((p: any) => p.kind === 'text')?.text;
                if (artText) {
                  textPart = artText;
                }
              }
              
              if (textPart) {
                shouldUpdateState = true;
                fullText = textPart;
                
                let rawJson = fullText.trim();
                const jsonMatch = rawJson.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
                if (jsonMatch) {
                   rawJson = jsonMatch[1].trim();
                } else if (rawJson.startsWith('```json')) {
                   rawJson = rawJson.replace(/^```json\n?/, '').replace(/```$/, '').trim();
                }

                if (rawJson.startsWith('[') || rawJson.startsWith('{')) {
                  try {
                     const parsed = JSON.parse(rawJson);
                     if (Array.isArray(parsed)) {
                       a2uiComponents = parsed;
                     } else if (parsed && parsed.type) {
                       a2uiComponents = [parsed];
                     }
                  } catch (e) {
                     // incomplete json
                  }
                }
              }
            } catch (e) {
              console.error(e);
            }
          }
        }

        if (shouldUpdateState) {
          setMessages(prev => {
             const m = [...prev];
             const latest = m[m.length - 1];
             if (latest && latest.role === 'agent') {
                latest.logs = [...logsBuffer];
                latest.text = a2uiComponents ? "" : fullText;
                latest.components = a2uiComponents;
             }
             return m;
          });
        }
      }

    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'agent', text: "Error connecting to backend." }]);
    } finally {
      setLoading(false);
    }
  };

  const renderComponent = (comp: A2UIComponent, i: number) => {
    switch (comp.type) {
      case 'card':
        return (
          <div key={i} className="flex flex-col border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow duration-300 mb-4 text-gray-900 dark:text-gray-100">
            {comp.title && <h3 className="font-bold text-xl mb-3">{comp.title}</h3>}
            {comp.content && <p className="text-gray-600 dark:text-gray-300 mb-4 leading-relaxed">{comp.content}</p>}
            <div className="mt-auto flex items-center justify-between">
              {comp.price !== undefined && <span className="text-emerald-600 dark:text-emerald-400 font-bold text-lg">${comp.price}</span>}
              {comp.deepLink && (
                <a href={comp.deepLink} target="_blank" className="ml-auto inline-flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-xl transition-colors duration-200">
                  Book Now
                  <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                </a>
              )}
            </div>
            {comp.components && <div className="mt-4">{comp.components.map((c, j) => renderComponent(c, j))}</div>}
          </div>
        );
      case 'list':
      case 'list_card_component':
      case 'layout_card':
      case 'card_list':
        return (
          <div key={i} className="mb-6 w-full">
            {comp.title && <h4 className="font-bold text-lg mb-4 text-gray-800 dark:text-gray-200">{comp.title}</h4>}
            <div className="flex flex-col gap-2 w-full">
              {comp.components && comp.components.map((c, j) => renderComponent(c, j))}
            </div>
          </div>
        );
      case 'text':
      case 'text_item':
        const fs = comp.font_style?.tag || (comp as any).fontStyle;
        const textClass = fs === 'display_small' ? 'text-2xl font-bold mb-4' : fs === 'title_medium' ? 'text-lg font-semibold mt-4 mb-2' : fs === 'body_large' ? 'text-lg mb-2' : 'text-base mb-1';
        return <p key={i} className={textClass}>{comp.text}</p>;
      case 'divider':
        return <hr key={i} className="my-4 border-gray-200 dark:border-gray-700 w-full" />;
      case 'list_item':
        return (
          <div key={i} className="flex flex-row items-center justify-between p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl mb-2 hover:bg-gray-100 transition-colors w-full border border-gray-100 dark:border-gray-600">
            <div className="flex items-center space-x-4 flex-1">
              {comp.leading_image && <img src={comp.leading_image.image_uri} alt="" className="w-12 h-12 rounded-lg object-contain bg-white shrink-0" />}
              <div className="flex flex-col">
                <h5 className="font-semibold text-lg">{comp.headline}</h5>
                <p className="text-sm text-gray-500 dark:text-gray-400">{comp.details}</p>
                {comp.accessories && comp.accessories.map((a: any, k: number) => (
                   <span key={k} className="text-xs text-emerald-600 dark:text-emerald-400 font-medium inline-block mt-1">{a.text}</span>
                ))}
              </div>
            </div>
            <div className="flex flex-col items-end pl-4 shrink-0">
              <span className="font-bold text-gray-900 dark:text-gray-100 text-lg block">{comp.trailing_details}</span>
              {comp.on_click && comp.on_click.type === 'link' && (
                <a href={comp.on_click.uri} target="_blank" className="text-blue-500 hover:text-blue-600 hover:underline text-sm font-medium mt-1 inline-flex items-center">
                  View <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                </a>
              )}
            </div>
          </div>
        );
      default:
        return (
          <div key={i} className="text-red-500 text-sm mt-2 border border-red-200 p-2 rounded">
            <strong>Unsupported component type: {comp.type || 'unknown'}</strong>
            <pre className="mt-1 text-xs overflow-x-auto text-gray-500">{JSON.stringify(comp, null, 2)}</pre>
          </div>
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 flex flex-col md:flex-row">
      
      {/* Sidebar for Mobile */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      
      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0 flex flex-col ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h2 className="font-bold text-lg">My Trips</h2>
          <button className="md:hidden p-2 text-gray-500" onClick={() => setSidebarOpen(false)}>
             <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>
        
        <div className="p-4">
          <button 
            onClick={() => createNewSession()} 
            className="w-full flex items-center justify-center space-x-2 bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 p-2.5 rounded-lg border border-blue-100 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path></svg>
            <span className="font-medium">New Plan</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sessionList.map(session => (
            <button 
              key={session.id}
              onClick={() => loadSession(session.id)}
              className={`w-full text-left p-3 rounded-lg text-sm truncate transition-colors ${sessionId === session.id ? 'bg-gray-100 dark:bg-gray-700 font-medium' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50 text-gray-600 dark:text-gray-300'}`}
            >
              {session.name}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 h-screen">
        <header className="w-full px-4 sm:px-6 py-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm z-10 shrink-0">
          <div className="flex items-center">
            <button className="md:hidden mr-3 p-2 text-gray-600 hover:bg-gray-100 rounded-lg dark:text-gray-300 dark:hover:bg-gray-800" onClick={() => setSidebarOpen(true)}>
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
            </button>
            <div>
              <h1 className="text-xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Personal Travel Planner</h1>
              <p className="text-gray-500 dark:text-gray-400 text-xs font-medium">Design your perfect itinerary instantly.</p>
            </div>
          </div>
        </header>
        
        <main className="flex-1 overflow-y-auto px-4 sm:px-6 py-8 flex flex-col items-center">
          <div className="w-full max-w-4xl flex-1 flex flex-col space-y-6">
            {messages.length === 0 && (
              <div className="text-center text-gray-400 dark:text-gray-500 mt-20 flex flex-col items-center">
                <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                <p>Where would you like to travel next?</p>
              </div>
            )}
            
            {messages.map((m, i) => (
              <div key={i} className={`flex w-full ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex flex-col max-w-[90%] md:max-w-[80%] rounded-3xl p-5 ${m.role === 'user' ? 'bg-blue-600 text-white rounded-br-none shadow-md' : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 border border-gray-100 dark:border-gray-700 rounded-bl-none shadow-sm'}`}>
                  {m.logs && m.logs.length > 0 && (
                     <div className="mb-4 bg-gray-50 dark:bg-gray-900/50 p-3 rounded-xl border border-gray-100 dark:border-gray-700 font-mono text-xs text-gray-500 overflow-x-auto space-y-1">
                        {m.logs.map((log, k) => (
                           <div key={k} className="leading-snug">
                             {log}
                           </div>
                        ))}
                     </div>
                  )}
                  {m.text && <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>}
                  {m.components && (
                    <div className="mt-4 w-full">
                      {m.components.map((comp, j) => renderComponent(comp, j))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            
            <div ref={messagesEndRef} />
          </div>
        </main>

        <div className="w-full max-w-4xl mx-auto px-4 sm:px-6 pb-6 shrink-0 bg-transparent">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-2 flex items-center transition-all focus-within:ring-2 focus-within:ring-blue-500/50">
            <input 
              type="text" 
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()}
              placeholder="Plan my trip to Miami..."
              className="flex-1 bg-transparent border-none p-3 focus:outline-none focus:ring-0 text-gray-900 dark:text-gray-100 placeholder-gray-400"
            />
            <button 
              onClick={sendMessage}
              disabled={loading}
              className={`mr-1 p-3 rounded-xl font-medium transition-all duration-200 flex items-center justify-center
                ${loading ? 'bg-gray-100 text-gray-400 dark:bg-gray-700' : 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-md'}`}
            >
              {loading ? (
                 <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              ) : (
                 <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
