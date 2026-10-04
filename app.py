"""PARAKH (परख) - Food Safety & Nutrition Intelligence.

A professional, age-inclusive packaged-food label explainer for Indian shoppers.
Engineered with high performance (<30s), robust Gradio events, and strict honesty rules.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Generator
from PIL import Image
import gradio as gr

# Strict CSP Workaround for Cloud Hosts (e.g. Embarko edge proxy)
# Gradio 5/6 evaluates gr.HTML using client-side Handlebars Function(...) which violates
# strict script-src CSP rules without 'unsafe-eval'.
# Using gr.Markdown(sanitize_html=False) renders identical full HTML safely.
_orig_html = gr.HTML

def _clean_str(val: Any) -> Any:
    if isinstance(val, str):
        lines = [line.strip() for line in val.splitlines() if line.strip()]
        return "\n".join(lines)
    return val

def _safe_html_component(*args, **kwargs):
    kwargs.pop("show_label", None)
    kwargs["sanitize_html"] = False
    if "value" in kwargs:
        kwargs["value"] = _clean_str(kwargs["value"])
    elif args and isinstance(args[0], str):
        args = (_clean_str(args[0]),) + args[1:]
    return gr.Markdown(*args, **kwargs)

gr.HTML = _safe_html_component

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings
from llm import health
from pipeline.models import AnalysisResult
from pipeline.render import (
    DISCLAIMER_H10,
    clean_html,
    render_ingredients_html,
    render_nutrition_html,
    render_qa_html,
    render_report,
    render_summary_html,
    render_transcription_html,
)
from pipeline.run import ProgressUpdate, analyze

logger = logging.getLogger("label_reader.app")

# ---------------------------------------------------------------------------
# Design System CSS — Clean, High-Contrast Light Theme
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&family=DM+Mono:wght@400;500&display=swap');

/* ═══════════════════════════════════════════
   GLOBAL RESETS & THEME ENFORCEMENT
═══════════════════════════════════════════ */
:root, html, body, .gradio-container, .dark, html.dark, body.dark {
    color-scheme: light !important;
    --font: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    --mono: 'DM Mono', monospace !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: #F8FAFC !important;
    background-color: #F8FAFC !important;
    color: #0F172A !important;
}

*, *::before, *::after { box-sizing: border-box; }

footer, .built-with { display: none !important; }

/* Transparent prose container for safe HTML rendering */
.prose, .prose.gradio-style { max-width: none !important; }
.gradio-container .prose p:empty { display: none !important; }

/* ═══ GRADIO BLOCK OVERRIDES (ELIMINATE DARK MODE LEAKS) ═══ */
.gradio-container .block,
.gradio-container .form,
.gradio-container fieldset,
.gradio-container .wrap,
.gradio-container .gr-panel,
.gradio-container .gr-box {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border-color: #E2E8F0 !important;
    color: #0F172A !important;
}

.gradio-container label, .gradio-container .block label {
    background: transparent !important;
    color: #334155 !important;
    font-size: 13px !important;
    font-weight: 700 !important;
}

.gradio-container input[type="text"],
.gradio-container input[type="password"],
.gradio-container textarea {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 10px !important;
    font-size: 14.5px !important;
    font-weight: 500 !important;
    padding: 10px 14px !important;
}

.gradio-container input[type="text"]:focus,
.gradio-container textarea:focus {
    border-color: #10B981 !important;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15) !important;
    outline: none !important;
}

/* ═══ WRAPPER & CONTAINER ═══ */
.p-wrap {
    max-width: 1060px !important;
    margin: 0 auto !important;
    padding: 0 16px 64px !important;
}

/* ═══ TOP NAVIGATION ═══ */
.top-bar {
    background: #FFFFFF !important;
    border-bottom: 1.5px solid #E2E8F0 !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 100 !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.03) !important;
}
.top-bar-inner {
    max-width: 1060px !important;
    margin: 0 auto !important;
    padding: 14px 20px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
}
.top-logo {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
}
.top-logo-icon {
    width: 38px !important; height: 38px !important;
    background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
    border-radius: 10px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 20px !important;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25) !important;
}
.top-logo-text {
    font-size: 19px !important;
    font-weight: 900 !important;
    color: #0F172A !important;
    letter-spacing: -0.4px !important;
    display: block !important;
    line-height: 1.2 !important;
}
.top-logo-sub {
    font-size: 11px !important;
    font-weight: 700 !important;
    color: #10B981 !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
}
.top-badge {
    background: #ECFDF5 !important;
    border: 1px solid #A7F3D0 !important;
    border-radius: 999px !important;
    padding: 6px 14px !important;
    font-size: 12.5px !important;
    font-weight: 700 !important;
    color: #065F46 !important;
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
}

/* ═══ HERO SECTION ═══ */
.hero-card {
    background: linear-gradient(135deg, #064E3B 0%, #065F46 50%, #047857 100%) !important;
    border-radius: 20px !important;
    padding: 40px 44px !important;
    margin: 20px 0 24px !important;
    color: #FFFFFF !important;
    position: relative !important;
    overflow: hidden !important;
    box-shadow: 0 10px 30px -5px rgba(6, 78, 59, 0.25) !important;
}
.hero-card::after {
    content: '' !important;
    position: absolute !important;
    top: -50px; right: -50px;
    width: 250px; height: 250px;
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%) !important;
    border-radius: 50% !important;
    pointer-events: none !important;
}
.hero-tag {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    background: rgba(255,255,255,0.15) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 999px !important;
    padding: 5px 14px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    margin-bottom: 14px !important;
}
.hero-title {
    font-size: 34px !important;
    font-weight: 900 !important;
    color: #FFFFFF !important;
    letter-spacing: -0.8px !important;
    line-height: 1.2 !important;
    margin-bottom: 10px !important;
}
.hero-title span { color: #6EE7B7 !important; }
.hero-desc {
    font-size: 15.5px !important;
    color: #D1FAE5 !important;
    line-height: 1.6 !important;
    max-width: 620px !important;
    margin-bottom: 24px !important;
}
.hero-stats {
    display: flex !important;
    gap: 32px !important;
    flex-wrap: wrap !important;
}
.hero-stat-val {
    font-size: 24px !important;
    font-weight: 900 !important;
    color: #6EE7B7 !important;
    line-height: 1 !important;
}
.hero-stat-lbl {
    font-size: 12px !important;
    color: #A7F3D0 !important;
    font-weight: 600 !important;
    margin-top: 4px !important;
}

/* ═══ CARDS ═══ */
.app-card {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 16px !important;
    padding: 22px 26px !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.03) !important;
    margin-bottom: 16px !important;
}
.card-head {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-bottom: 14px !important;
}
.card-icon {
    width: 34px !important; height: 34px !important;
    background: #ECFDF5 !important;
    border-radius: 8px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 17px !important;
}
.card-title {
    font-size: 16px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
}
.card-sub {
    font-size: 12.5px !important;
    color: #64748B !important;
    font-weight: 500 !important;
}

/* ═══ QUICK QUESTION CHIPS ═══ */
.q-chip, .q-chip button, button.q-chip, div.q-chip > button {
    background: #F0FDF4 !important;
    background-color: #F0FDF4 !important;
    color: #166534 !important;
    border: 1.5px solid #BBF7D0 !important;
    border-radius: 9999px !important;
    font-weight: 700 !important;
    font-size: 12.5px !important;
    padding: 7px 14px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    white-space: nowrap !important;
}
.q-chip:hover, .q-chip button:hover, button.q-chip:hover, div.q-chip > button:hover {
    background: #DCFCE7 !important;
    background-color: #DCFCE7 !important;
    color: #14532D !important;
    border-color: #86EFAC !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 8px rgba(22, 101, 52, 0.12) !important;
}

/* ═══ LANGUAGE SELECTOR ═══ */
.lang-radio, .lang-radio .wrap {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    display: flex !important;
    gap: 8px !important;
    padding: 0 !important;
}
.lang-radio label {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    color: #334155 !important;
    border-radius: 9999px !important;
    padding: 7px 16px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
.lang-radio label.selected, .lang-radio label:has(input:checked) {
    background: #ECFDF5 !important;
    background-color: #ECFDF5 !important;
    border-color: #10B981 !important;
    color: #065F46 !important;
    box-shadow: 0 1px 4px rgba(16, 185, 129, 0.2) !important;
}

/* ═══ BUTTONS ═══ */
.btn-primary button, button.btn-primary {
    background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
    color: #FFFFFF !important;
    font-size: 16px !important;
    font-weight: 800 !important;
    padding: 14px 28px !important;
    border-radius: 12px !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35) !important;
    cursor: pointer !important;
    letter-spacing: -0.2px !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
}
.btn-primary button:hover, button.btn-primary:hover {
    background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.45) !important;
    transform: translateY(-2px) !important;
}
.btn-primary button:active, button.btn-primary:active {
    transform: scale(0.98) !important;
}
.btn-secondary button, button.btn-secondary {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #475569 !important;
    font-size: 14.5px !important;
    font-weight: 700 !important;
    padding: 14px 22px !important;
    border-radius: 12px !important;
    border: 1.5px solid #CBD5E1 !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
.btn-secondary button:hover, button.btn-secondary:hover {
    background: #F8FAFC !important;
    color: #0F172A !important;
    border-color: #94A3B8 !important;
}

/* ═══ IMAGE CANCEL / REMOVE BUTTONS ═══ */
.btn-remove-img, .btn-remove-img button, button.btn-remove-img {
    background: #FFF1F2 !important;
    background-color: #FFF1F2 !important;
    color: #E11D48 !important;
    border: 1.5px solid #FECDD3 !important;
    border-radius: 8px !important;
    font-size: 12.5px !important;
    font-weight: 700 !important;
    padding: 7px 16px !important;
    margin-top: 8px !important;
    cursor: pointer !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    transition: all 0.15s ease !important;
    width: auto !important;
}
.btn-remove-img:hover, .btn-remove-img button:hover, button.btn-remove-img:hover {
    background: #FFE4E6 !important;
    background-color: #FFE4E6 !important;
    color: #BE123C !important;
    border-color: #FDA4AF !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 6px rgba(225, 29, 72, 0.12) !important;
}

/* Make Gradio built-in image toolbar buttons prominent & visible */
.gradio-image button[aria-label="Clear"],
.gradio-image button[aria-label="Remove image"],
.gradio-image .clear-button,
.gradio-image .toolbar button {
    background: #FFFFFF !important;
    color: #E11D48 !important;
    border: 1.5px solid #FECDD3 !important;
    border-radius: 8px !important;
    opacity: 1 !important;
    visibility: visible !important;
    padding: 6px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
    cursor: pointer !important;
}
.gradio-image button[aria-label="Clear"]:hover,
.gradio-image button[aria-label="Remove image"]:hover,
.gradio-image .clear-button:hover,
.gradio-image .toolbar button:hover {
    background: #FFE4E6 !important;
    border-color: #E11D48 !important;
}

/* ═══ COMPACT IMAGE PREVIEWS (STRICT HEIGHT CONSTRAINTS) ═══ */
.compact-img-input,
.compact-img-input > div,
.compact-img-input .wrap,
.compact-img-input .image-frame,
.compact-img-input .image-container,
.compact-img-input .upload-container,
.compact-img-input [data-testid="image"],
.compact-img-input .image-preview,
div[data-testid="image"],
.gradio-image,
.gradio-image .image-frame,
.gradio-image .image-container,
.gradio-image .upload-container,
.gradio-image .wrap,
.gradio-image .image-preview {
    max-height: 200px !important;
    min-height: unset !important;
    height: auto !important;
}

.compact-img-input img,
div[data-testid="image"] img,
.gradio-image img,
.image-preview img,
.image-container img {
    max-height: 175px !important;
    max-width: 100% !important;
    width: auto !important;
    height: auto !important;
    margin: 0 auto !important;
    object-fit: contain !important;
    border-radius: 8px !important;
    display: block !important;
}

.image-drop {
    min-height: unset !important;
    max-height: 190px !important;
}

/* ═══ IMAGE BADGES & UPLOAD STATUS ═══ */
.img-control-row {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 12px !important;
    margin-top: 8px !important;
    flex-wrap: wrap !important;
}

.img-badge-pending {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    background: #F8FAFC !important;
    color: #64748B !important;
    border: 1px dashed #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 6px 12px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}

.img-badge-success {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    background: #ECFDF5 !important;
    color: #065F46 !important;
    border: 1.5px solid #10B981 !important;
    border-radius: 8px !important;
    padding: 6px 14px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    box-shadow: 0 1px 3px rgba(16, 185, 129, 0.15) !important;
    animation: fadeInBadge 0.25s ease !important;
}

@keyframes fadeInBadge {
    from { opacity: 0; transform: translateY(3px); }
    to { opacity: 1; transform: translateY(0); }
}

.upload-summary-bar {
    background: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 12px 18px !important;
    margin-bottom: 14px !important;
    font-size: 13.5px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    transition: all 0.2s ease !important;
}

.upload-summary-bar.has-photos {
    background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 100%) !important;
    border-color: #10B981 !important;
    color: #065F46 !important;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.12) !important;
}

.upload-summary-pill {
    padding: 4px 12px !important;
    border-radius: 999px !important;
    font-size: 11.5px !important;
    font-weight: 800 !important;
    letter-spacing: 0.3px !important;
    text-transform: uppercase !important;
}

.upload-summary-pill.pending {
    background: #F1F5F9 !important;
    color: #64748B !important;
    border: 1px solid #CBD5E1 !important;
}

.upload-summary-pill.ready {
    background: #10B981 !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 4px rgba(16, 185, 129, 0.3) !important;
}

/* ═══ TABS ═══ */
[role="tablist"] {
    background: #F1F5F9 !important;
    background-color: #F1F5F9 !important;
    border-bottom: 1.5px solid #E2E8F0 !important;
    padding: 6px 8px !important;
    border-radius: 14px 14px 0 0 !important;
    display: flex !important;
    gap: 6px !important;
}
[role="tab"] {
    background: transparent !important;
    color: #64748B !important;
    font-size: 13.5px !important;
    font-weight: 700 !important;
    padding: 9px 18px !important;
    border-radius: 10px !important;
    border: none !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
[role="tab"][aria-selected="true"] {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}
[role="tab"]:hover:not([aria-selected="true"]) {
    color: #0F172A !important;
    background: rgba(255,255,255,0.6) !important;
}

/* ═══ STATUS INDICATORS ═══ */
.status-loading {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    background: #EFF6FF !important;
    border: 1.5px solid #BFDBFE !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    color: #1E40AF !important;
    font-size: 14.5px !important;
    font-weight: 700 !important;
    margin-bottom: 6px !important;
}
.status-ok {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    background: #ECFDF5 !important;
    border: 1.5px solid #A7F3D0 !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    color: #065F46 !important;
    font-size: 14.5px !important;
    font-weight: 700 !important;
    margin-bottom: 6px !important;
}
.status-warn {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    background: #FFFBEB !important;
    border: 1.5px solid #FCD34D !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    color: #92400E !important;
    font-size: 14.5px !important;
    font-weight: 700 !important;
    margin-bottom: 6px !important;
}
.status-error {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    background: #FEF2F2 !important;
    border: 1.5px solid #FCA5A5 !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    color: #991B1B !important;
    font-size: 14.5px !important;
    font-weight: 700 !important;
    margin-bottom: 6px !important;
}

.spinner {
    width: 20px !important; height: 20px !important;
    border: 3px solid rgba(37,99,235,0.2) !important;
    border-top-color: #2563EB !important;
    border-radius: 50% !important;
    animation: spin 0.8s linear infinite !important;
    flex-shrink: 0 !important;
    display: inline-block !important;
}
@keyframes spin { to { transform: rotate(360deg); } }

.progress-track {
    width: 100% !important;
    height: 5px !important;
    background: #E2E8F0 !important;
    border-radius: 99px !important;
    overflow: hidden !important;
    margin-bottom: 12px !important;
}
.progress-bar {
    height: 100% !important;
    background: linear-gradient(90deg, #10B981 0%, #34D399 100%) !important;
    border-radius: 99px !important;
    animation: indeterminate 1.5s ease-in-out infinite !important;
}
@keyframes indeterminate {
    0% { transform: translateX(-100%) scaleX(0.4); }
    100% { transform: translateX(250%) scaleX(0.4); }
}

/* ═══ RESULTS CONTAINER ═══ */
.results-container {
    background: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 18px !important;
    overflow: hidden !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.04) !important;
    margin-top: 14px !important;
}
"""

