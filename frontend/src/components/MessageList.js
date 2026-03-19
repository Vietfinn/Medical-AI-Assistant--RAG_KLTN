import React, { useState } from 'react';
import { User, Bot, AlertTriangle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import Citation from './Citation';
import './MessageList.css';

const MessageList = ({ messages }) => {
  const [expandedCitations, setExpandedCitations] = useState({});

  const toggleCitations = (index) => {
    setExpandedCitations(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const formatMessageText = (text) => {
    // Simple formatting for warnings
    const parts = text.split(/(\⚠️[^:]+:|ℹ️[^:]+:)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith('⚠️')) {
        return (
          <span key={index} className="warning-high">
            {part}
          </span>
        );
      } else if (part.startsWith('ℹ️')) {
        return (
          <span key={index} className="warning-medium">
            {part}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="message-list">
      {messages.map((message, index) => (
        <div key={index} className={`message ${message.role} fade-in`}>
          <div className="message-avatar">
            {message.role === 'user' ? (
              <User size={20} />
            ) : (
              <Bot size={20} />
            )}
          </div>
          
          <div className="message-content">
            <div className="message-text">
              {message.role === 'user' ? (
                message.content
              ) : (
                <>
                  {/* Display warnings first */}
                  {message.warnings && message.warnings.length > 0 && (
                    <div className="warnings-container">
                      {message.warnings.map((warning, wIndex) => (
                        <div
                          key={wIndex}
                          className={`warning-box severity-${warning.severity}`}
                        >
                          <div className="warning-header">
                            {warning.severity === 'high' ? (
                              <AlertTriangle size={18} />
                            ) : (
                              <Info size={18} />
                            )}
                            <strong>{warning.message}</strong>
                          </div>
                          <p className="warning-reason">{warning.reason}</p>
                          {warning.affected_conditions && warning.affected_conditions.length > 0 && (
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
                  
                  {/* Display answer */}
                  <div className="answer-text">
                    {formatMessageText(message.content)}
                  </div>
                  
                  {/* Display citations */}
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
                            <Citation key={cIndex} citation={citation} index={cIndex + 1} />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Processing time */}
                  {message.processing_time && (
                    <div className="metadata">
                      <span className="processing-time">
                        ⏱️ Xử lý trong {message.processing_time.toFixed(2)}s
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default MessageList;
