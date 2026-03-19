import React, { useState } from 'react';
import { ChevronDown, ChevronUp, FileText } from 'lucide-react';
import './Citation.css';

const Citation = ({ citation, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="citation">
      <div className="citation-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="citation-title">
          <FileText size={16} />
          <span>
            [{index}] {citation.doc_id}
          </span>
          <span className="citation-score">
            ({(citation.score * 100).toFixed(1)}% phù hợp)
          </span>
        </div>
        <button className="citation-toggle">
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      
      {isExpanded && (
        <div className="citation-content fade-in">
          <div className="citation-section">
            <strong>Câu hỏi gốc:</strong>
            <p>{citation.question}</p>
          </div>
          <div className="citation-section">
            <strong>Câu trả lời từ bác sĩ:</strong>
            <p>{citation.answer}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Citation;