# ---------------------------------------------------------------------------
# Beautiful Empty State HTML Generators
# ---------------------------------------------------------------------------

def _empty_card(icon: str, title: str, subtitle: str, tips: list[str]) -> str:
    tips_html = "".join(
        f"<span style='background:#F1F5F9;border:1px solid #E2E8F0;border-radius:999px;padding:5px 14px;font-size:12.5px;color:#475569;font-weight:600;'>{t}</span>"
        for t in tips
    )
    return clean_html(f"""
    <div style="text-align:center;padding:50px 24px;font-family:'Plus Jakarta Sans',sans-serif;color:#0F172A;">
        <div style="width:64px;height:64px;background:#ECFDF5;border:1px solid #A7F3D0;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:30px;margin-bottom:14px;box-shadow:0 2px 8px rgba(16,185,129,0.15);">
            {icon}
        </div>
        <h3 style="font-size:19px;font-weight:800;color:#0F172A;margin:0 0 6px;">{title}</h3>
        <p style="font-size:14px;color:#64748B;max-width:440px;margin:0 auto 18px;line-height:1.6;">
            {subtitle}
        </p>
        <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;max-width:540px;margin:0 auto;">
            {tips_html}
        </div>
    </div>
    """)

EMPTY_SUMMARY_HTML = _empty_card(
    "📋", "Awaiting Food Label",
    "Upload a clear photo of any packaged food label and tap <strong>Analyze Label</strong> to get an instant, honest health scorecard.",
    ["🥜 Peanut Butter", "🍪 Biscuits & Bakery", "🥣 Cereals", "🧃 Drinks", "🌿 Health Foods"],
)

