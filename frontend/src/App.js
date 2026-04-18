import React, { useState, useEffect, useCallback, useRef } from 'react';
import { SignedIn, SignedOut, useUser, UserButton } from '@clerk/clerk-react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import HealthProfile from './components/HealthProfile';
import Homepage from './components/Homepage';
import About from './components/About';
import {
  sendChatMessageStream,
  checkHealth,
  getSessions,
  getSessionMessages,
  deleteSession,
  saveHealthProfile,
} from './services/api';
import { Routes, Route } from 'react-router-dom';
import './App.css';

function AuthenticatedApp() {
  const { user } = useUser();


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
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [profileCompleted, setProfileCompleted] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [safetyReviewing, setSafetyReviewing] = useState(false);
  const streamingRef = useRef('');
  const abortControllerRef = useRef(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('appTheme') || 'dark';
  });
  const currentSession = chatSessions.find((session) => session._id === currentSessionId);
  const conversationTitle = currentSession?.title || 'Cuộc trò chuyện mới';

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('appTheme', theme);
  }, [theme]);

  useEffect(() => {
    checkApiHealth();
    fetchSessions();
    const savedSessionId = localStorage.getItem('currentSessionId');
    if (savedSessionId) {
      // Create a local async function to load the session without depending on handleSelectSession 
      // closure before it's defined, or just use the same logic here.
      const loadInitialSession = async () => {
        setIsLoading(true);
        try {
          const sessionMessages = await getSessionMessages(savedSessionId);
          const formattedMessages = sessionMessages.map((msg) => ({
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

  const handleNewChat = () => {
    setCurrentSessionId(null);
    localStorage.removeItem('currentSessionId');
    setMessages([]);
  };

  const handleSelectSession = async (sessionId) => {
    setCurrentSessionId(sessionId);
    localStorage.setItem('currentSessionId', sessionId);
    setIsLoading(true);
    setMessages([]);
    try {
      const sessionMessages = await getSessionMessages(sessionId);
      const formattedMessages = sessionMessages.map((msg) => ({
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

  const handleSendMessage = async (query) => {
    const userMessage = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setIsStreaming(true);
    setStreamingContent('');
    setStatusMessage('');
    setSafetyReviewing(false);
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
          const assistantMessage = {
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

          if (data.session_id && currentSessionId !== data.session_id) {
            setCurrentSessionId(data.session_id);
            localStorage.setItem('currentSessionId', data.session_id);
            fetchSessions();
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
      }, abortControllerRef.current.signal);
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

  const handleProfileChange = useCallback(async (newProfile) => {
    setHealthProfile(newProfile);

    const hasData =
      (newProfile.chronic_diseases && newProfile.chronic_diseases.length > 0) ||
      (newProfile.allergies && newProfile.allergies.length > 0) ||
      (newProfile.current_medications && newProfile.current_medications.length > 0) ||
      newProfile.age ||
      newProfile.gender;
    setProfileCompleted(!!hasData);

    try {
      await saveHealthProfile(newProfile);
    } catch (error) {
      console.error('Failed to sync profile to server:', error);
    }
  }, []);

  const handleOnboardingClose = () => {
    setShowOnboarding(false);
  };

  const handleOnboardingOpenProfile = () => {
    setShowOnboarding(false);
    setIsProfileOpen(true);
  };

  return (
    <div className="app-layout">
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
      />

      <main className={`main-canvas ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="top-right-actions">
          <UserButton
            appearance={{
              elements: {
                avatarBox: { width: '36px', height: '36px' },
              },
            }}
          />
        </div>

        {apiStatus && apiStatus.status !== 'healthy' && (
          <div className="api-banner">
            <span className="banner-dot" />
            API không khả dụng — kiểm tra backend
          </div>
        )}
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
        />
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
