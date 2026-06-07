import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path

# Cấu hình đường dẫn
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Thiết lập phong cách vẽ biểu đồ sang trọng và chuyên nghiệp
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 14,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 16,
    "figure.dpi": 300,
})

# Bảng màu hiện đại nhã nhặn (和谐/和谐/Harmonious Palette)
COLORS_METRIC = ["#3A86C8", "#83B2FF", "#5FAD56", "#E9A15A"]
COLORS_PRIMARY = "#2C3E50"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F1C40F"
COLOR_DANGER = "#E74C3C"

def generate_lop1_plots():
    """Vẽ biểu đồ so sánh các phương pháp trích xuất (Lớp 1)"""
    print("Drawing Layer 1 plots...")
    methods = [
        "Vector Search\n(BKAI Bi-Encoder)",
        "BM25\n(Lexical)",
        "Hybrid Search\n(Vector + BM25)",
        "Hybrid + Cohere Rerank\n(Đề xuất)"
    ]
    
    metrics = {
        "MRR@5": [0.8122, 0.6974, 0.8443, 0.8654],
        "Recall@5": [0.8122, 0.6974, 0.8443, 0.8654],
        "Hit Rate@5": [0.8122, 0.6974, 0.8443, 0.8654],
        "MAP@5": [0.8122, 0.6974, 0.8443, 0.8654]
    }
    
    # Ở đây do các giá trị của mỗi metric trùng nhau (đặc thù của tập test đơn đáp án), 
    # ta sẽ biểu diễn dưới dạng biểu đồ cột đơn giản so sánh MRR@5 và Recall@5 của các phương pháp.
    df = pd.DataFrame({
        "Phương pháp": methods,
        "Độ chính xác (MRR / Recall @5)": metrics["MRR@5"]
    })
    
    plt.figure(figsize=(9, 5.5))
    ax = sns.barplot(
        x="Độ chính xác (MRR / Recall @5)",
        y="Phương pháp",
        data=df,
        palette="Blues_r",
        hue="Phương pháp",
        legend=False
    )
    
    # Thêm số liệu lên đầu cột
    for p in ax.patches:
        width = p.get_width()
        ax.text(
            width + 0.01,
            p.get_y() + p.get_height() / 2,
            f"{width:.4f}",
            ha="left",
            va="center",
            fontweight="bold",
            color="#2C3E50"
        )
        
    plt.xlim(0, 1.0)
    plt.title("So Sánh Hiệu Năng Các Phương Pháp Truy Xuất Tài Liệu (Layer 1)", pad=15, fontweight="bold")
    plt.xlabel("Điểm số (Tỷ lệ %)")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "lop1_retrieval_comparison.png", dpi=300)
    plt.close()


def generate_lop2_plots():
    """Vẽ biểu đồ cột điểm số RAG Triad (Lớp 2)"""
    print("Drawing Layer 2 plots...")
    criteria = [
        "Faithfulness\n(Tính trung thực y khoa)",
        "Answer Relevance\n(Trả lời đúng trọng tâm)",
        "Context Relevance\n(Tài liệu khớp câu hỏi)"
    ]
    scores = [4.74, 4.62, 4.81]
    
    df = pd.DataFrame({
        "Tiêu chí đánh giá": criteria,
        "Điểm trung bình (Thang 1-5)": scores
    })
    
    plt.figure(figsize=(8, 5.5))
    ax = sns.barplot(
        x="Tiêu chí đánh giá",
        y="Điểm trung bình (Thang 1-5)",
        data=df,
        palette="viridis",
        hue="Tiêu chí đánh giá",
        legend=False
    )
    
    # Thêm số liệu lên cột
    for p in ax.patches:
        height = p.get_height()
        ax.text(
            p.get_x() + p.get_width() / 2.,
            height - 0.4,
            f"{height:.2f} / 5.0",
            ha="center",
            va="bottom",
            fontweight="bold",
            color="white",
            fontsize=12
        )
        
    plt.ylim(0, 5.5)
    plt.title("Điểm Số Đánh Giá RAG Triad Bằng LLM-as-a-Judge (Layer 2)", pad=15, fontweight="bold")
    plt.xlabel("")
    plt.ylabel("Điểm trung bình (Thang điểm 1 - 5)")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "lop2_rag_triad.png", dpi=300)
    plt.close()