EMPTY_INGREDIENTS_HTML = _empty_card(
    "🧪", "Ingredients & Additives Audit",
    "Every ingredient, INS number, and additive will be evaluated for health safety and verified against the physical pack.",
    ["Palm Oil Check", "Emulsifiers & INS", "Preservatives", "Artificial Sweeteners"],
)

EMPTY_NUTRITION_HTML = _empty_card(
    "🥗", "Nutrition Facts & Traffic Lights",
    "Sugar, saturated fat, sodium, and calories will be extracted and benchmarked against UK FSA & FSSAI standards.",
    ["Sugar Flags", "Sodium / BP Risk", "Trans Fat 0g", "High Protein"],
)

EMPTY_QA_HTML = _empty_card(
    "💬", "Sourced Label Answers",
    "Ask any question about diabetic safety, pregnancy suitability, or allergens. Answers are grounded in the physical label.",
    ["Diabetic Friendly?", "Pregnancy Safe?", "Good for Kids?", "Contains Palm Oil?"],
)

EMPTY_TRANSCRIPTION_HTML = clean_html("""
<div style="padding:40px 24px;text-align:center;font-family:'Plus Jakarta Sans',sans-serif;color:#64748B;font-size:14px;">
    Raw extracted text from your label photos will appear here for complete transparency and cross-checking.
</div>
""")


