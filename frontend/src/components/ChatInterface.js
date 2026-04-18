import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, ArrowDown, Square } from 'lucide-react';
import MessageList from './MessageList';
import './ChatInterface.css';

const ChatInterface = ({
  onSendMessage,
  onStopGeneration,
  messages,
  isLoading,
  streamingContent,
  statusMessage,
  isStreaming,
  safetyReviewing,
  conversationTitle,
}) => {
  const [input, setInput] = useState('');
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const chatContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const isUserScrollingRef = useRef(false);
  const lastUserMsgRef = useRef(null);
  const spacerRef = useRef(null);
  const justSentRef = useRef(false);
  const firstMessageRef = useRef(null);
  const firstLoadRef = useRef(true);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const container = chatContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior });
    }
  }, []);

  const updateSpacer = useCallback(() => {
    const container = chatContainerRef.current;
    const userEl = lastUserMsgRef.current;
    const spacerEl = spacerRef.current;
    if (!container || !userEl || !spacerEl) return;

    spacerEl.style.height = '0px';
    void container.scrollHeight;

    const userMsgTop = userEl.offsetTop;
    const totalContent = container.scrollHeight;
    const contentBelowUser = totalContent - userMsgTop;
    const viewportH = container.clientHeight;

    const needed = Math.max(0, viewportH - contentBelowUser);
    spacerEl.style.height = needed + 'px';
  }, []);

  const scrollUserToTop = useCallback(() => {
    const userEl = lastUserMsgRef.current;
    const container = chatContainerRef.current;
    if (userEl && container) {
      const containerRect = container.getBoundingClientRect();
      const elRect = userEl.getBoundingClientRect();
      const offset = elRect.top - containerRect.top + container.scrollTop;
      container.scrollTo({ top: offset - 12, behavior: 'smooth' });
    }
  }, []);

  useEffect(() => {
    if (justSentRef.current) {
      requestAnimationFrame(() => {
        updateSpacer();
        scrollUserToTop();
        justSentRef.current = false;
      });
    }
  }, [messages, updateSpacer, scrollUserToTop]);

  useEffect(() => {
    const currentFirst = messages.length > 0 ? messages[0].content : null;
    if (messages.length > 0 && (firstLoadRef.current || currentFirst !== firstMessageRef.current)) {
      firstMessageRef.current = currentFirst;
      firstLoadRef.current = false;
      requestAnimationFrame(() => {
        updateSpacer();
        scrollUserToTop();
      });
    }
  }, [messages, updateSpacer, scrollUserToTop]);

  useEffect(() => {
    if (isStreaming && streamingContent) {
      requestAnimationFrame(() => {
        updateSpacer();
      });
    }
  }, [streamingContent, isStreaming, updateSpacer]);

  useEffect(() => {
    if (isLoading && !isStreaming && !streamingContent) {
      requestAnimationFrame(() => {
        updateSpacer();
      });
    }
  }, [isLoading, isStreaming, streamingContent, updateSpacer]);

  useEffect(() => {
    if (!isStreaming && !isLoading && messages.length > 0) {
      requestAnimationFrame(() => {
        updateSpacer();
      });
    }
  }, [isStreaming, isLoading, messages, updateSpacer]);

  const handleScroll = () => {
    const container = chatContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;

    setShowScrollBtn(distanceFromBottom > 150);

    if (isStreaming) {
      isUserScrollingRef.current = distanceFromBottom > 80;
    }
  };

  const autoResize = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    autoResize();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      justSentRef.current = true;
      isUserScrollingRef.current = false;
      onSendMessage(input.trim());
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const suggestions = [
    'Dấu hiệu của bệnh tiểu đường?',
    'Cách giảm huyết áp tự nhiên?',
    'Cách phòng ngừa cảm cúm?',
    'Làm sao để chữa đau đầu?',
  ];

  const handleSuggestion = (text) => {
    if (!isLoading) {
      justSentRef.current = true;
      isUserScrollingRef.current = false;
      onSendMessage(text);
    }
  };

  return (
    <div className="chat-canvas">
      <div className="chat-topbar">
        <span className="chat-topbar-brand">A.I.M Care</span>
        <h2 className="chat-topbar-title">{conversationTitle}</h2>
        <div className="chat-topbar-spacer" aria-hidden="true" />
      </div>

      <div
        className="chat-messages"
        ref={chatContainerRef}
        onScroll={handleScroll}
      >
        {messages.length === 0 && !isLoading && !isStreaming ? (
          <div className="welcome-screen">
            <div className="welcome-greeting">
              <img src="/images/Logo_chat.png?v=20260417" alt="A.I.M Care" className="welcome-avatar" />
              <h1>Xin chào!</h1>
              <p>Tôi là A.I.M Care, trợ lý y tế cá nhân của bạn. Hãy chia sẻ các triệu chứng hoặc đặt bất kỳ câu hỏi nào về sức khỏe nhé.</p>
            </div>

            <div className="suggestions-grid">
              {suggestions.map((text, i) => (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => handleSuggestion(text)}
                  disabled={isLoading}
                >
                  <span className="chip-text">{text}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <MessageList
              messages={messages}
              streamingContent={streamingContent}
              isStreaming={isStreaming}
              safetyReviewing={safetyReviewing}
              lastUserMsgRef={lastUserMsgRef}
            />

            {/* Status indicator â€” replaces typing dots during pipeline phases */}
            {isLoading && !isStreaming && (
              <div className="typing-indicator fade-in">
                <div className="typing-avatar">
                  <img src="/images/Logo_chat.png?v=20260417" alt="A.I.M Care" className="typing-avatar-img" />
                </div>
                <div className="typing-dots">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              </div>
            )}

            {statusMessage && (
              <div className="status-indicator fade-in">
                <div className="typing-avatar">
                  <img src="/images/Logo_chat.png?v=20260417" alt="A.I.M Care" className="typing-avatar-img" />
                </div>
                <span className="status-text">{statusMessage}</span>
              </div>
            )}

            {/* Dynamic spacer â€” LAST element in scroll container */}
            <div ref={spacerRef} className="dynamic-spacer" />
          </>
        )}
      </div>

      {showScrollBtn && (
        <button
          className="scroll-bottom-btn"
          onClick={() => scrollToBottom()}
          title="Cuá»™n xuá»‘ng cuá»‘i"
        >
          <ArrowDown size={18} />
        </button>
      )}

      <div className="input-area">
        <form onSubmit={handleSubmit} className="input-form">
          <div className="input-wrapper">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Nháº­p cÃ¢u há»i vá» sá»©c khá»e..."
              disabled={isLoading}
              rows={1}
              className="chat-textarea"
            />
            {isLoading || isStreaming ? (
              <button
                type="button"
                onClick={onStopGeneration}
                className="send-btn stop-btn"
                title="Dá»«ng xá»­ lÃ½"
              >
                <Square size={16} fill="currentColor" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="send-btn"
              >
                <Send size={18} />
              </button>
            )}
          </div>
        </form>
        <p className="disclaimer">
          ThÃ´ng tin chá»‰ mang tÃ­nh tham kháº£o. Vui lÃ²ng tham kháº£o Ã½ kiáº¿n bÃ¡c sÄ© chuyÃªn khoa.
        </p>
      </div>
    </div>
  );
};

export default ChatInterface;

