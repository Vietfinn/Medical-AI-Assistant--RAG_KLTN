import React, { useState } from 'react';
import { Check } from 'lucide-react';
import './FeedbackModal.css';

const TAGS = [
  { id: 'wrong_medical_info', label: 'Sai kiến thức y khoa hoặc có nguy cơ gây hại.' },
  { id: 'off_topic', label: 'Nội dung lạc đề, không giải quyết đúng trọng tâm.' },
  { id: 'irrelevant_source', label: 'Nguồn tài liệu tham khảo không khớp với câu trả lời.' },
  { id: 'too_technical', label: 'Dùng quá nhiều từ chuyên môn y tế gây khó hiểu.' },
  { id: 'ignored_allergy', label: 'Bỏ qua thông tin tiền sử bệnh và dị ứng đã khai báo.' },
  { id: 'cold_tone', label: 'Văn phong rập khuôn, thiếu sự thấu cảm với người bệnh.' },
];

const FeedbackModal = ({ onClose, onSubmit }) => {
  const [selectedTags, setSelectedTags] = useState([]);
  const [otherText, setOtherText] = useState('');
  const [otherSelected, setOtherSelected] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const toggleTag = (tagId) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId]
    );
  };

  const toggleOther = () => {
    setOtherSelected((prev) => !prev);
    if (otherSelected) setOtherText('');
  };

  const handleSubmit = async () => {
    const finalTags = [...selectedTags];
    if (otherSelected && otherText.trim()) {
      finalTags.push('other');
    }
    setIsSubmitting(true);
    await onSubmit({ reason_tags: finalTags, text_feedback: otherText.trim() });
    setIsSubmitting(false);
  };

  const hasSelection = selectedTags.length > 0 || (otherSelected && otherText.trim());

  return (
    <div className="fb-overlay" onClick={onClose}>
      <div className="fb-modal" onClick={(e) => e.stopPropagation()}>
        <div className="fb-header">
          <div>
            <h3 className="fb-title">Đánh giá chất lượng phản hồi</h3>
            <p className="fb-subtitle">Hệ thống ghi nhận phản hồi chưa tốt. Vui lòng cho chúng tôi biết vấn đề bạn gặp phải:</p>
          </div>
        </div>

        <div className="fb-tag-list">
          {TAGS.map((tag) => {
            const isActive = selectedTags.includes(tag.id);
            return (
              <button
                key={tag.id}
                className={`fb-tag-row ${isActive ? 'active' : ''}`}
                onClick={() => toggleTag(tag.id)}
              >
                <span className="fb-tag-checkbox">
                  {isActive && <Check size={12} strokeWidth={3} />}
                </span>
                <span className="fb-tag-label">{tag.label}</span>
              </button>
            );
          })}



          <button
            className={`fb-tag-row fb-other-row ${otherSelected ? 'active' : ''}`}
            onClick={toggleOther}
          >
            <span className="fb-tag-checkbox">
              {otherSelected && <Check size={12} strokeWidth={3} />}
            </span>
            <span className="fb-tag-label">Phát sinh vấn đề khác</span>
          </button>

          {otherSelected && (
            <div className="fb-other-input-wrap fade-in">
              <textarea
                className="fb-other-textarea"
                placeholder="Vui lòng mô tả chi tiết vấn đề để giúp A.I.M Care hoàn thiện hơn..."
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                rows={3}
                maxLength={500}
                autoFocus
              />
            </div>
          )}
        </div>

        <div className="fb-footer fade-in">
          <button
            className="fb-cancel-btn"
            onClick={onClose}
          >
            Hủy
          </button>
          <button
            className="fb-submit-btn"
            onClick={handleSubmit}
            disabled={isSubmitting || !hasSelection}
          >
            {isSubmitting ? 'Đang gửi...' : 'Gửi đánh giá'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FeedbackModal;
