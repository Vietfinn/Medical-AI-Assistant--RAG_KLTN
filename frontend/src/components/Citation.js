import React, { useState, useEffect } from 'react';
import { Info } from 'lucide-react';
import './Citation.css';

const Citation = ({ citations, initialActiveIndex }) => {
  const [activeIndex, setActiveIndex] = useState(0);

  // Sync activeIndex with initialActiveIndex when requested, or reset on citations change
  useEffect(() => {
    if (
      typeof initialActiveIndex === 'number' &&
      initialActiveIndex >= 0 &&
      initialActiveIndex < citations.length
    ) {
      setActiveIndex(initialActiveIndex);
    } else {
      setActiveIndex(0);
    }
  }, [citations, initialActiveIndex]);

  if (!citations || citations.length === 0) {
    return <p className="source-panel-empty">Không có nguồn tham khảo cho tin nhắn này.</p>;
  }

  const activeCitation = citations[activeIndex];

  return (
    <div className="citations-container">
      {/* Hàng các ô nguồn dạng flex-wrap (ảnh 2) */}
      <div className="citations-tabs">
        {citations.map((cit, cIndex) => {
          const scorePct = cit.score ? Math.round(cit.score * 100) : 100;
          const docLabel = cit.doc_id || `Nguồn ${cIndex + 1}`;
          const isActive = cIndex === activeIndex;

          return (
            <button
              key={cIndex}
              type="button"
              className={`citation-tab-chip ${isActive ? 'active' : ''}`}
              onClick={() => setActiveIndex(cIndex)}
            >
              <span>{docLabel}</span> <span className="citation-score-pct">({scorePct}%)</span>
            </button>
          );
        })}
      </div>

      {/* Khung form thông tin chi tiết với thiết kế thông báo nổi */}
      {activeCitation && (
        <div className="citation-detail-form fade-in">
          <div className="citation-detail-header">
            <Info size={16} className="citation-info-icon" />
            <span>Chi tiết nguồn trích xuất</span>
          </div>
          <div className="citation-detail-section">
            <span className="citation-detail-label">Câu hỏi:</span>
            <span className="citation-detail-text"> {activeCitation.question}</span>
          </div>
          <div className="citation-detail-section">
            <span className="citation-detail-label">Trích xuất:</span>
            <span className="citation-detail-text"> {activeCitation.answer}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default Citation;
