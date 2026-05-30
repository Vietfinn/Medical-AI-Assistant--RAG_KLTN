import React, { useState, useRef, useEffect } from 'react';
import { ArrowRight, HeartPulse, Sparkles } from 'lucide-react';
import './HealthCornerCreate.css';

const HealthCornerCreate = ({ onConfirm, onCancel }) => {
  const [name, setName] = useState('');
  const [emoji] = useState('🩺'); // Keep default emoji as 🩺, no longer selecting in creation screen
  const inputRef = useRef(null);

  useEffect(() => {
    // Auto-focus input field on mount
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (trimmed) {
      onConfirm(trimmed, emoji);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSubmit();
    } else if (e.key === 'Escape') {
      onCancel();
    }
  };

  return (
    <div className="corner-create-canvas">
      <div className="corner-create-content">
        
        {/* HeartPulse Icon at the top (centered) */}
        <div className="corner-create-icon">
          <HeartPulse size={48} strokeWidth={1.5} />
        </div>

        {/* Heading */}
        <h1 className="corner-create-heading">
          Đặt tên cho Góc sức khỏe của bạn
        </h1>

        {/* Centered Input area */}
        <div className="corner-create-input-wrapper">
          <input
            ref={inputRef}
            type="text"
            className="corner-create-input"
            placeholder="Góc sức khỏe mới"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={100}
          />
          <button
            className={`corner-create-submit-btn ${name.trim() ? 'visible' : ''}`}
            onClick={handleSubmit}
            disabled={!name.trim()}
            title="Tạo Góc sức khỏe"
          >
            <ArrowRight size={22} />
          </button>
        </div>

        {/* Tip Card (Gemini Sparkle card style) */}
        <div className="corner-create-tip-card">
          <Sparkles className="corner-tip-spark-icon" size={18} />
          <p className="corner-tip-text">
            Góc sức khỏe giúp bạn gom nhóm các cuộc trò chuyện theo chủ đề bệnh lý. 
            Bạn có thể thêm ngữ cảnh để A.I.M Care hiểu rõ tình trạng sức khỏe của bạn hơn.
          </p>
        </div>

      </div>
    </div>
  );
};

export default HealthCornerCreate;
