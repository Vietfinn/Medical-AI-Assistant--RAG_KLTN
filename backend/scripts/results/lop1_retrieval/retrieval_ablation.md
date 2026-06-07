# Retrieval Ablation Study

> Đánh giá trên **2012** mẫu từ `test_clean.csv` (Đã bổ sung đầy đủ kết quả thành công)
> Collection: `vnhealthqa` (bkai-foundation-models/vietnamese-bi-encoder)
> Ngày chạy: 2026-06-05 00:11

| Cấu hình | P@1 (%) | P@5 (%) | P@10 (%) | mAP (%) |
|:---|:---:|:---:|:---:|:---:|
| BM25 (SPBERTQA Baseline) | 44.96 | — | 70.09 | 56.93 |
| SPBERTQA (Best Baseline) | 50.92 | — | 83.76 | 62.25 |
| **Dense Only (vi-bi-encoder)** | **91.05** | **95.13** | **96.57** | **92.88** |
| **Hybrid RRF (Dense + BM25)** | **95.83** | **99.60** | **99.85** | **97.62** |
| **Hybrid RRF + Cohere Reranker** | **97.47** | **99.75** | **99.85** | **98.51** |
