import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, ArrowDown, Square, X, Menu, MoreVertical, Pin, PinOff, Edit2, Trash2, FolderPlus, HeartPulse, RefreshCw, Check } from 'lucide-react';
import { pinSession, renameSession } from '../services/api';
import MessageList from './MessageList';
import Citation from './Citation';
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
  suggestions,
  currentSessionId,
  onEditMessage,
  activeCorner,
  onOpenCorner,
  onToggleMobileSidebar,
  sessions,
  healthCorners,
  onRefreshSessions,
  onDeleteSession,
  onAssignSession,
  onUpdateCorner,
  onDeleteCorner,
}) => {
  const [input, setInput] = useState('');
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [selectedSourceMsg, setSelectedSourceMsg] = useState(null);
  const [activeCitationIndex, setActiveCitationIndex] = useState(0);
  const [isChatScrolling, setIsChatScrolling] = useState(false);
  const [isOptionsMenuOpen, setIsOptionsMenuOpen] = useState(false);
  const [renameData, setRenameData] = useState(null);
  const [deleteData, setDeleteData] = useState(null);
  const [isActionProcessing, setIsActionProcessing] = useState(false);
  const [assignSessionData, setAssignSessionData] = useState(null);
  const [isAssigning, setIsAssigning] = useState(false);
  const [chatToast, setChatToast] = useState(null);
  const optionsMenuRef = useRef(null);
  const scrollTimeoutRef = useRef(null);
  const chatContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const isUserScrollingRef = useRef(false);
  const lastUserMsgRef = useRef(null);
  const spacerRef = useRef(null);
  const justSentRef = useRef(false);
  const firstMessageRef = useRef(null);
  const firstLoadRef = useRef(true);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (optionsMenuRef.current && !optionsMenuRef.current.contains(event.target) && !event.target.closest('.canvas-options-btn')) {
        setIsOptionsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const showToastNotification = (message) => {
    setChatToast(message);
    setTimeout(() => {
      setChatToast(null);
    }, 3000);
  };

  const handlePin = async (e, session) => {
    e.stopPropagation();
    setIsOptionsMenuOpen(false);
    try {
      await pinSession(session._id, !session.is_pinned);
      if (onRefreshSessions) onRefreshSessions();
      showToastNotification(session.is_pinned ? 'Đã bỏ ghim cuộc trò chuyện!' : 'Đã ghim cuộc trò chuyện!');
    } catch (error) {
      console.error('Lỗi khi ghim/bỏ ghim:', error);
    }
  };

  const handleRenameSave = async () => {
    if (!renameData.title.trim() || isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      await renameSession(renameData.id, renameData.title);
      if (onRefreshSessions) onRefreshSessions();
      showToastNotification('Đã đổi tên cuộc trò chuyện thành công!');
    } catch (error) {
      console.error('Lỗi khi đổi tên:', error);
    } finally {
      setIsActionProcessing(false);
      setRenameData(null);
    }
  };

  const handleRenameCancel = () => {
    setRenameData(null);
  };

  const handleDeleteConfirm = async () => {
    if (isActionProcessing) return;
    setIsActionProcessing(true);
    try {
      await onDeleteSession(deleteData.id);
      showToastNotification('Đã xóa cuộc trò chuyện thành công!');
    } catch (error) {
      console.error('Lỗi khi xóa cuộc trò chuyện:', error);
    } finally {
      setIsActionProcessing(false);
      setDeleteData(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteData(null);
  };
  const prevMessagesLengthRef = useRef(0);

  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

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
      container.scrollTo({ top: offset - 30, behavior: 'smooth' });
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

  /* Scroll user question to top when messages change (e.g. after edit) */
  useEffect(() => {
    if (messages.length > 0 && messages.length !== prevMessagesLengthRef.current) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === 'user' && messages.length <= prevMessagesLengthRef.current) {
        requestAnimationFrame(() => {
          updateSpacer();
          scrollUserToTop();
        });
      }
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages, updateSpacer, scrollUserToTop]);

  const handleScroll = () => {
    const container = chatContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;

    setShowScrollBtn(distanceFromBottom > 150);

    if (isStreaming) {
      isUserScrollingRef.current = distanceFromBottom > 80;
    }

    // Auto-hide scrollbar after 1 second of scroll inactivity
    setIsChatScrolling(true);
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    scrollTimeoutRef.current = setTimeout(() => {
      setIsChatScrolling(false);
    }, 1000);
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

  const welcomeSuggestions = [
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

  const handleViewSource = (message) => {
    if (selectedSourceMsg && selectedSourceMsg === message) {
      setSelectedSourceMsg(null);
    } else {
      setSelectedSourceMsg(message);
      setActiveCitationIndex(0);
    }
  };

  const handleCitationClick = useCallback((message, citationNumber) => {
    setSelectedSourceMsg(message);
    setActiveCitationIndex(citationNumber - 1);
  }, []);

  const topbarTitle = activeCorner
    ? `${activeCorner.emoji || '📁'} ${activeCorner.name}`
    : conversationTitle;

  return (
    <div className={`chat-canvas ${selectedSourceMsg ? 'source-panel-open' : ''} ${isChatScrolling ? 'is-chat-scrolling' : ''}`}>
      <div className="chat-topbar">
        <div className="chat-topbar-left">
          {onToggleMobileSidebar && (
            <button
              className="mobile-hamburger-btn"
              onClick={onToggleMobileSidebar}
              aria-label="Mở menu"
            >
              <Menu size={20} />
            </button>
          )}
        </div>

        <h2 className="chat-topbar-title">{topbarTitle}</h2>

        <div className="chat-topbar-right">
          {currentSessionId && (
            <div className="canvas-options-wrapper" ref={optionsMenuRef}>
              <button
                className={`canvas-options-btn ${isOptionsMenuOpen ? 'active' : ''}`}
                onClick={() => setIsOptionsMenuOpen(!isOptionsMenuOpen)}
              >
                <MoreVertical size={20} />
              </button>
              {isOptionsMenuOpen && (
                (() => {
                  const session = sessions?.find(s => s._id === currentSessionId);
                  if (!session) return null;
                  const isInCorner = !!session.corner_id;
                  return (
                    <div className="canvas-options-menu fade-in">
                      {isInCorner ? (
                        <>
                          {healthCorners?.length > 0 && (
                            <button className="option-item" onClick={(e) => {
                              setIsOptionsMenuOpen(false);
                              setAssignSessionData({ id: session._id, title: session.title });
                            }}>
                              <FolderPlus size={14}/> Chuyển sang góc khác
                            </button>
                          )}
                          <button className="option-item" onClick={async (e) => {
                            setIsOptionsMenuOpen(false);
                            try {
                              await onAssignSession(session._id, null);
                              showToastNotification('Đã gỡ cuộc trò chuyện khỏi Góc sức khỏe!');
                            } catch (err) {
                              console.error('Lỗi khi xóa khỏi góc:', err);
                            }
                          }}>
                            <X size={14}/> Xóa khỏi góc
                          </button>
                        </>
                      ) : (
                        <>
                          <button className="option-item" onClick={(e) => handlePin(e, session)}>
                            {session.is_pinned ? (
                              <><PinOff size={14}/> Bỏ ghim</>
                            ) : (
                              <><Pin size={14}/> Ghim</>
                            )}
                          </button>
                          {healthCorners?.length > 0 && (
                            <button className="option-item" onClick={(e) => {
                              setIsOptionsMenuOpen(false);
                              setAssignSessionData({ id: session._id, title: session.title });
                            }}>
                              <FolderPlus size={14}/> Đưa vào Góc sức khỏe
                            </button>
                          )}
                        </>
                      )}
                      <button className="option-item" onClick={(e) => { setIsOptionsMenuOpen(false); setRenameData({ id: session._id, title: session.title, type: 'session' }); }}>
                        <Edit2 size={14}/> Đổi tên
                      </button>
                      <button className="option-item danger" onClick={(e) => { setIsOptionsMenuOpen(false); setDeleteData({ id: session._id, title: session.title, type: 'session' }); }}>
                        <Trash2 size={14}/> Xoá
                      </button>
                    </div>
                  );
                })()
              )}
            </div>
          )}
        </div>
      </div>

      <div className="chat-body">
        <div className="chat-content">
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
                  {welcomeSuggestions.map((text, i) => (
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
                  suggestions={suggestions}
                  onSuggestionClick={handleSuggestion}
                  currentSessionId={currentSessionId}
                  onViewSource={handleViewSource}
                  onEditMessage={onEditMessage}
                  onCitationClick={handleCitationClick}
                />

                {/* Status indicator — replaces typing dots during pipeline phases */}
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

                {/* Dynamic spacer — LAST element in scroll container */}
                <div ref={spacerRef} className="dynamic-spacer" />
              </>
            )}
          </div>

          {showScrollBtn && (
            <button
              className="scroll-bottom-btn"
              onClick={() => scrollToBottom()}
              title="Cuộn xuống cuối"
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
                  placeholder="Nhập câu hỏi về sức khỏe..."
                  disabled={isLoading}
                  rows={1}
                  className="chat-textarea"
                  spellCheck={false}
                />
                {isLoading || isStreaming ? (
                  <button
                    type="button"
                    onClick={onStopGeneration}
                    className="send-btn stop-btn"
                    title="Dừng xử lý"
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
              Thông tin chỉ mang tính tham khảo. Vui lòng tham khảo ý kiến bác sĩ chuyên khoa.
            </p>
          </div>
        </div>

        {/* Side Panel — Citations / Sources */}
        <div className={`chat-source-panel ${selectedSourceMsg ? 'open' : ''}`}>
          {selectedSourceMsg && (
            <div className="source-panel-inner">
              <div className="source-panel-header">
                <h3>Nguồn</h3>
                <button
                  className="source-panel-close"
                  onClick={() => setSelectedSourceMsg(null)}
                  aria-label="Đóng"
                >
                  <X size={18} />
                </button>
              </div>
              <div className="source-panel-body">
                {selectedSourceMsg.citations && selectedSourceMsg.citations.length > 0 ? (
                  <Citation
                    citations={selectedSourceMsg.citations}
                    initialActiveIndex={activeCitationIndex}
                  />
                ) : (
                  <p className="source-panel-empty">Không có nguồn tham khảo cho tin nhắn này.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Rename Confirmation Modal */}
      {renameData && (
        <div className="modal-overlay" style={{ zIndex: 3000 }}>
          <div className="modal-content rename-modal">
            <h3>{renameData.type === 'corner' ? 'Đổi tên cho Góc sức khỏe' : 'Đổi tên cho cuộc trò chuyện này'}</h3>
            <input
              autoFocus
              className="modal-rename-input"
              value={renameData.title}
              onChange={(e) => setRenameData({ ...renameData, title: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameSave();
                if (e.key === 'Escape') handleRenameCancel();
              }}
            />
            <div className="modal-actions">
              <button className="modal-btn cancel-text" onClick={handleRenameCancel} disabled={isActionProcessing}>Huỷ</button>
              <button className="modal-btn save-text" onClick={handleRenameSave} disabled={isActionProcessing}>{isActionProcessing ? 'Đang lưu...' : 'Đổi tên'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteData && (
        <div className="modal-overlay" style={{ zIndex: 3100 }}>
          <div className="modal-content">
            {deleteData.type === 'corner' ? (
              <>
                <h3>Xóa Góc sức khỏe?</h3>
                <p style={{ lineHeight: '1.6', fontSize: '0.92rem', color: 'var(--text-secondary, #94a3b8)' }}>
                  Bạn có chắc chắn muốn xóa Góc sức khỏe <strong>"{deleteData.title}"</strong> không?
                  <br />
                  <span style={{ color: 'var(--accent-blue, #3b82f6)', fontWeight: '500' }}>Lưu ý:</span> Các cuộc trò chuyện bên trong Góc sẽ <strong style={{ color: 'var(--text-primary, #e2e8f0)' }}>không bị xóa</strong>. Chúng sẽ được tự động chuyển ra danh sách "Gần đây" ở thanh bên.
                </p>
                <div className="modal-actions">
                  <button className="modal-btn cancel" onClick={handleDeleteCancel} disabled={isActionProcessing}>Huỷ</button>
                  <button className="modal-btn delete" onClick={handleDeleteConfirm} disabled={isActionProcessing}>{isActionProcessing ? 'Đang xóa...' : 'Xóa'}</button>
                </div>
              </>
            ) : (
              <>
                <h3>Xoá cuộc hội thoại?</h3>
                <p>Bạn có chắc chắn muốn xoá cuộc hội thoại <strong>"{deleteData.title}"</strong> không? Hành động này không thể hoàn tác.</p>
                <div className="modal-actions">
                  <button className="modal-btn cancel" onClick={handleDeleteCancel} disabled={isActionProcessing}>Huỷ</button>
                  <button className="modal-btn delete" onClick={handleDeleteConfirm} disabled={isActionProcessing}>{isActionProcessing ? 'Đang xóa...' : 'Xoá'}</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Assign Session to Corner Modal */}
      {assignSessionData && (
        <div className="modal-overlay" style={{ zIndex: 3200 }}>
          <div className="modal-content assign-modal">
            <div className="assign-modal-header">
              <h3>Di chuyển cuộc trò chuyện</h3>
              <button className="close-btn" onClick={() => !isAssigning && setAssignSessionData(null)} disabled={isAssigning}>
                <X size={18} />
              </button>
            </div>
            <p className="assign-modal-sub">
              Chọn một Góc sức khỏe bạn muốn chuyển cuộc trò chuyện này vào
            </p>
            <div className="assign-corners-list">
              {isAssigning ? (
                <div className="assign-loading">
                  <RefreshCw size={24} className="spin" />
                  <p>Đang di chuyển cuộc trò chuyện...</p>
                </div>
              ) : (
                healthCorners.map(corner => (
                  <button
                    key={corner._id}
                    className="assign-corner-item"
                    disabled={isAssigning}
                    onClick={async () => {
                      setIsAssigning(true);
                      try {
                        await onAssignSession(assignSessionData.id, corner._id);
                        setAssignSessionData(null);
                        showToastNotification(`Đã di chuyển cuộc trò chuyện vào Góc "${corner.name}" thành công!`);
                      } catch (err) {
                        console.error("Error moving session:", err);
                      } finally {
                        setIsAssigning(false);
                      }
                    }}
                  >
                    <HeartPulse size={18} className="assign-corner-icon" />
                    <span className="assign-corner-name">{corner.name}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Chat Toast Notification */}
      {chatToast && (
        <div className="sidebar-toast-notification" style={{ zIndex: 4000 }}>
          <Check size={16} style={{ color: '#22c55e' }} />
          <span>{chatToast}</span>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
