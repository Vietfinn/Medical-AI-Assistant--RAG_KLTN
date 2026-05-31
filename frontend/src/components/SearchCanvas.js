import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, Clock, MessageSquare, Menu } from 'lucide-react';
import { searchSessions } from '../services/api';
import './SearchCanvas.css';

/**
 * Highlight từ khóa trong snippet bằng thẻ <mark>
 */
const highlightText = (text, keyword) => {
  if (!keyword || !text) return text;
  try {
    const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="search-highlight">{part}</mark>
      ) : (
        part
      )
    );
  } catch {
    return text;
  }
};

/**
 * Format timestamp thành nhãn thân thiện (Hôm nay, Hôm qua, 21 thg 5, ...)
 */
const formatTimeLabel = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date >= today) return 'Hôm nay';
  if (date >= yesterday) return 'Hôm qua';

  const day = date.getDate();
  const months = ['thg 1', 'thg 2', 'thg 3', 'thg 4', 'thg 5', 'thg 6',
    'thg 7', 'thg 8', 'thg 9', 'thg 10', 'thg 11', 'thg 12'];
  const month = months[date.getMonth()];

  if (date.getFullYear() === now.getFullYear()) {
    return `${day} ${month}`;
  }
  return `${day} ${month} ${date.getFullYear()}`;
};

const SearchCanvas = ({ recentSessions = [], onSelectSession, onClose, onToggleMobileSidebar }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef(null);
  const debounceTimer = useRef(null);

  // Auto-focus vào input khi mở
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  // Debounce search: chờ 500ms sau khi ngừng gõ
  const performSearch = useCallback(async (searchQuery) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setHasSearched(false);
      return;
    }
    setIsSearching(true);
    setHasSearched(true);
    try {
      const data = await searchSessions(searchQuery.trim());
      setResults(data || []);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);

    // Clear timer cũ
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Set timer mới (500ms debounce)
    debounceTimer.current = setTimeout(() => {
      performSearch(value);
    }, 500);
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setHasSearched(false);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const handleResultClick = (sessionId) => {
    if (onSelectSession) {
      onSelectSession(sessionId);
    }
  };

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  return (
    <div className="search-canvas">
      {/* Search Header */}
      <div className="search-header">
        <div className="search-header-row">
          {onToggleMobileSidebar && (
            <button
              className="mobile-hamburger-btn search-hamburger-btn"
              onClick={onToggleMobileSidebar}
              aria-label="Mở menu"
            >
              <Menu size={20} />
            </button>
          )}
          <div className="search-input-container">
            <Search size={18} className="search-input-icon" />
            <input
              ref={inputRef}
              type="text"
              className="search-input"
              placeholder="Tìm kiếm trong các cuộc trò chuyện..."
              value={query}
              onChange={handleInputChange}
            />
            {query && (
              <button className="search-clear-btn" onClick={handleClear} type="button">
                <X size={18} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Search Results */}
      <div className="search-results-area">
        {!hasSearched && !query && (
          <div className="recent-sessions-list">
            <div className="search-results-header">
              <span>Gần đây</span>
            </div>
            {recentSessions.length === 0 ? (
              <div className="search-empty-state" style={{ padding: '40px 0' }}>
                <p>Chưa có cuộc trò chuyện nào gần đây.</p>
              </div>
            ) : (
              recentSessions.map((session) => (
                <button
                  key={session._id}
                  className="recent-session-item"
                  onClick={() => handleResultClick(session._id)}
                >
                  <span className="recent-session-title">{session.title}</span>
                  <span className="recent-session-time">
                    {formatTimeLabel(session.created_at || session.updated_at)}
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        {isSearching && (
          <div className="search-loading">
            <div className="search-loading-dots">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
            <p>Đang tìm kiếm...</p>
          </div>
        )}

        {hasSearched && !isSearching && results.length === 0 && (
          <div className="search-no-results">
            <p>Không tìm thấy kết quả cho "<strong>{query}</strong>"</p>
            <span>Thử tìm kiếm bằng từ khóa khác hoặc diễn đạt ngắn gọn hơn</span>
          </div>
        )}

        {!isSearching && results.length > 0 && (
          <div className="search-results-list">
            <div className="search-results-header">
              <span>Kết quả ({results.length})</span>
            </div>
            {results.map((result) => (
              <button
                key={result._id}
                className="search-result-item"
                onClick={() => handleResultClick(result._id)}
              >
                <div className="result-left">
                  <MessageSquare size={16} className="result-icon" />
                  <div className="result-info">
                    <span className="result-title">{result.title}</span>
                    {result.snippet && (
                      <span className="result-snippet">
                        {highlightText(result.snippet, query)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="result-right">
                  <Clock size={12} className="result-time-icon" />
                  <span className="result-time">
                    {formatTimeLabel(result.created_at || result.updated_at)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchCanvas;