# ---------------------------------------------------------------------------
# Pipeline Generator & Helpers
# ---------------------------------------------------------------------------

def _loading_status(step: int, total: int, msg: str, elapsed: float) -> str:
    pct = min(100, int((step / max(total, 1)) * 100))
    return clean_html(
        f'<div class="status-loading">'
        f'<span class="spinner"></span>'
        f'<span><strong>Step {step}/{total}:</strong> {msg}'
        f'<span style="opacity:0.7;font-weight:600;margin-left:8px">({elapsed:.0f}s)</span></span>'
        f'</div>'
        f'<div class="progress-track">'
        f'<div class="progress-bar" style="animation:none;transform:none;width:{pct}%"></div>'
        f'</div>'
    )


def run_connection_check(api_key: str) -> str:
    effective_key = api_key.strip() if api_key and api_key.strip() else None
    res = health(backend="gemini", api_key=effective_key)
    checks = res.get("checks", [])
    overall = res.get("ok", False)

    cls = "status-ok" if overall else "status-error"
    icon = "✅" if overall else "❌"
    label = "Google AI Studio connected — Gemma 4 ready" if overall else "Connection failed — check your API key"
    lines = [f'<div class="{cls}">{icon} <strong>{label}</strong></div>']
    for c in checks:
        ci = "✅" if c.get("ok") else "❌"
        lines.append(f"<div style='font-size:13px;color:#334155;margin:4px 0;'>{ci} <strong>{c.get('name', 'Check')}</strong>: {c.get('detail', '')}</div>")
    return clean_html("".join(lines))


