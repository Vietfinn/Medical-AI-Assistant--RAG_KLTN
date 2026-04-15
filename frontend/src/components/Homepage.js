import React from 'react';
import { useClerk } from '@clerk/clerk-react';
import { Search, ArrowRight, Sparkles, Shield, Brain, Activity } from 'lucide-react';
import './Homepage.css';

const Homepage = () => {
  const { openSignIn } = useClerk();

  const handleAuthTrigger = () => {
    openSignIn({ redirectUrl: '/' });
  };

  const suggestions = [
    { icon: '🩺', text: 'Tra cứu triệu chứng' },
    { icon: '💊', text: 'Tương tác thuốc' },
    { icon: '🥗', text: 'Dinh dưỡng & Chế độ ăn' },
    { icon: '🚑', text: 'Hướng dẫn Sơ cứu' },
  ];

  const features = [
    {
      icon: <Brain size={28} />,
      title: 'Đa tác nhân AI',
      desc: 'Kết hợp Gemini 2.5 Flash và Llama 3.3 70B cho độ chính xác cao nhất.',
    },
    {
      icon: <Shield size={28} />,
      title: 'An toàn Cá nhân hóa',
      desc: 'Kiểm tra chéo với hồ sơ sức khỏe để cảnh báo chống chỉ định.',
    },
    {
      icon: <Activity size={28} />,
      title: 'Dựa trên bằng chứng',
      desc: 'Mọi phản hồi đều được trích dẫn từ nguồn y khoa đáng tin cậy.',
    },
  ];

  return (
    <div className="homepage">
      {/* Header */}
      <header className="hp-header">
        <div className="hp-logo">
          <Sparkles size={24} className="hp-logo-icon" />
          <span>Medical AI</span>
        </div>
        <button className="hp-login-btn" onClick={handleAuthTrigger}>
          Đăng nhập
          <ArrowRight size={16} />
        </button>
      </header>

      {/* Hero */}
      <main className="hp-hero">
        <div className="hp-hero-content">
          <div className="hp-badge">🩺 Trợ lý Y tế Thông minh</div>
          <h1 className="hp-title">
            Làm quen với <span className="hp-title-accent">Medical AI</span>,
            <br />
            trợ lý sức khỏe cá nhân của bạn
          </h1>
          <p className="hp-subtitle">
            Hệ thống AI đa tác nhân giúp tra cứu thông tin y tế,
            kiểm tra tương tác thuốc và cảnh báo an toàn dựa trên hồ sơ sức khỏe cá nhân.
          </p>

          {/* Fake Search Bar */}
          <div className="hp-search-wrapper" onClick={handleAuthTrigger}>
            <div className="hp-search-bar">
              <Search size={20} className="hp-search-icon" />
              <span className="hp-search-placeholder">Hỏi bất kỳ câu hỏi sức khỏe nào...</span>
              <div className="hp-search-submit">
                <ArrowRight size={18} />
              </div>
            </div>
          </div>

          {/* Suggestion Chips */}
          <div className="hp-chips">
            {suggestions.map((s, i) => (
              <button
                key={i}
                className="hp-chip"
                onClick={handleAuthTrigger}
              >
                <span>{s.icon}</span>
                <span>{s.text}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Feature Cards */}
        <div className="hp-features">
          {features.map((f, i) => (
            <div key={i} className="hp-feature-card">
              <div className="hp-feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="hp-footer">
        <p>
          <strong>Miễn trừ trách nhiệm:</strong> Medical AI Assistant là công cụ hỗ trợ thông tin,
          không phải là bác sĩ. Vui lòng luôn tham khảo ý kiến chuyên gia y tế.
        </p>
        <p className="hp-footer-copy">© 2026 Medical AI Assistant — Đồ án tốt nghiệp</p>
      </footer>
    </div>
  );
};

export default Homepage;
