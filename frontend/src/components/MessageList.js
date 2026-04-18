import React, { useState, useEffect } from 'react';
import { AlertTriangle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import Citation from './Citation';
import './MessageList.css';

const MessageList = ({
  messages,
  streamingContent,
  isStreaming,
  safetyReviewing,
  lastUserMsgRef,
}) => {
  const [expandedCitations, setExpandedCitations] = useState({});
  const [newChunkClass, setNewChunkClass] = useState('');

  const toggleCitations = (index) => {
    setExpandedCitations((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  useEffect(() => {
    if (!streamingContent) return;
    setNewChunkClass('chunk-fade-in');
    const timer = setTimeout(() => setNewChunkClass(''), 350);
    return () => clearTimeout(timer);
  }, [streamingContent]);

  const lastUserIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return i;
    }
    return -1;
  })();

  return (
    <div className="message-list">
      {messages.map((message, index) => (
        <div
          key={index}
          className={`message ${message.role} fade-in`}
          ref={message.role === 'user' && index === lastUserIndex ? lastUserMsgRef : null}
        >
          {message.role === 'user' ? (
            <div className="user-row">
              <div className="user-bubble">{message.content}</div>
            </div>
          ) : (
            <div className="assistant-row">
              <div className="assistant-avatar">
                <img src="/images/Logo_chat.png?v=20260417" alt="A.I.M Care" className="assistant-avatar-img" />
              </div>

              <div className="assistant-content">
                {/* Warnings */}
                {message.warnings && message.warnings.length > 0 && (
                  <div className="warnings-container">
                    {message.warnings.map((warning, wIndex) => (
                      <div
                        key={wIndex}
                        className={`warning-box severity-${warning.severity}`}
                      >
                        <div className="warning-header">
                          {warning.severity === 'high' ? (
                            <AlertTriangle size={16} />
                          ) : (
                            <Info size={16} />
                          )}
                          <strong>{warning.message}</strong>
                        </div>
                        <p className="warning-reason">{warning.reason}</p>
                        {warning.affected_conditions &&
                          warning.affected_conditions.length > 0 && (
                            <div className="affected-conditions">
                              <span>Liên quan: </span>
                              {warning.affected_conditions.map((cond, cIndex) => (
                                <span key={cIndex} className="condition-tag">
                                  {cond}
                                </span>
                              ))}
                            </div>
                          )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Markdown answer */}
                <div className="answer-text markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {message.content}
                  </ReactMarkdown>
                </div>

                {/* Citations */}
                {message.citations && message.citations.length > 0 && (
                  <div className="citations-section">
                    <button
                      className="citations-toggle"
                      onClick={() => toggleCitations(index)}
                    >
                      <span>
                        📚 Nguồn tham khảo ({message.citations.length})
                      </span>
                      {expandedCitations[index] ? (
                        <ChevronUp size={16} />
                      ) : (
                        <ChevronDown size={16} />
                      )}
                    </button>

                    {expandedCitations[index] && (
                      <div className="citations-list fade-in">
                        {message.citations.map((citation, cIndex) => (
                          <Citation
                            key={cIndex}
                            citation={citation}
                            index={cIndex + 1}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Processing time */}
                {message.processing_time && (
                  <div className="metadata">
                    <span className="processing-time">
                      ⏱️ {message.processing_time.toFixed(2)}s
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* Streaming message — live text with chunk-level fade */}
      {isStreaming && streamingContent && (
        <div className={`message assistant fade-in ${safetyReviewing ? 'safety-reviewing' : ''}`}>
          <div className="assistant-row">
            <div className="assistant-avatar">
              <img src="/images/Logo_chat.png?v=20260417" alt="A.I.M Care" className="assistant-avatar-img" />
            </div>
            <div className="assistant-content">
              {safetyReviewing && (
                <div className="safety-review-banner fade-in">
                  <span className="safety-review-icon">⚠️</span>
                  <span>Bác sĩ AI đang rà soát lại thông tin...</span>
                </div>
              )}
              <div className={`answer-text markdown-body streaming-text ${newChunkClass}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                  {streamingContent}
                </ReactMarkdown>
                <span className="streaming-cursor" />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MessageList;