def generate_lop3_plots():
    """Vẽ các biểu đồ Confusion Matrix và tỷ lệ các nhóm an toàn (Lớp 3)"""
    print("Drawing Layer 3 plots...")
    
    # ── 1. Triage Confusion Matrix ───────────────────────────────────────────
    triage_labels = ["MEDICAL", "NON_MEDICAL", "UNSAFE"]
    triage_matrix = np.array([
        [20, 0, 0],
        [0, 15, 0],
        [0, 0, 15]
    ])
    
    plt.figure(figsize=(7, 5.5))
    sns.heatmap(
        triage_matrix,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=triage_labels,
        yticklabels=triage_labels,
        annot_kws={"size": 14, "weight": "bold"},
        cbar=True
    )
    plt.title("Ma Trận Nhầm Lẫn (Confusion Matrix) - Triage Agent đầu vào", pad=15, fontweight="bold")
    plt.xlabel("Nhãn Dự Đoán", labelpad=10)
    plt.ylabel("Nhãn Thực Tế", labelpad=10)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "lop3_triage_confusion_matrix.png", dpi=300)
    plt.close()

    # ── 2. Safety Guard Confusion Matrix ─────────────────────────────────────
    safety_labels = ["CÓ CẢNH BÁO\n(Rủi ro)", "KHÔNG CẢNH BÁO\n(An toàn)"]
    # 35 TP, 5 FN (Bỏ sót), 0 FP (Cảnh báo nhầm), 10 TN (Chứng âm đúng)
    safety_matrix = np.array([
        [35, 5],
        [0, 10]
    ])
    
    plt.figure(figsize=(7, 5.5))
    sns.heatmap(
        safety_matrix,
        annot=True,
        fmt="d",
        cmap="Reds",
        xticklabels=safety_labels,
        yticklabels=safety_labels,
        annot_kws={"size": 14, "weight": "bold"},
        cbar=True
    )
    plt.title("Ma Trận Nhầm Lẫn (Confusion Matrix) - Safety Guard đầu ra", pad=15, fontweight="bold")
    plt.xlabel("Nhãn Dự Đoán", labelpad=10)
    plt.ylabel("Nhãn Thực Tế", labelpad=10)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "lop3_safety_confusion_matrix.png", dpi=300)
    plt.close()

    # ── 3. Tỷ lệ chính xác của các nhóm rủi ro y khoa ───────────────────────
    categories = [
        "Dị ứng thuốc\n(Drug Allergy)",
        "Chống chỉ định\n(Contraindication)",
        "Tương tác thuốc\n(Drug-Drug)",
        "Đa yếu tố\n(Multi-factor)",
        "Chứng âm\n(Negative Control)"
    ]
    accuracy_rates = [1.00, 0.80, 0.80, 0.80, 1.00]
    
    df_cat = pd.DataFrame({
        "Danh mục rủi ro": categories,
        "Tỷ lệ chính xác (%)": [r * 100 for r in accuracy_rates]
    })
    
    plt.figure(figsize=(9, 5.5))
    ax = sns.barplot(
        x="Tỷ lệ chính xác (%)",
        y="Danh mục rủi ro",
        data=df_cat,
        palette="coolwarm",
        hue="Danh mục rủi ro",
        legend=False
    )
    
    # Thêm số liệu lên đầu cột
    for p in ax.patches:
        width = p.get_width()
        ax.text(
            width + 1.5,
            p.get_y() + p.get_height() / 2,
            f"{width:.1f}%",
            ha="left",
            va="center",
            fontweight="bold",
            color="#2C3E50"
        )
        
    plt.xlim(0, 115)
    plt.title("Hiệu Năng Nhận Diện Rủi Ro Theo Danh Mục (Layer 3 Safety)", pad=15, fontweight="bold")
    plt.xlabel("Tỷ lệ chính xác (%)")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "lop3_safety_categories.png", dpi=300)
    plt.close()


def generate_latency_plot():
    """Vẽ biểu đồ so sánh độ trễ của các thành phần trong hệ thống"""
    print("Drawing Latency plots...")
    components = [
        "Triage Agent\n(Đầu vào)",
        "Truy xuất tài liệu\n(Retrieval + Rerank)",
        "Sinh câu trả lời\n(Clinical Agent)",
        "Safety Guard Agent\n(Đầu ra)"
    ]
    latencies = [4.033, 1.079, 1.364, 2.660]  # s
    
    df = pd.DataFrame({
        "Thành phần xử lý": components,
        "Độ trễ trung bình (giây)": latencies
    })
    
    plt.figure(figsize=(8.5, 5.5))
    # Sử dụng bảng màu ấm cho dễ theo dõi
    ax = sns.barplot(
        x="Thành phần xử lý",
        y="Độ trễ trung bình (giây)",
        data=df,
        palette="autumn",
        hue="Thành phần xử lý",
        legend=False
    )
    
    # Thêm số liệu lên cột
    for p in ax.patches:
        height = p.get_height()
        ax.text(
            p.get_x() + p.get_width() / 2.,
            height + 0.1,
            f"{height:.3f}s",
            ha="center",
            va="bottom",
            fontweight="bold",
            color="#2C3E50"
        )
        
    # Tính tổng độ trễ vận hành chính (Retrieval + Gen)
    prod_latency = latencies[1] + latencies[2]
    # Tổng độ trễ toàn trình (Triage + Retrieval + Gen + Safety)
    total_latency = sum(latencies)
    
    plt.ylim(0, 5.0)
    plt.title("Phân Tích Độ Trễ Trung Bình Của Các Thành Phần Hệ Thống (AIMCare)", pad=15, fontweight="bold")
    plt.xlabel("")
    plt.ylabel("Thời gian phản hồi (giây)")
    
    # Thêm text chú thích tổng quan
    note_text = f"Độ trễ Core RAG (Retrieval + Gen): {prod_latency:.3f}s\nTổng độ trễ an toàn đa tầng: {total_latency:.3f}s"
    plt.gcf().text(0.55, 0.75, note_text, fontsize=10, bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))
    
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "system_latency_comparison.png", dpi=300)
    plt.close()


def main():
    print("=== START GENERATING PLOTS ===")
    try:
        generate_lop1_plots()
        generate_lop2_plots()
        generate_lop3_plots()
        generate_latency_plot()
        print(f"\nSuccess! Plots saved at: {PLOTS_DIR}")
    except Exception as e:
        print(f"Error drawing plots: {str(e)}")

if __name__ == "__main__":
    main()
