import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import MessageList from './MessageList';
import './ChatInterface.css';

const ChatInterface = ({ onSendMessage, messages, isLoading }) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const quickQuestions = [
    'Làm sao để chữa đau đầu?',
    'Dấu hiệu của bệnh tiểu đường?',
    'Cách phòng ngừa cảm cúm?',
    'Cách giảm huyết áp tự nhiên?',
  ];

  const handleQuickQuestion = (question) => {
    if (!isLoading) {
      onSendMessage(question);
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <div className="header-content">
          <div className="header-icon">🏥</div>
          <div>
            <h2>Trợ lý Y tế AI</h2>
            <p className="header-subtitle">Hỏi đáp y tế với độ chính xác cao</p>
          </div>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon">👋</div>
            <h3>Chào mừng bạn đến với Trợ lý Y tế AI!</h3>
            <p>
              Tôi có thể giúp bạn tìm hiểu về các vấn đề sức khỏe, bệnh tật, và
              phương pháp điều trị. Hãy đặt câu hỏi hoặc chọn một câu hỏi mẫu bên dưới.
            </p>
            <div className="quick-questions">
              <p className="quick-label">💡 Câu hỏi gợi ý:</p>
              {quickQuestions.map((question, index) => (
                <button
                  key={index}
                  className="quick-question-btn"
                  onClick={() => handleQuickQuestion(question)}
                  disabled={isLoading}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        <MessageList messages={messages} />
        
        {isLoading && (
          <div className="loading-message fade-in">
            <div className="loading-content">
              <Loader2 className="spin" size={20} />
              <span>Đang tìm kiếm và phân tích thông tin...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <form onSubmit={handleSubmit} className="chat-input-form">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Nhập câu hỏi của bạn về sức khỏe..."
            disabled={isLoading}
            className="chat-input"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="send-button"
          >
            {isLoading ? <Loader2 className="spin" size={20} /> : <Send size={20} />}
          </button>
        </form>
        <p className="disclaimer">
          ⚠️ Lưu ý: Thông tin chỉ mang tính tham khảo. Vui lòng tham khảo bác sĩ cho chẩn đoán chính xác.
        </p>
      </div>
    </div>
  );
};

export default ChatInterface;
