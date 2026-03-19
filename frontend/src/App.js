import React, { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';
import ChatInterface from './components/ChatInterface';
import HealthProfile from './components/HealthProfile';
import { sendChatMessage, checkHealth } from './services/api';
import './App.css';

function App() {
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

  // Check API health on mount
  useEffect(() => {
    checkApiHealth();
  }, []);

  // Load profile from localStorage
  useEffect(() => {
    const savedProfile = localStorage.getItem('healthProfile');
    if (savedProfile) {
      try {
        setHealthProfile(JSON.parse(savedProfile));
      } catch (error) {
        console.error('Error loading profile:', error);
      }
    }
  }, []);

  // Save profile to localStorage
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

  const handleSendMessage = async (query) => {
    // Add user message
    const userMessage = {
      role: 'user',
      content: query,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Send to API
      const response = await sendChatMessage(query, healthProfile);

      // Add assistant response
      const assistantMessage = {
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        warnings: response.warnings,
        processing_time: response.processing_time,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      
      // Add error message
      const errorMessage = {
        role: 'assistant',
        content: '⚠️ Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn. Vui lòng thử lại sau.',
        warnings: [{
          severity: 'high',
          message: 'Lỗi kết nối',
          reason: error.message || 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng và đảm bảo backend đang chạy.',
          affected_conditions: []
        }],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleProfileChange = (newProfile) => {
    setHealthProfile(newProfile);
  };

  return (
    <div className="app">
      <div className="app-container">
        {/* Header */}
        <header className="app-header">
          <div className="header-left">
            <Activity size={32} />
            <div>
              <h1>Hệ thống Trợ lý Y tế AI</h1>
              <p className="app-subtitle">
                Context-Aware Medical Assistant • Powered by RAG & Gemini 1.5 Flash
              </p>
            </div>
          </div>
          
          <div className="api-status">
            {apiStatus && (
              <div className={`status-badge ${apiStatus.status === 'healthy' ? 'healthy' : 'error'}`}>
                <span className="status-dot"></span>
                {apiStatus.status === 'healthy' ? 'API Sẵn sàng' : 'API Lỗi'}
              </div>
            )}
          </div>
        </header>

        {/* Main Content */}
        <main className="app-main">
          <div className="main-grid">
            {/* Left Column - Health Profile */}
            <aside className="sidebar">
              <HealthProfile 
                profile={healthProfile} 
                onProfileChange={handleProfileChange}
              />
              
              <div className="info-card">
                <h4>💡 Tính năng chính</h4>
                <ul>
                  <li>🔍 Tra cứu y khoa độ chính xác cao</li>
                  <li>⚠️ Cảnh báo tương tác thuốc/bệnh</li>
                  <li>📚 Trích dẫn nguồn minh bạch</li>
                  <li>🎯 Cá nhân hóa theo hồ sơ sức khỏe</li>
                </ul>
              </div>
            </aside>

            {/* Right Column - Chat Interface */}
            <section className="chat-section">
              <ChatInterface
                onSendMessage={handleSendMessage}
                messages={messages}
                isLoading={isLoading}
              />
            </section>
          </div>
        </main>

        {/* Footer */}
        <footer className="app-footer">
          <p>
            ⚠️ <strong>Disclaimer:</strong> Thông tin chỉ mang tính tham khảo và không thay thế cho
            chẩn đoán y tế chuyên nghiệp. Luôn tham khảo ý kiến bác sĩ.
          </p>
        </footer>
      </div>
    </div>
  );
}

export default App;
