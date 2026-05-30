import React, { useState, useEffect, useCallback, useRef } from 'react';
import { SignedIn, SignedOut, useUser } from '@clerk/clerk-react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import HealthProfile from './components/HealthProfile';
import Homepage from './components/Homepage';
import About from './components/About';
import SearchCanvas from './components/SearchCanvas';
import HealthCornerCreate from './components/HealthCornerCreate';
import HealthCornerView from './components/HealthCornerView';
import AdminDashboard from './components/AdminDashboard';
import {
  sendChatMessageStream,
  checkHealth,
  getSessions,
  getSessionMessages,
  deleteSession,
  saveHealthProfile,
  getHealthProfile,
  getCorners,
  createCorner,
  updateCorner,
  deleteCorner,
  assignSessionToCorner,
} from './services/api';
import { Routes, Route } from 'react-router-dom';
import './App.css';

function AuthenticatedApp() {
  const { user } = useUser();
  const isAdmin = user?.publicMetadata?.role === 'admin';
  const [showAdmin, setShowAdmin] = useState(false);

  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [healthProfile, setHealthProfile] = useState({
    chronic_diseases: [],
    allergies: [],
    current_medications: [],
    age: null,
    gender: '',
  });
  const [apiStatus, setApiStatus] = useState(null);
  const [chatSessions, setChatSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(() => {
    return localStorage.getItem('currentSessionId') || null;
  });
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [profileCompleted, setProfileCompleted] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [safetyReviewing, setSafetyReviewing] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const streamingRef = useRef('');
  const abortControllerRef = useRef(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('appTheme') || 'dark';
  });
  const [currentView, setCurrentView] = useState('chat'); // 'chat', 'search', 'corner', 'corner-create'

  // Health Corner state
  const [healthCorners, setHealthCorners] = useState([]);
  const [activeCorner, setActiveCorner] = useState(null);
  const [refreshCornerSessionsTrigger, setRefreshCornerSessionsTrigger] = useState(0);

  const currentSession = chatSessions.find((session) => session._id === currentSessionId);
  const conversationTitle = currentSession?.title || 'Cuộc trò chuyện mới';

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('appTheme', theme);
  }, [theme]);

  useEffect(() => {
    checkApiHealth();
    fetchSessions();
    fetchCorners();

    // Tải thông tin hồ sơ từ máy chủ để đồng bộ hóa
    const loadProfileFromServer = async () => {
      try {
        const profileData = await getHealthProfile();
        if (profileData) {
          setHealthProfile(profileData);
          const hasData =
            (profileData.chronic_diseases && profileData.chronic_diseases.length > 0) ||
            (profileData.allergies && profileData.allergies.length > 0) ||
            (profileData.current_medications && profileData.current_medications.length > 0) ||
            profileData.age ||
            profileData.gender;
          setProfileCompleted(!!hasData);
        }
      } catch (error) {
        console.error('Failed to fetch health profile from server:', error);
      }
    };
    loadProfileFromServer();

    const savedSessionId = localStorage.getItem('currentSessionId');
    if (savedSessionId) {
      const loadInitialSession = async () => {
        setIsLoading(true);
        try {
          const sessionMessages = await getSessionMessages(savedSessionId);
          const formattedMessages = sessionMessages.map((msg) => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            citations: msg.citations || [],
            warnings: msg.warnings || [],
          }));
          setMessages(formattedMessages);
        } catch (error) {
          console.error('Error loading session messages', error);
          setCurrentSessionId(null);
          localStorage.removeItem('currentSessionId');
        } finally {
          setIsLoading(false);
        }
      };
      loadInitialSession();
    }
  }, []);

  /* Load profile from localStorage on mount — check if onboarding is needed */
  useEffect(() => {
    const savedProfile = localStorage.getItem('healthProfile');
    if (savedProfile) {
      try {
        const parsed = JSON.parse(savedProfile);
        setHealthProfile(parsed);
        const hasData =
          (parsed.chronic_diseases && parsed.chronic_diseases.length > 0) ||
          (parsed.allergies && parsed.allergies.length > 0) ||
          (parsed.current_medications && parsed.current_medications.length > 0) ||
          parsed.age ||
          parsed.gender;
        setProfileCompleted(!!hasData);
      } catch (error) {
        console.error('Error loading profile:', error);
      }
    }
  }, []);

  /* Show onboarding modal for first-time users */
  useEffect(() => {
    if (user) {
      const onboardingKey = `onboarding_seen_${user.id}`;
      const seen = localStorage.getItem(onboardingKey);
      if (!seen) {
        setShowOnboarding(true);
        localStorage.setItem(onboardingKey, 'true');
      }
    }
  }, [user]);

  useEffect(() => {
    localStorage.setItem('healthProfile', JSON.stringify(healthProfile));
  }, [healthProfile]);

  const checkApiHealth = async () => {
    try {
      const status = await checkHealth();
      setApiStatus(status);
    } catch (error) {
      console.error('API health check failed:', error);
      setApiStatus({ status: 'error' });
    }
  };

  const fetchSessions = async () => {
    try {
      const data = await getSessions();
      setChatSessions(data);
    } catch (error) {
      console.error('Failed to load sessions', error);
    }
  };

  const fetchCorners = async () => {
    try {
      const data = await getCorners();
      setHealthCorners(data);
    } catch (error) {
      console.error('Failed to load health corners:', error);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    localStorage.removeItem('currentSessionId');
    setMessages([]);
    setActiveCorner(null);
    setIsProfileOpen(false);
    setCurrentView('chat');
  };

  const handleSelectSession = async (sessionId) => {
    setCurrentSessionId(sessionId);
    localStorage.setItem('currentSessionId', sessionId);

    // Sync activeCorner based on session's corner_id
    const session = chatSessions.find(s => s._id === sessionId);
    if (session?.corner_id) {
      const corner = healthCorners.find(c => c._id === session.corner_id);
      setActiveCorner(corner || null);
    } else {
      setActiveCorner(null);
    }

    setIsLoading(true);
    setMessages([]);
    setCurrentView('chat');
    try {
      const sessionMessages = await getSessionMessages(sessionId);
      const formattedMessages = sessionMessages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        citations: msg.citations || [],
        warnings: msg.warnings || [],
      }));
      setMessages(formattedMessages);
    } catch (error) {
      console.error('Error loading session messages', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await deleteSession(sessionId);
      if (currentSessionId === sessionId) {
        handleNewChat();
      }
      fetchSessions();
    } catch (error) {
      console.error('Error deleting session', error);
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  const handleSendMessage = async (query, cornerId = null) => {
    const userMessage = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setIsStreaming(true);
    setStreamingContent('');
    setStatusMessage('');
    setSafetyReviewing(false);
    setSuggestions([]);
    streamingRef.current = '';

    abortControllerRef.current = new AbortController();

    try {
      await sendChatMessageStream(query, healthProfile, currentSessionId, {
        onToken: (text) => {
          streamingRef.current += text;
          setStreamingContent(streamingRef.current);
          setStatusMessage('');
        },

        onStatus: (message) => {
          setStatusMessage(message);
        },

        onWarnings: (warnings) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.role === 'assistant') {
              updated[updated.length - 1] = { ...last, warnings };
            }
            return updated;
          });
        },

        onReplace: (newContent) => {
          setSafetyReviewing(true);
          setTimeout(() => {
            streamingRef.current = newContent;
            setStreamingContent(newContent);
            setSafetyReviewing(false);
          }, 1500);
        },

        onDone: (data) => {
          const finalContent = streamingRef.current;

          // Extract suggestions from [SUGGESTIONS] tag
          const sugDelimiter = '[SUGGESTIONS]';
          let extractedSuggestions = [];
          const sugIdx = finalContent.indexOf(sugDelimiter);
          if (sugIdx !== -1) {
            const sugBlock = finalContent.substring(sugIdx + sugDelimiter.length).trim();
            extractedSuggestions = sugBlock
              .split('\n')
              .map(s => s.replace(/^\d+\.\s*/, '').replace(/^[-*]\s*/, '').trim())
              .filter(s => s.length > 0);
          }
          setSuggestions(extractedSuggestions);

          const assistantMessage = {
            id: data.message_id,
            role: 'assistant',
            content: finalContent,
            citations: data.citations || [],
            warnings: data.warnings || [],
            processing_time: data.processing_time,
          };
          setMessages((prev) => [...prev, assistantMessage]);
          setStreamingContent('');
          setStatusMessage('');
          setIsStreaming(false);
          streamingRef.current = '';

          if (data.session_id) {
            if (currentSessionId !== data.session_id) {
              setCurrentSessionId(data.session_id);
              localStorage.setItem('currentSessionId', data.session_id);
            }
            fetchSessions();
            fetchCorners();
          }
        },

        onError: (errorMsg) => {
          console.error('Stream error:', errorMsg);
          const errorMessage = {
            role: 'assistant',
            content:
              '⚠️ Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn. Vui lòng thử lại sau.',
            warnings: [
              {
                severity: 'high',
                message: 'Lỗi kết nối',
                reason: errorMsg || 'Không thể kết nối đến máy chủ.',
                affected_conditions: [],
              },
            ],
          };
          setMessages((prev) => [...prev, errorMessage]);
          setStreamingContent('');
          setStatusMessage('');
          setIsStreaming(false);
          streamingRef.current = '';
        },

        onAbort: () => {
          const finalContent = streamingRef.current;
          if (finalContent) {
            const assistantMessage = {
              role: 'assistant',
              content: finalContent + '\n\n*(Đã dừng bởi người dùng)*',
              citations: [],
              warnings: [],
            };
            setMessages((prev) => [...prev, assistantMessage]);
          } else {
            // Remove user message if aborted before any character generated
            setMessages((prev) => {
              const updated = [...prev];
              if (updated.length > 0 && updated[updated.length - 1].role === 'user') {
                updated.pop();
              }
              return updated;
            });
          }
          setStreamingContent('');
          setStatusMessage('');
          setIsStreaming(false);
          streamingRef.current = '';
          setIsLoading(false);
        },
      }, abortControllerRef.current.signal, cornerId);
    } catch (error) {
      console.error('Streaming connection failed:', error);
      const errorMessage = {
        role: 'assistant',
        content:
          '⚠️ Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn. Vui lòng thử lại sau.',
        warnings: [
          {
            severity: 'high',
            message: 'Lỗi kết nối',
            reason:
              error.message ||
              'Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng.',
            affected_conditions: [],
          },
        ],
      };
      setMessages((prev) => [...prev, errorMessage]);
      setStreamingContent('');
      setStatusMessage('');
      setIsStreaming(false);
      streamingRef.current = '';
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditMessage = (newText) => {
    // Replace the last user message with edited text, remove subsequent messages, and re-send
    setMessages((prev) => {
      const updated = [...prev];
      // Find and remove from last user message onwards
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === 'user') {
          return updated.slice(0, i);
        }
      }
      return updated;
    });
    setSuggestions([]);
    // Re-send the edited message after a tick
    setTimeout(() => handleSendMessage(newText), 50);
  };

  const handleProfileChange = useCallback(async (newProfile) => {
    setHealthProfile(newProfile);

    const hasData =
      (newProfile.chronic_diseases && newProfile.chronic_diseases.length > 0) ||
      (newProfile.allergies && newProfile.allergies.length > 0) ||
      (newProfile.current_medications && newProfile.current_medications.length > 0) ||
      newProfile.age ||
      newProfile.gender;
    setProfileCompleted(!!hasData);

    // Không cần gọi saveHealthProfile ở đây nữa vì HealthProfile component đã gọi patchHealthProfile trực tiếp và ghi nhận thành công
  }, []);

  const handleOnboardingClose = () => {
    setShowOnboarding(false);
  };

  const handleOnboardingOpenProfile = () => {
    setShowOnboarding(false);
    setIsProfileOpen(true);
  };

  const handleOpenCorner = async (corner) => {
    setActiveCorner(corner);
    setCurrentSessionId(null);
    setMessages([]);
    setCurrentView('corner');
  };

  const handleAssignSession = async (sessionId, cornerId) => {
    try {
      await assignSessionToCorner(sessionId, cornerId);
      await fetchCorners();
      await fetchSessions();
      setRefreshCornerSessionsTrigger((prev) => prev + 1);
      // If this is the active session, sync activeCorner
      if (currentSessionId === sessionId) {
        const corner = healthCorners.find((c) => c._id === cornerId);
        setActiveCorner(corner || null);
      }
    } catch (error) {
      console.error('Error assigning session:', error);
    }
  };

  const handleUpdateCorner = async (cornerId, name, emoji) => {
    try {
      await updateCorner(cornerId, { name, emoji });
      await fetchCorners();
      if (activeCorner?._id === cornerId) {
        setActiveCorner((prev) => ({ ...prev, name, emoji }));
      }
    } catch (error) {
      console.error('Error updating corner:', error);
    }
  };

  const handleDeleteCorner = async (cornerId) => {
    try {
      await deleteCorner(cornerId);
      await fetchCorners();
      if (activeCorner?._id === cornerId) {
        setActiveCorner(null);
        setCurrentView('chat');
      }
    } catch (error) {
      console.error('Error deleting corner:', error);
    }
  };

  const handleSelectCornerSession = async (session) => {
    setCurrentSessionId(session._id);
    localStorage.setItem('currentSessionId', session._id);
    setIsLoading(true);
    setMessages([]);
    try {
      const sessionMessages = await getSessionMessages(session._id);
      const formattedMessages = sessionMessages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        citations: msg.citations || [],
        warnings: msg.warnings || [],
      }));
      setMessages(formattedMessages);
      setCurrentView('chat');
    } catch (error) {
      console.error('Error loading session messages:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChatInCorner = async (query) => {
    setCurrentSessionId(null);
    localStorage.removeItem('currentSessionId');
    setMessages([]);
    setCurrentView('chat');
    await handleSendMessage(query, activeCorner?._id);
  };

  return (
    <div className="app-layout">
      {!showAdmin && (
        <Sidebar
          sessions={chatSessions}
          currentSessionId={currentSessionId}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          onRefreshSessions={fetchSessions}
          theme={theme}
          onToggleTheme={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
          isOpen={isSidebarOpen}
          onToggle={() => setIsSidebarOpen((prev) => !prev)}
          profileCompleted={profileCompleted}
          onOpenProfile={() => setIsProfileOpen(true)}
          isProfileOpen={isProfileOpen}
          currentView={currentView}
          isAdmin={isAdmin}
          onOpenAdmin={() => {
            setShowAdmin(true);
            setCurrentView('chat');
          }}
          onOpenSearch={() => setCurrentView('search')}
          healthCorners={healthCorners}
          activeCorner={activeCorner}
          currentSession={currentSession}
          onCreateCornerView={() => setCurrentView('corner-create')}
          onOpenCorner={handleOpenCorner}
          onAssignSession={handleAssignSession}
          onUpdateCorner={handleUpdateCorner}
          onDeleteCorner={handleDeleteCorner}
          isMobileSidebarOpen={isMobileSidebarOpen}
          onCloseMobileSidebar={() => setIsMobileSidebarOpen(false)}
        />
      )}

      <main className={`main-canvas ${isSidebarOpen && !showAdmin ? 'sidebar-open' : ''} ${showAdmin ? 'admin-open' : ''}`}>
        {apiStatus && apiStatus.status !== 'healthy' && (
          <div className="api-banner">
            <span className="banner-dot" />
            API không khả dụng — kiểm tra backend
          </div>
        )}

        {showAdmin && isAdmin ? (
          <AdminDashboard 
            onBack={() => setShowAdmin(false)} 
            onClose={() => setShowAdmin(false)} 
          />
        ) : currentView === 'search' ? (
          <SearchCanvas
            recentSessions={chatSessions}
            onClose={() => setCurrentView('chat')}
            onSelectSession={handleSelectSession}
          />
        ) : currentView === 'corner-create' ? (
          <HealthCornerCreate
            onConfirm={async (name, emoji) => {
              try {
                await createCorner(name, emoji);
                await fetchCorners();
                setCurrentView('chat');
              } catch (err) {
                console.error('Error creating corner:', err);
              }
            }}
            onCancel={() => setCurrentView('chat')}
          />
        ) : currentView === 'corner' && activeCorner ? (
          <HealthCornerView
            corner={activeCorner}
            healthCorners={healthCorners}
            refreshTrigger={refreshCornerSessionsTrigger}
            onClose={() => {
              setActiveCorner(null);
              setCurrentView('chat');
            }}
            onSelectSession={handleSelectCornerSession}
            onAssignSession={handleAssignSession}
            onDeleteCorner={handleDeleteCorner}
            onUpdateCorner={handleUpdateCorner}
            onRefreshCorners={fetchCorners}
            onNewChatInCorner={handleNewChatInCorner}
            onDeleteSession={handleDeleteSession}
            onToggleMobileSidebar={() => setIsMobileSidebarOpen(true)}
          />
        ) : (
          <ChatInterface
            onSendMessage={handleSendMessage}
            onStopGeneration={handleStopGeneration}
            messages={messages}
            isLoading={isLoading}
            streamingContent={streamingContent}
            statusMessage={statusMessage}
            isStreaming={isStreaming}
            safetyReviewing={safetyReviewing}
            conversationTitle={conversationTitle}
            suggestions={suggestions}
            currentSessionId={currentSessionId}
            onEditMessage={handleEditMessage}
            activeCorner={activeCorner}
            onOpenCorner={handleOpenCorner}
            onToggleMobileSidebar={() => setIsMobileSidebarOpen(true)}
            sessions={chatSessions}
            healthCorners={healthCorners}
            onRefreshSessions={fetchSessions}
            onDeleteSession={handleDeleteSession}
            onAssignSession={handleAssignSession}
            onUpdateCorner={handleUpdateCorner}
            onDeleteCorner={handleDeleteCorner}
          />
        )}


      </main>

      <HealthProfile
        profile={healthProfile}
        onProfileChange={handleProfileChange}
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />

      {/* Onboarding Modal — first login only */}
      {showOnboarding && (
        <div className="onboarding-overlay" onClick={handleOnboardingClose}>
          <div className="onboarding-modal fade-in" onClick={(e) => e.stopPropagation()}>
            <div className="onboarding-icon">🩺</div>
            <h2>Chào mừng đến với Medical AI!</h2>
            <p>
              Để AI có thể đưa ra lời khuyên <strong>an toàn và phù hợp nhất</strong>,
              hãy cập nhật Hồ sơ Sức khỏe của bạn (bệnh nền, dị ứng, thuốc đang dùng).
            </p>
            <div className="onboarding-actions">
              <button className="onboarding-btn primary" onClick={handleOnboardingOpenProfile}>
                📋 Cập nhật Hồ sơ ngay
              </button>
              <button className="onboarding-btn secondary" onClick={handleOnboardingClose}>
                Bỏ qua / Cập nhật sau
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/about" element={<About />} />
      <Route
        path="/*"
        element={
          <>
            <SignedOut>
              <Homepage />
            </SignedOut>
            <SignedIn>
              <AuthenticatedApp />
            </SignedIn>
          </>
        }
      />
    </Routes>
  );
}

export default App;