def run_pipeline(
    img1: Image.Image | None,
    img2: Image.Image | None,
    img3: Image.Image | None,
    language: str,
    question: str,
    api_key: str,
) -> Generator[tuple[str, str, str, str, str, str, Any], None, None]:
    """Generator driving the pipeline. Yields 7 outputs:
    (status_box, summary_html, ingredients_html, nutrition_html, qa_html, transcription_html, report_file)
    """
    effective_key = api_key.strip() if api_key and api_key.strip() else None
    images: list[Image.Image] = [img for img in (img1, img2, img3) if img is not None]

    if not images:
        yield (
            '<div class="status-error">⚠️ <strong>No label photo uploaded.</strong> Please add at least one clear photo of the food packaging.</div>',
            EMPTY_SUMMARY_HTML, EMPTY_INGREDIENTS_HTML, EMPTY_NUTRITION_HTML, EMPTY_QA_HTML, EMPTY_TRANSCRIPTION_HTML, None,
        )
        return

    yield (
        '<div class="status-loading"><span class="spinner"></span><span><strong>Connecting to Gemma 4</strong> via Google AI Studio…</span></div>'
        '<div class="progress-track"><div class="progress-bar"></div></div>',
        EMPTY_SUMMARY_HTML, EMPTY_INGREDIENTS_HTML, EMPTY_NUTRITION_HTML, EMPTY_QA_HTML, EMPTY_TRANSCRIPTION_HTML, None,
    )

    final_result: AnalysisResult | None = None
    start_wall = time.time()

    try:
        for update in analyze(
            images=images,
            language=language,
            question=question,
            backend="gemini",
            api_key=effective_key,
        ):
            if isinstance(update, ProgressUpdate):
                elapsed = time.time() - start_wall
                yield (
                    _loading_status(update.step, update.total_steps, update.message, elapsed),
                    EMPTY_SUMMARY_HTML, EMPTY_INGREDIENTS_HTML, EMPTY_NUTRITION_HTML, EMPTY_QA_HTML, EMPTY_TRANSCRIPTION_HTML, None,
                )
            elif isinstance(update, AnalysisResult):
                final_result = update

    except Exception as exc:
        logger.exception("Unexpected pipeline error: %s", exc)
        yield (
            f'<div class="status-error">⚠️ <strong>Analysis Error:</strong> {exc} — Please try again with a clearer, well-lit photo.</div>',
            EMPTY_SUMMARY_HTML, EMPTY_INGREDIENTS_HTML, EMPTY_NUTRITION_HTML, EMPTY_QA_HTML, EMPTY_TRANSCRIPTION_HTML, None,
        )
        return

    if final_result:
        report_path = render_report(final_result)
        summary_html = render_summary_html(final_result)
        ingredients_html = render_ingredients_html(final_result)
        nutrition_html = render_nutrition_html(final_result)
        qa_html = render_qa_html(final_result)
        transcription_html = render_transcription_html(final_result)

        t = final_result.seconds_taken
        if final_result.refused:
            status = (
                f'<div class="status-error">🚫 <strong>Analysis Refused:</strong> '
                f'{final_result.refusal_reason or "Label could not be analyzed."} ({t:.1f}s)</div>'
            )
        elif final_result.warnings:
            status = (
                f'<div class="status-warn">⚠️ <strong>Analysis complete with cautions</strong> — {t:.1f}s. '
                f'Please review packaging warnings below.</div>'
            )
        else:
            status = (
                f'<div class="status-ok">✅ <strong>Analysis complete</strong> — {t:.1f}s '
                f'<span style="opacity:0.75;font-weight:600"> · Gemma 4 via Google AI Studio</span></div>'
            )

        yield (
            clean_html(status),
            clean_html(summary_html),
            clean_html(ingredients_html),
            clean_html(nutrition_html),
            clean_html(qa_html),
            clean_html(transcription_html),
            report_path,
        )


# ---------------------------------------------------------------------------
# UI Construction
# ---------------------------------------------------------------------------

HEAD_SCRIPT = """
<script>
(function() {
  function forceLightTheme() {
    if (document.documentElement && document.documentElement.classList.contains('dark')) {
      document.documentElement.classList.remove('dark');
    }
    if (document.body && document.body.classList.contains('dark')) {
      document.body.classList.remove('dark');
    }
    if (document.documentElement) {
      document.documentElement.style.colorScheme = 'light';
    }
  }
  forceLightTheme();
  document.addEventListener('DOMContentLoaded', forceLightTheme);
  window.addEventListener('load', forceLightTheme);
  if (window.MutationObserver) {
    new MutationObserver(forceLightTheme).observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'style'] });
  }
})();
</script>
"""


