import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { AlertTriangle, Info, Lightbulb, ThumbsUp, ThumbsDown, Copy, Check, FileSearch, Pencil } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import FeedbackModal from './FeedbackModal';
import { submitFeedback } from '../services/api';
import './MessageList.css';

const CitationBadge = ({ number, citation, onCitationClick }) => {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span
      className="citation-badge"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onClick={onCitationClick}
    >
      {number}
      {showTooltip && citation && (
        <span className="citation-tooltip" onClick={(e) => e.stopPropagation()}>
          <span className="tooltip-header">
            <span className="tooltip-title">Nguồn: {citation.doc_id || `Nguồn ${number}`}</span>
          </span>
          <span className="tooltip-body">
            <span className="tooltip-section">
              <span className="tooltip-label">Câu hỏi đối chiếu:</span>
              <span className="tooltip-text tooltip-question">{citation.question}</span>
            </span>
            <span className="tooltip-section">
              <span className="tooltip-label">Nội dung y khoa:</span>
              <span className="tooltip-text tooltip-answer">{citation.answer}</span>
            </span>
          </span>
        </span>
      )}
    </span>
  );
};

const SUGGESTIONS_DELIMITER = '[SUGGESTIONS]';

const stripMarkdown = (md) => {
  if (!md) return '';
  return md
    .replace(/```[a-zA-Z]*\n([\s\S]*?)```/g, '$1') // Bỏ ký hiệu code block but giữ nội dung
    .replace(/^#+\s+/gm, '') // Bỏ headers
    .replace(/(\*\*|__)(.*?)\1/g, '$2') // Bỏ bold
    .replace(/(\*|_)(.*?)\1/g, '$2') // Bỏ italic
    .replace(/^\s*>\s+/gm, '') // Bỏ blockquote
    .replace(/`([^`]+)`/g, '$1') // Bỏ inline code
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Bỏ links
    .replace(/^\s*[-*+]\s+/gm, '') // Bỏ bullet points
    .replace(/^\s*\d+\.\s+/gm, '') // Bỏ numbered list
    .replace(/\n{3,}/g, '\n\n') // Bỏ dòng trống thừa
    .trim();
};

const getStringContent = (children) => {
  let text = '';
  React.Children.forEach(children, (child) => {
    if (typeof child === 'string') {
      text += child;
    } else if (child && child.props) {
      if (typeof child.props.children === 'string') {
        text += child.props.children;
      } else if (Array.isArray(child.props.children) || React.isValidElement(child.props.children)) {
        text += getStringContent(child.props.children);
      }
    }
  });
  return text;
};

const processAlertText = (children, isSafety) => {
  return React.Children.map(children, (child) => {
    if (typeof child === 'string') {
      let text = child;
      if (isSafety) {
        text = text.replace(/⚠️\s*/g, '');
        if (text.includes('CẢNH BÁO AN TOÀN')) {
          const parts = text.split('CẢNH BÁO AN TOÀN:');
          if (parts.length > 1) {
            return (
              <>
                <strong>CẢNH BÁO AN TOÀN:</strong>
                {parts.slice(1).join('CẢNH BÁO AN TOÀN:')}
              </>
            );
          }
        }
      } else {
        if (text.trim().startsWith('Lưu ý:')) {
          const colonIndex = text.indexOf('Lưu ý:');
          const pre = text.substring(0, colonIndex);
          const post = text.substring(colonIndex + 6);
          return (
            <>
              {pre}<strong>Lưu ý:</strong>{post}
            </>
          );
        }
      }
      return text;
    }
    
    if (React.isValidElement(child)) {
      let childChildren = child.props.children;
      if (child.type === 'strong' || child.type === 'b') {
        let text = getStringContent(childChildren);
        if (isSafety) {
          text = text.replace(/⚠️\s*/g, '').replace(/CẢNH BÁO AN TOÀN:?\s*/g, 'CẢNH BÁO AN TOÀN:');
          return <strong>{text}</strong>;
        } else {
          if (text.trim().startsWith('Lưu ý:')) {
            text = text.replace(/Lưu ý:?\s*/g, 'Lưu ý:');
            return <strong>{text}</strong>;
          }
        }
      }
      
      if (childChildren) {
        return React.cloneElement(child, {
          children: processAlertText(childChildren, isSafety)
        });
      }
    }
    return child;
  });
};

const MessageList = ({
  messages,
  streamingContent,
  isStreaming,
  safetyReviewing,
  lastUserMsgRef,
  suggestions,
  onSuggestionClick,
  currentSessionId,
  onViewSource,
  onEditMessage,
  onCitationClick,
}) => {
  const [editingIndex, setEditingIndex] = useState(null);
  const [editText, setEditText] = useState('');
  const [newChunkClass, setNewChunkClass] = useState('');
  const [feedbackStates, setFeedbackStates] = useState({});
  const [feedbackModal, setFeedbackModal] = useState(null);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [isFeedbackLoading, setIsFeedbackLoading] = useState({});
  const [toast, setToast] = useState(null);
  const toastTimeoutRef = useRef(null);

  const showToast = useCallback((message, type = 'success') => {
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    setToast({ message, type });
    toastTimeoutRef.current = setTimeout(() => {
      setToast(null);
    }, 3000);
  }, []);

  const getMessageContent = (content) => {
    if (!content) return '';
    const dIdx = content.indexOf(SUGGESTIONS_DELIMITER);
    if (dIdx !== -1) {
      return content.substring(0, dIdx).replace(/[*\s]+$/, '');
    }
    return content;
  };

  const handleCopy = useCallback((rawMarkdown, index) => {
    const plainText = stripMarkdown(rawMarkdown);
    
    try {
      // Chuyển đổi markdown cơ bản thành HTML đơn giản để dán có định dạng
      const htmlContent = rawMarkdown
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br/>');

      const blobHtml = new Blob([htmlContent], { type: 'text/html' });
      const blobText = new Blob([plainText], { type: 'text/plain' });
      
      const data = [new ClipboardItem({
        'text/html': blobHtml,
        'text/plain': blobText
      })];
      
      navigator.clipboard.write(data).then(() => {
        setCopiedIndex(index);
        setTimeout(() => setCopiedIndex(null), 2000);
      });
    } catch (err) {
      // Fallback nếu trình duyệt cũ không hỗ trợ ClipboardItem phức tạp hoặc lỗi bảo mật clipboard
      navigator.clipboard.writeText(plainText).then(() => {
        setCopiedIndex(index);
        setTimeout(() => setCopiedIndex(null), 2000);
      });
    }
  }, []);

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

  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return i;
    }
    return -1;
  })();

  const displayStreamingContent = useMemo(() => {
    if (!streamingContent) return '';
    const delimiterPos = streamingContent.indexOf(SUGGESTIONS_DELIMITER);
    if (delimiterPos !== -1) {
      return streamingContent.substring(0, delimiterPos).trim();
    }
    return streamingContent;
  }, [streamingContent]);

  const showSuggestions = !isStreaming && suggestions && suggestions.length > 0;

  const parseText = useCallback((text) => {
    if (typeof text !== 'string') return [text];
    const regex = /\[(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }
      parts.push({ type: 'citation', number: parseInt(match[1], 10) });
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }
    return parts.length > 0 ? parts : [text];
  }, []);

  const createMarkdownComponents = useCallback((message) => {
    const processChildren = (children) => {
      return React.Children.map(children, (child) => {
        if (typeof child === 'string') {
          const parsed = parseText(child);
          return parsed.map((part, idx) => {
            if (typeof part === 'string') {
              return part;
            }
            if (part.type === 'citation') {
              const num = part.number;
              const citations = message ? message.citations : null;
              const citation = citations && citations[num - 1];
              if (!citation) return `[${num}]`;
              return (
                <CitationBadge
                  key={idx}
                  number={num}
                  citation={citation}
                  onCitationClick={() => onCitationClick && onCitationClick(message, num)}
                />
              );
            }
            return null;
          });
        }
        if (React.isValidElement(child) && child.props.children) {
          return React.cloneElement(child, {
            children: processChildren(child.props.children)
          });
        }
        return child;
      });
    };

    return {
      p: ({ children }) => {
        const textContent = getStringContent(children);
        if (textContent.includes('⚠️ CẢNH BÁO AN TOÀN') || textContent.includes('CẢNH BÁO AN TOÀN:')) {
          return (
            <div className="safety-alert-paragraph">
              {processAlertText(processChildren(children), true)}
            </div>
          );
        }
        if (textContent.trim().startsWith('Lưu ý:')) {
          return (
            <div className="note-alert-paragraph">
              {processAlertText(processChildren(children), false)}
            </div>
          );
        }
        return <p>{processChildren(children)}</p>;
      },
      li: ({ children }) => <li>{processChildren(children)}</li>,
      h1: ({ children }) => <h1>{processChildren(children)}</h1>,
      h2: ({ children }) => <h2>{processChildren(children)}</h2>,
      h3: ({ children }) => <h3>{processChildren(children)}</h3>,
      blockquote: ({ children }) => {
        const textContent = getStringContent(children);
        if (textContent.includes('⚠️ CẢNH BÁO AN TOÀN') || textContent.includes('CẢNH BÁO AN TOÀN:')) {
          return (
            <div className="safety-alert-paragraph">
              {processAlertText(processChildren(children), true)}
            </div>
          );
        }
        if (textContent.trim().startsWith('Lưu ý:')) {
          return (
            <div className="note-alert-paragraph">
              {processAlertText(processChildren(children), false)}
            </div>
          );
        }
        return <blockquote>{processChildren(children)}</blockquote>;
      },
    };
  }, [parseText, onCitationClick]);

  /* ---- Feedback handlers ---- */

  const handleLike = useCallback(async (message, index) => {
    if (isFeedbackLoading[index]) return;

    const currentRating = feedbackStates[index]?.rated;
    const newRating = currentRating === 'like' ? 0 : 1;
    const newRatedState = currentRating === 'like' ? null : 'like';

    const previousStates = { ...feedbackStates };
    setFeedbackStates((prev) => {
      const next = { ...prev };
      if (newRatedState) next[index] = { rated: newRatedState };
      else delete next[index];
      return next;
    });

    if (newRating === 1) {
      showToast("Cám ơn bạn đã đánh giá hữu ích!");
    } else {
      showToast("Đã hủy đánh giá.");
    }

    const prevUserMsg = (() => {
      for (let i = index - 1; i >= 0; i--) {
        if (messages[i].role === 'user') return messages[i].content;
      }
      return '';
    })();

    try {
      await submitFeedback({
        interaction_id: message.id || `msg_${index}`,
        session_id: currentSessionId || '',
        query: prevUserMsg,
        ai_response: getMessageContent(message.content),
        retrieved_sources: message.citations || [],
        rating: newRating,
        reason_tags: [],
        text_feedback: '',
      });
    } catch (err) {
      console.warn('[Feedback] Like failed:', err);
      setFeedbackStates(previousStates);
      showToast("Kết nối thất bại. Vui lòng thử lại.", "error");
    }
  }, [feedbackStates, messages, currentSessionId, isFeedbackLoading, showToast]);

  const handleDislike = useCallback(async (message, index) => {
    if (isFeedbackLoading[index]) return;

    const currentRating = feedbackStates[index]?.rated;

    if (currentRating === 'dislike') {
      const previousStates = { ...feedbackStates };
      setFeedbackStates((prev) => {
        const next = { ...prev };
        delete next[index];
        return next;
      });
      showToast("Đã hủy đánh giá.");
      setIsFeedbackLoading((prev) => ({ ...prev, [index]: true }));

      const prevUserMsg = (() => {
        for (let i = index - 1; i >= 0; i--) {
          if (messages[i].role === 'user') return messages[i].content;
        }
        return '';
      })();

      try {
        await submitFeedback({
          interaction_id: message.id || `msg_${index}`,
          session_id: currentSessionId || '',
          query: prevUserMsg,
          ai_response: getMessageContent(message.content),
          retrieved_sources: message.citations || [],
          rating: 0,
          reason_tags: [],
          text_feedback: '',
        });
      } catch (err) {
        console.warn('[Feedback] Un-dislike failed:', err);
        setFeedbackStates(previousStates);
        showToast("Kết nối thất bại. Vui lòng thử lại.", "error");
      } finally {
        setIsFeedbackLoading((prev) => ({ ...prev, [index]: false }));
      }
    } else {
      setFeedbackModal({ message, index });
    }
  }, [feedbackStates, messages, currentSessionId, isFeedbackLoading, showToast]);

  const handleFeedbackSubmit = useCallback(async ({ reason_tags, text_feedback }) => {
    if (!feedbackModal) return;
    const { message, index } = feedbackModal;

    const previousStates = { ...feedbackStates };
    setFeedbackStates((prev) => ({ ...prev, [index]: { rated: 'dislike' } }));
    setFeedbackModal(null);
    showToast("Cám ơn bạn đã gửi đánh giá chi tiết!");
    setIsFeedbackLoading((prev) => ({ ...prev, [index]: true }));

    const prevUserMsg = (() => {
      for (let i = index - 1; i >= 0; i--) {
        if (messages[i].role === 'user') return messages[i].content;
      }
      return '';
    })();

    try {
      await submitFeedback({
        interaction_id: message.id || `msg_${index}`,
        session_id: currentSessionId || '',
        query: prevUserMsg,
        ai_response: getMessageContent(message.content),
        retrieved_sources: message.citations || [],
        rating: -1,
        reason_tags,
        text_feedback,
      });
    } catch (err) {
      console.warn('[Feedback] Dislike submit failed:', err);
      setFeedbackStates(previousStates);
      showToast("Kết nối thất bại. Vui lòng thử lại.", "error");
    } finally {
      setIsFeedbackLoading((prev) => ({ ...prev, [index]: false }));
    }
  }, [feedbackModal, messages, currentSessionId, feedbackStates, showToast]);

  const handleModalClose = useCallback(() => {
    if (feedbackModal) {
      const { index } = feedbackModal;
      setFeedbackStates((prev) => {
        const next = { ...prev };
        if (next[index]?.rated === 'dislike') delete next[index];
        return next;
      });
    }
    setFeedbackModal(null);
  }, [feedbackModal]);

  /* ---- Edit question handler ---- */

  const handleEditKeyDown = (e, originalContent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const trimmed = editText.trim();
      const original = originalContent.trim();
      if (trimmed && trimmed !== original) {
        if (onEditMessage) {
          onEditMessage(trimmed);
        }
        setEditingIndex(null);
      }
    }
  };

  return (
    <div className="message-list">
      {messages.map((message, index) => (
        <div
          key={index}
          className={`message ${message.role}${message.role === 'user' ? ' fade-in' : ''}`}
          ref={message.role === 'user' && index === lastUserIndex ? lastUserMsgRef : null}
        >
          {message.role === 'user' ? (
            <div className="user-row">
              {editingIndex === index ? (
                <div className="edit-bubble-container">
                  <textarea
                    className="edit-textarea"
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => handleEditKeyDown(e, message.content)}
                    rows={Math.max(1, editText.split('\n').length)}
                    autoFocus
                    spellCheck={false}
                  />
                  <div className="edit-actions">
                    <button
                      type="button"
                      className="edit-cancel-btn"
                      onClick={() => setEditingIndex(null)}
                    >
                      Hủy
                    </button>
                    <button
                      type="button"
                      className="edit-update-btn"
                      disabled={editText.trim() === message.content.trim() || !editText.trim()}
                      onClick={() => {
                        if (onEditMessage) {
                          onEditMessage(editText.trim());
                        }
                        setEditingIndex(null);
                      }}
                    >
                      Cập nhật
                    </button>
                  </div>
                </div>
              ) : (
                <div className="user-message-container">
                  <div className="user-bubble">{message.content}</div>
                  {!isStreaming && (
                    <div className="user-action-bar">
                      <button
                        type="button"
                        className={`user-action-btn ${copiedIndex === index ? 'active-copy' : ''}`}
                        onClick={() => handleCopy(message.content, index)}
                        data-tooltip={copiedIndex === index ? "Đã sao chép!" : "Sao chép câu hỏi"}
                        aria-label="Sao chép câu hỏi"
                      >
                        {copiedIndex === index ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                      {index === lastUserIndex && (
                        <button
                          type="button"
                          className="user-edit-btn"
                          onClick={() => {
                            setEditingIndex(index);
                            setEditText(message.content);
                          }}
                          data-tooltip="Chỉnh sửa câu hỏi"
                          aria-label="Chỉnh sửa câu hỏi"
                        >
                          <Pencil size={14} />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="assistant-row">
              <div className="assistant-avatar">
                <img src="/images/Logo_chat.png?v=20260417" alt="A.I.M Care" className="assistant-avatar-img" />
              </div>

              <div className="assistant-content">
                {/* Markdown answer */}
                <div className="answer-text markdown-body">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={createMarkdownComponents(message)}
                  >
                    {getMessageContent(message.content)}
                  </ReactMarkdown>
                </div>

                {/* Action bar — Like / Dislike / Copy / View Source / Time */}
                {!isStreaming && (
                  <div className="assistant-action-bar">
                    <button
                      type="button"
                      className={`action-btn like ${feedbackStates[index]?.rated === 'like' ? 'active' : ''}`}
                      onClick={() => handleLike(message, index)}
                      disabled={isFeedbackLoading[index]}
                      data-tooltip="Hữu ích"
                      aria-label="Đánh giá hữu ích"
                    >
                      <ThumbsUp size={15} />
                    </button>
                    <button
                      type="button"
                      className={`action-btn dislike ${feedbackStates[index]?.rated === 'dislike' ? 'active' : ''}`}
                      onClick={() => handleDislike(message, index)}
                      disabled={isFeedbackLoading[index]}
                      data-tooltip="Chưa hài lòng"
                      aria-label="Đánh giá chưa hài lòng"
                    >
                      <ThumbsDown size={15} />
                    </button>
                    <button
                      type="button"
                      className={`action-btn copy ${copiedIndex === index ? 'active-copy' : ''}`}
                      onClick={() => handleCopy(getMessageContent(message.content), index)}
                      data-tooltip={copiedIndex === index ? "Đã sao chép!" : "Sao chép câu trả lời"}
                      aria-label="Sao chép câu trả lời"
                    >
                      {copiedIndex === index ? <Check size={15} /> : <Copy size={15} />}
                    </button>
                    {message.citations && message.citations.length > 0 && (
                      <button
                        type="button"
                        className="action-btn source"
                        onClick={() => onViewSource && onViewSource(message)}
                        data-tooltip="Xem nguồn tham khảo"
                        aria-label="Xem nguồn tham khảo"
                      >
                        <FileSearch size={15} />
                      </button>
                    )}
                    {message.processing_time && (
                      <>
                        <div className="action-bar-divider" />
                        <span className="action-time">⏱ {message.processing_time.toFixed(2)}s</span>
                      </>
                    )}
                  </div>
                )}

                {/* Follow-up suggestions — only on last assistant message */}
                {showSuggestions && index === lastAssistantIndex && (
                  <div className="suggestions-followup fade-in">
                    <div className="suggestions-followup-label">
                      <Lightbulb size={14} />
                      <span>CÁC CÂU HỎI LIÊN QUAN</span>
                    </div>
                    <div className="suggestions-followup-list">
                      {suggestions.map((text, sIdx) => (
                        <button
                          key={sIdx}
                          className="suggestion-followup-btn"
                          onClick={() => onSuggestionClick && onSuggestionClick(text)}
                        >
                          {text}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* Streaming message */}
      {isStreaming && displayStreamingContent && (
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
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={createMarkdownComponents(null)}
                >
                  {displayStreamingContent}
                </ReactMarkdown>
                <span className="streaming-cursor" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Feedback Modal */}
      {feedbackModal && (
        <FeedbackModal
          onClose={handleModalClose}
          onSubmit={handleFeedbackSubmit}
        />
      )}

      {/* Toast Notification */}
      {toast && (
        <div className={`feedback-toast ${toast.type}`}>
          {toast.type === 'success' && <Check size={16} />}
          {toast.type === 'error' && <AlertTriangle size={16} />}
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
};

export default MessageList;
