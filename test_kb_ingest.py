import pandas as pd

# ==========================================
# 1. Table 1: Main Results (主实验结果)
# ==========================================
data_main = [
    ["Method", "Backbone", "Retrieval R@5", "Retrieval MRR", "Gen BLEU-4", "Gen ROUGE-L", "Cit. Prec.", "Faith. Score", "Latency (ms)", "Mem (GB)"],
    ["Text-Only Baselines", "", "", "", "", "", "", "", "", ""],
    ["DPR + FiD", "T5-Large", 45.2, 51.3, 28.4, 33.1, "62.1%", 3.2, 120, 14.2],
    ["Multimodal RAG", "", "", "", "", "", "", "", "", ""],
    ["ViLBERT-RAG", "BERT-Large", 68.5, 72.1, 35.6, 41.2, "74.5%", 3.8, 450, 28.5],
    ["CLIP-BART", "BART-Large", 65.8, 70.4, 34.2, 40.5, "71.2%", 3.6, 410, 24.1],
    ["Non-RAG LMMs", "", "", "", "", "", "", "", "", ""],
    ["LLaVA-1.5 (13B)", "LLaMA-2", "-", "-", 38.9, 44.5, "-", 2.1, 85, 26.0],
    ["GPT-4V (Zero-shot)", "Proprietary", "-", "-", 44.2, 48.1, "-", 2.9, "-", "-"],
    ["Ours", "", "", "", "", "", "", "", "", ""],
    ["DDR (Ours)", "Mamba-2.8B", 74.2, 78.5, 43.8, 47.5, "89.4%", 4.6, 145, 8.4]
]

df_main = pd.DataFrame(data_main[1:], columns=data_main[0])

# ==========================================
# 2. Table 2: Ablation Studies (消融实验)
# ==========================================
data_ablation = [
    ["Model Variant", "Module Removed", "Acc. (%)", "Delta", "Faith. Score"],
    ["Full Model (DDR)", "None", 68.4, "-", 4.62],
    ["(A1) w/o MM-Retriever", "Visual Evidence", 42.1, "-26.3", 2.10],
    ["(A2) w/o EvidenceNorm", "Denoising", 61.5, "-6.9", 3.85],
    ["(A3) w/o AttentionAlign", "Alignment", 63.2, "-5.2", 3.15],
    ["(A4) Replace w/ Transformer", "Mamba Backbone", 68.1, "-0.3", 4.58],
    ["(A5) SFT Only (No DPO)", "DDR Objective", 65.8, "-2.6", 3.40],
    ["(A6) PPO Training", "DPO Optimization", 66.2, "-2.2", 4.10]
]

df_ablation = pd.DataFrame(data_ablation[1:], columns=data_ablation[0])

# ==========================================
# 3. Table 3: Statistics (数据与效率)
# ==========================================
data_stats = [
    ["Dataset", "Type", "Size (QAs)", "Avg. Tokens", "Note"],
    ["DocVQA", "Real", "12,767", 180, ""],
    ["ChartQA", "Real", "9,608", 350, ""],
    ["InfographicVQA", "Real", "5,485", 1200, ""],
    ["Synthetic-Long", "Synth", "10,000", 16384, "Robustness Test"],
    ["Efficiency Test (32k ctx)", "", "", "", ""],
    ["Transformer (FlashAttn-2)", "-", "-", "-", "OOM (>80GB)"],
    ["DDR-Mamba (Ours)", "-", "-", "-", "12.4 GB / 85 ms"]
]

df_stats = pd.DataFrame(data_stats[1:], columns=data_stats[0])

# ==========================================
# Save to Excel
# ==========================================
with pd.ExcelWriter('experiment_results.xlsx') as writer:
    df_main.to_excel(writer, sheet_name='Table1_Main_Results', index=False)
    df_ablation.to_excel(writer, sheet_name='Table2_Ablations', index=False)
    df_stats.to_excel(writer, sheet_name='Table3_Stats', index=False)

print("✅ Excel file 'experiment_results.xlsx' has been generated successfully!")