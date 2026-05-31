import React from 'react';
import { useClerk } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowRight } from 'lucide-react';
import './Homepage.css';

const Homepage = () => {
  const { openSignIn } = useClerk();
  const navigate = useNavigate();

  const handleAuthTrigger = () => {
    openSignIn({ redirectUrl: '/' });
  };

  const suggestions = [
    { text: 'Tra cứu triệu chứng' },
    { text: 'Tương tác thuốc' },
    { text: 'Dinh dưỡng & Chế độ ăn' },
    { text: 'Hướng dẫn Sơ cứu' },
  ];

  return (
    <div className="homepage">
      {/* Header */}
      <header className="hp-header">
        <div className="hp-logo">
          <img src="/images/Logo_name.png" alt="A.I.M Care Logo" className="hp-logo-text" />
        </div>
        <div className="hp-header-actions">
          <button className="hp-ghost-btn" onClick={() => navigate('/about')}>
            Giới thiệu về A.I.M Care
          </button>
          <button className="hp-login-btn" onClick={handleAuthTrigger}>
            Đăng nhập
            <ArrowRight size={16} />
          </button>
        </div>
      </header>

      {/* Hero */}
      <main className="hp-hero">
        <div className="hp-hero-content">
          <div className="hp-badge">Trợ lý Y tế Thông minh</div>
          <h1 className="hp-title">
            Làm quen với <span className="hp-title-accent">A.I.M Care</span>,
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
                <span>{s.text}</span>
              </button>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="hp-footer">
        <p className="hp-disclaimer">
          Lưu ý: A.I.M Care cung cấp thông tin tham khảo dựa trên y khoa, không thay thế cho chẩn đoán hay chỉ định của bác sĩ chuyên môn.
        </p>
      </footer>
    </div>
  );
};

export default Homepage;