def make_img_badge(img: Any, label: str = "Photo") -> str:
    if img is not None:
        try:
            w, h = img.size
            dim = f"{w}×{h}px"
        except Exception:
            dim = "Loaded"
        return clean_html(f'<span class="img-badge-success">✅ {label} Uploaded ({dim}) &nbsp;·&nbsp; Ready for AI Scan</span>')
    return clean_html('<span class="img-badge-pending">⏳ No image uploaded yet</span>')


def make_upload_summary(img1: Any, img2: Any, img3: Any) -> str:
    count = sum(1 for img in (img1, img2, img3) if img is not None)
    if count == 0:
        return clean_html(
            '<div class="upload-summary-bar">'
            '<div>📸 <strong>0 / 3 Photos Uploaded</strong> &nbsp;·&nbsp; '
            '<span style="color:#64748B;">Upload packaging photo to begin AI verification.</span></div>'
            '<span class="upload-summary-pill pending">Waiting for photo</span>'
            '</div>'
        )
    elif count == 1:
        return clean_html(
            '<div class="upload-summary-bar has-photos">'
            '<div>📸 <strong>✅ 1 Photo Uploaded</strong> &nbsp;·&nbsp; '
            '<span style="color:#047857;font-weight:600;">Primary packaging panel ready for AI audit!</span></div>'
            '<span class="upload-summary-pill ready">READY TO SCAN</span>'
            '</div>'
        )
    else:
        return clean_html(
            f'<div class="upload-summary-bar has-photos">'
            f'<div>📸 <strong>✅ {count} Photos Uploaded</strong> &nbsp;·&nbsp; '
            f'<span style="color:#047857;font-weight:600;">Multi-angle packaging panels loaded for full 360° audit!</span></div>'
            f'<span class="upload-summary-pill ready">{count} PANELS LOADED</span>'
            f'</div>'
        )


