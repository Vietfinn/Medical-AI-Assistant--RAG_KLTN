import React from 'react';
import { useClerk } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import './About.css';

const About = () => {
  const { openSignIn } = useClerk();
  const navigate = useNavigate();

  const handleAuthTrigger = () => {
    openSignIn({ redirectUrl: '/' });
  };

  return (
    <div className="about-page">
      {/* Header — reuses Homepage layout */}
      <header className="about-header">
        <div className="about-logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <img src="/images/Logo_name.png" alt="A.I.M Care Logo" className="about-logo-img" />
        </div>
        <div className="about-header-actions">
          <button className="about-try-btn" onClick={handleAuthTrigger}>
            Dùng thử
            <ArrowRight size={16} />
          </button>
        </div>
      </header>

      {/* ========== 1. Hero ========== */}
      <section className="about-hero">
        <span className="about-badge">VỀ CHÚNG TÔI</span>
        <h1 className="about-hero-title">
          Định hình lại cách bạn tiếp cận y tế số cùng{' '}
          <span className="about-brand-gradient">A.I.M Care</span>
        </h1>
        <p className="about-hero-subtitle">
          Hệ thống Trợ lý Y khoa thế hệ mới, vận hành trên nền tảng kiến trúc Đa tác nhân
          (Multi-Agent), mang đến thông tin sức khỏe chính xác và tận tâm.
        </p>
      </section>

      {/* ========== 2. Vision ========== */}
      <section className="about-vision">
        <div className="about-vision-text">
          <h2>Giải quyết "nỗi đau" thông tin y tế</h2>
          <p>
            Giữa kỷ nguyên số, người dùng dễ dàng bị choáng ngợp và bối rối trước hàng triệu
            luồng thông tin y tế nhiễu loạn, dẫn đến việc tự chẩn đoán sai lệch.
          </p>
          <p>
            Tầm nhìn của chúng tôi là biến <strong>A.I.M Care</strong> thành một trợ lý Y Khoa đáng tin cậy.
            Không chỉ đơn thuần là tìm kiếm từ khóa, hệ thống thấu hiểu ngữ
            cảnh, kiểm chứng chéo thông tin và đưa ra lời khuyên an toàn nhất cho từng cá nhân.
          </p>
        </div>
        <div className="about-vision-image">
          <img src="/images/logo_about.png?v=20260417" alt="A.I.M Care Vision" />
        </div>
      </section>

      {/* ========== 3. Core Pillars — A.I.M ========== */}
      <section className="about-pillars">
        <h2 className="about-pillars-title">
          Giải mã kiến trúc lõi của <strong>A.I.M Care</strong>
        </h2>

        <div className="about-pillars-grid">
          {/* Card A */}
          <div className="pillar-card pillar-blue">
            <div className="pillar-letter">A</div>
            <h3>Agile — Nhanh nhẹn &amp; Linh hoạt</h3>
            <p>
              Tốc độ là yếu tố sống còn. Thông qua hệ thống phân loại (Triage),{' '}
              <strong>A.I.M Care</strong> đánh giá mức độ khẩn cấp của triệu chứng và đưa ra
              phản hồi tức thì chỉ trong vài giây.
            </p>
          </div>

          {/* Card I */}
          <div className="pillar-card pillar-purple">
            <div className="pillar-letter">I</div>
            <h3>Integrated — Tích hợp &amp; Hiệp đồng</h3>
            <p>
              Sự kết hợp sức mạnh. Hệ thống tích hợp liền mạch cơ sở dữ liệu Vector (RAG) và
              mạng lưới các Tác nhân AI (Multi-Agent). Các AI này liên tục giao tiếp, phản biện
              và kiểm chứng chéo để loại bỏ "ảo giác" (hallucination).
            </p>
          </div>

          {/* Card M */}
          <div className="pillar-card pillar-teal">
            <div className="pillar-letter">M</div>
            <h3>Medical — Chuẩn Y khoa</h3>
            <p>
              An toàn là ưu tiên tối thượng. Mọi luồng suy luận, nguồn tài liệu và ngữ cảnh
              đều được giới hạn và neo chặt vào các tiêu chuẩn y khoa đáng tin cậy.
            </p>
          </div>
        </div>
      </section>

      {/* ========== 4. Callout Banner ========== */}
      <section className="about-callout">
        <h2>Công nghệ phức tạp. Trải nghiệm đơn giản.</h2>
        <p>
          Máy móc và thuật toán chịu trách nhiệm xử lý hàng triệu điểm dữ liệu kỹ thuật ở
          hậu cảnh (<strong>A.I.M</strong>). Thứ duy nhất bạn nhận được ở giao diện chính là sự
          chăm sóc tận tâm, an toàn và dễ hiểu (<strong>Care</strong>).
        </p>
      </section>

      {/* ========== 5. Footer ========== */}
      <footer className="about-footer">
        <p className="about-footer-disclaimer">
          Lưu ý quan trọng: A.I.M Care là một hệ thống cung cấp thông tin tham khảo hữu ích dựa
          trên AI. Hệ thống không nhằm mục đích thay thế cho các chẩn đoán, điều trị hay chỉ
          định từ bác sĩ chuyên môn.
        </p>
        <p className="about-footer-copy">© 2026 A.I.M Care.</p>
        <p className="about-footer-contact">Liên hệ: aimcare.chat@gmail.com</p>
      </footer>
    </div>
  );
};

export default About;