def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="PARAKH — Food Safety & Nutrition Intelligence",
    ) as demo:

        # ── TOP NAVIGATION ─────────────────────────────────────────────────
        gr.HTML("""
<nav class="top-bar">
  <div class="top-bar-inner">
    <div class="top-logo">
      <span class="top-logo-icon">🏷️</span>
      <div>
        <span class="top-logo-text">PARAKH (परख)</span>
        <span class="top-logo-sub">FOOD SAFETY & NUTRITION INTELLIGENCE</span>
      </div>
    </div>
    <div class="top-badge">
      <span>⚡</span> Powered by Gemma 4 · Google AI Studio
    </div>
  </div>
</nav>
""")

        with gr.Column(elem_classes=["p-wrap"]):

            # ── HERO BANNER ────────────────────────────────────────────────
            gr.HTML("""
<div class="hero-card">
  <div style="position:relative;z-index:1;">
    <div class="hero-tag">🇮🇳 Built for Indian Packaged Foods · FSSAI Norms</div>
    <h1 class="hero-title">Decode What’s <span>Actually</span> Inside Your Pack</h1>
    <p class="hero-desc">
      Snap any Indian packaged food label. Get instant, honest health scores,
      spot hidden sugars & palm oil, and verify manufacturer claims in seconds.
    </p>
    <div class="hero-stats">
      <div>
        <div class="hero-stat-val">&lt; 30s</div>
        <div class="hero-stat-lbl">Fast Turnaround</div>
      </div>
      <div>
        <div class="hero-stat-val">100%</div>
        <div class="hero-stat-lbl">Label Grounded</div>
      </div>
      <div>
        <div class="hero-stat-val">0-100</div>
        <div class="hero-stat-lbl">Health Scorecard</div>
      </div>
      <div>
        <div class="hero-stat-val">FSSAI</div>
        <div class="hero-stat-lbl">Veg/Non-Veg Check</div>
      </div>
    </div>
  </div>
</div>
""")

            # ── UPLOAD CARD ────────────────────────────────────────────────
            with gr.Column(elem_classes=["app-card"]):
                gr.HTML("""
<div class="card-head">
  <div class="card-icon">📸</div>
  <div>
    <div class="card-title">Upload Packaging Photos</div>
    <div class="card-sub">Clear photos of the ingredients panel and nutrition table give the best results</div>
  </div>
</div>
""")
                img1_input = gr.Image(
                    type="pil",
                    sources=["upload", "webcam", "clipboard"],
                    label="Front Panel or Ingredients List (Required)",
                    height=180,
                    elem_classes=["compact-img-input"],
                )
                with gr.Row(elem_classes=["img-control-row"]):
                    clear_img1_btn = gr.Button("✕ Cancel / Remove Photo", size="sm", elem_classes=["btn-remove-img"])
                    img1_badge = gr.HTML(
                        value=make_img_badge(None, "Photo 1"),
                        elem_classes=["img-badge-container"],
                    )

                with gr.Accordion("➕ Add Nutrition Table or Expiry Date Panels (Optional, for deeper audit)", open=False):
                    with gr.Row():
                        with gr.Column():
                            img2_input = gr.Image(
                                type="pil",
                                sources=["upload", "webcam", "clipboard"],
                                label="Nutrition Table Panel",
                                height=150,
                                elem_classes=["compact-img-input"],
                            )
                            with gr.Row(elem_classes=["img-control-row"]):
                                clear_img2_btn = gr.Button("✕ Remove Photo 2", size="sm", elem_classes=["btn-remove-img"])
                                img2_badge = gr.HTML(value="", elem_classes=["img-badge-container"])
                        with gr.Column():
                            img3_input = gr.Image(
                                type="pil",
                                sources=["upload", "webcam", "clipboard"],
                                label="Expiry / Batch / Other Panel",
                                height=150,
                                elem_classes=["compact-img-input"],
                            )
                            with gr.Row(elem_classes=["img-control-row"]):
                                clear_img3_btn = gr.Button("✕ Remove Photo 3", size="sm", elem_classes=["btn-remove-img"])
                                img3_badge = gr.HTML(value="", elem_classes=["img-badge-container"])

                gr.HTML(
                    '<p style="color:#64748B;font-size:12px;margin:8px 0 0;line-height:1.5;">'
                    '💡 <em>Tip: Ensure flat, bright lighting without harsh flash reflection. '
                    'For cylindrical bottles or pouches, capture panels separately.</em></p>'
                )

            # ── QUESTION + LANGUAGE CARD ───────────────────────────────────
            with gr.Column(elem_classes=["app-card"]):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=3):
                        gr.HTML("""
<div class="card-head" style="margin-bottom:8px;">
  <div class="card-icon">💬</div>
  <div>
    <div class="card-title">Ask a Specific Question <span style="font-size:12.5px;font-weight:500;color:#64748B;">(Optional)</span></div>
    <div class="card-sub">Answers are strictly verified against the physical pack — no hallucinations</div>
  </div>
</div>
""")
                        question_input = gr.Textbox(
                            label="",
                            placeholder="e.g. Is this safe during pregnancy? Can a diabetic eat this? Does it contain palm oil?",
                            lines=1,
                        )
                        with gr.Row():
                            chip1 = gr.Button("🤰 Pregnancy safe?", elem_classes=["q-chip"], size="sm")
                            chip2 = gr.Button("🩸 OK for diabetics?", elem_classes=["q-chip"], size="sm")
                            chip3 = gr.Button("👶 Good for kids?", elem_classes=["q-chip"], size="sm")
                            chip4 = gr.Button("🌱 100% Vegetarian?", elem_classes=["q-chip"], size="sm")
                            chip5 = gr.Button("🧂 Low sodium / BP?", elem_classes=["q-chip"], size="sm")
                            chip6 = gr.Button("🌴 Contains Palm Oil?", elem_classes=["q-chip"], size="sm")

                        chip1.click(lambda: "Is this food safe to eat during pregnancy?", outputs=[question_input])
                        chip2.click(lambda: "Is it okay for someone with diabetes?", outputs=[question_input])
                        chip3.click(lambda: "Is this food good for kids under 10?", outputs=[question_input])
                        chip4.click(lambda: "Is this product vegetarian?", outputs=[question_input])
                        chip5.click(lambda: "Is this a low-sodium food suitable for high blood pressure?", outputs=[question_input])
                        chip6.click(lambda: "Does this product contain palm oil, palmolein, or hydrogenated fats?", outputs=[question_input])

                    with gr.Column(scale=1):
                        gr.HTML("""
<div style="padding-left:14px;border-left:2px solid #F1F5F9;">
<div class="card-head" style="margin-bottom:8px;">
  <div class="card-icon">🌐</div>
  <div><div class="card-title">Language</div></div>
</div>
""")
                        lang_radio = gr.Radio(
                            choices=["English", "Hinglish"],
                            value="English",
                            label="",
                            elem_classes=["lang-radio"],
                        )
                        gr.HTML("</div>")

            # ── API SETTINGS ACCORDION ─────────────────────────────────────
            with gr.Accordion("⚙️ Google AI Studio API Settings & Connection Check", open=False):
                with gr.Row(equal_height=True):
                    api_key_input = gr.Textbox(
                        label="Google AI Studio API Key (Leave blank to use server environment key)",
                        placeholder="Paste your Gemini / Gemma 4 API key here",
                        type="password",
                        scale=3,
                    )
                    check_btn = gr.Button(
                        "🔌 Test Connection",
                        scale=1,
                        elem_classes=["btn-secondary"],
                    )
                conn_status = gr.HTML(value="", visible=True)

            # ── UPLOAD CONFIRMATION & STATUS ───────────────────────────────
            upload_summary_box = gr.HTML(
                value=make_upload_summary(None, None, None),
                elem_classes=["upload-summary-wrapper"],
            )

            # ── ACTION BUTTONS ─────────────────────────────────────────────
            with gr.Row():
                analyze_btn = gr.Button(
                    "🔍  Analyze Food Label",
                    variant="primary",
                    scale=4,
                    elem_classes=["btn-primary"],
                )
                clear_btn = gr.Button(
                    "✕  Clear All",
                    variant="secondary",
                    scale=1,
                    elem_classes=["btn-secondary"],
                )

            # ── STATUS BOX ─────────────────────────────────────────────────
            status_box = gr.HTML(value="", visible=True)

            # ── RESULTS PANEL ──────────────────────────────────────────────
            with gr.Column(elem_classes=["results-container"]):
                with gr.Tabs():
                    with gr.TabItem("📋 Overview & Verdict"):
                        summary_output = gr.HTML(
                            value=EMPTY_SUMMARY_HTML,
                        )
                    with gr.TabItem("🧪 Ingredients & Additives"):
                        ingredients_output = gr.HTML(
                            value=EMPTY_INGREDIENTS_HTML,
                        )
                    with gr.TabItem("🥗 Nutrition Facts"):
                        nutrition_output = gr.HTML(
                            value=EMPTY_NUTRITION_HTML,
                        )
                    with gr.TabItem("💬 Evidence Q & A"):
                        qa_output = gr.HTML(
                            value=EMPTY_QA_HTML,
                        )
                    with gr.TabItem("📄 Raw Pack Text"):
                        transcription_output = gr.HTML(
                            value=EMPTY_TRANSCRIPTION_HTML,
                        )

                report_file = gr.File(
                    label="📥 Download Full Health Report (.md)",
                    interactive=False,
                )

            # ── FOOTER ─────────────────────────────────────────────────────
            gr.HTML(f"""
<div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:14px;padding:18px 24px;margin-top:24px;font-size:12.5px;color:#64748B;line-height:1.7;">
  ⚠️ <strong>Disclaimer:</strong> {DISCLAIMER_H10}<br>
  🔒 <em>Privacy: Label images are processed in-memory only. No images are permanently stored.</em>
  &nbsp;·&nbsp; 🤖 <em>Powered by Gemma 4 via Google AI Studio.</em>
</div>
""")

            # ── EVENT BINDINGS ──────────────────────────────────────────────
            check_btn.click(
                fn=run_connection_check,
                inputs=[api_key_input],
                outputs=[conn_status],
            )

            analyze_btn.click(
                fn=run_pipeline,
                inputs=[
                    img1_input, img2_input, img3_input,
                    lang_radio, question_input, api_key_input,
                ],
                outputs=[
                    status_box, summary_output, ingredients_output,
                    nutrition_output, qa_output, transcription_output, report_file,
                ],
                concurrency_limit=1,
            )

            # ── PHOTO CHANGE & CANCEL HANDLERS ─────────────────────────────
            def on_img1_change(img, i2, i3):
                return make_img_badge(img, "Photo 1"), make_upload_summary(img, i2, i3)

            def on_img2_change(img, i1, i3):
                badge = make_img_badge(img, "Photo 2") if img is not None else ""
                return badge, make_upload_summary(i1, img, i3)

            def on_img3_change(img, i1, i2):
                badge = make_img_badge(img, "Photo 3") if img is not None else ""
                return badge, make_upload_summary(i1, i2, img)

            def clear_img1_fn(i2, i3):
                return None, make_img_badge(None, "Photo 1"), make_upload_summary(None, i2, i3)

            def clear_img2_fn(i1, i3):
                return None, "", make_upload_summary(i1, None, i3)

            def clear_img3_fn(i1, i2):
                return None, "", make_upload_summary(i1, i2, None)

            clear_img1_btn.click(
                fn=clear_img1_fn,
                inputs=[img2_input, img3_input],
                outputs=[img1_input, img1_badge, upload_summary_box],
            )
            clear_img2_btn.click(
                fn=clear_img2_fn,
                inputs=[img1_input, img3_input],
                outputs=[img2_input, img2_badge, upload_summary_box],
            )
            clear_img3_btn.click(
                fn=clear_img3_fn,
                inputs=[img1_input, img2_input],
                outputs=[img3_input, img3_badge, upload_summary_box],
            )

            img1_input.change(
                fn=on_img1_change,
                inputs=[img1_input, img2_input, img3_input],
                outputs=[img1_badge, upload_summary_box],
            )
            img2_input.change(
                fn=on_img2_change,
                inputs=[img2_input, img1_input, img3_input],
                outputs=[img2_badge, upload_summary_box],
            )
            img3_input.change(
                fn=on_img3_change,
                inputs=[img3_input, img1_input, img2_input],
                outputs=[img3_badge, upload_summary_box],
            )

            def clear_all() -> tuple[Any, ...]:
                return (
                    None, None, None,                  # images
                    make_img_badge(None, "Photo 1"),   # img1_badge
                    "",                                # img2_badge
                    "",                                # img3_badge
                    make_upload_summary(None, None, None),  # upload_summary_box
                    "",                                # question
                    "",                                # conn_status
                    "",                                # status_box
                    EMPTY_SUMMARY_HTML,
                    EMPTY_INGREDIENTS_HTML,
                    EMPTY_NUTRITION_HTML,
                    EMPTY_QA_HTML,
                    EMPTY_TRANSCRIPTION_HTML,
                    None,                              # report_file
                )

            clear_btn.click(
                fn=clear_all,
                outputs=[
                    img1_input, img2_input, img3_input,
                    img1_badge, img2_badge, img3_badge,
                    upload_summary_box,
                    question_input, conn_status, status_box,
                    summary_output, ingredients_output,
                    nutrition_output, qa_output,
                    transcription_output, report_file,
                ],
            )

    return demo


def main():
    demo = build_app()
    demo.queue(max_size=8).launch(
        server_name=settings.app_host,
        server_port=settings.app_port,
        share=False,
        show_error=True,
        head=HEAD_SCRIPT,
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(
            primary_hue="emerald",
            neutral_hue="slate",
            font=[gr.themes.GoogleFont("Plus Jakarta Sans"), "sans-serif"],
        ),
    )


if __name__ == "__main__":
    main()
