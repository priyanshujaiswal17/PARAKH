"""Rendering module producing rich, responsive HTML tabs and downloadable Markdown reports.

Engineered for high-contrast readability, age-inclusive typography,
and comprehensive packaged-food intelligence (FSSAI norms, Nutri-Score, allergens).
"""

from __future__ import annotations

import glob
import html
import os
import time
from pathlib import Path
from typing import Any

from config import BASE_DIR
from pipeline.models import AnalysisResult, IngredientRating

DISCLAIMER_H10 = "⚠️ Disclaimer: Not medical advice. Always check the physical packaging. Ratings are based on established nutritional science."

RATING_ICONS = {
    "good": "🟢 Good",
    "neutral": "🟡 Neutral",
    "watch": "🟠 Watch",
    "limit": "🔴 Limit",
    "not_rated": "⚪ Not rated",
}

QA_BADGES = {
    "label": "📄 From physical label",
    "general": "🌐 General nutritional science",
    "both": "📄🌐 Label + Science",
    "cannot_tell": "❓ Cannot determine from label",
}


def clean_html(val: str) -> str:
    """Strips leading/trailing indentation from each line so CommonMark renders raw HTML instead of code blocks."""
    if not val:
        return ""
    lines = [line.strip() for line in val.splitlines() if line.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Health Score & Classification Calculation
# ---------------------------------------------------------------------------

def calculate_health_score(result: AnalysisResult) -> dict[str, Any]:
    """Calculates an intelligent 0-100 formulation score, processing level, and health tier."""
    score = 70  # Baseline

    # Adjust based on ingredient ratings
    if result.ratings:
        for r in result.ratings:
            if r.level == "good":
                score += 4
            elif r.level == "limit":
                score -= 14
            elif r.level == "watch":
                score -= 6

    # Adjust based on nutrition flags (UK FSA benchmarks)
    if result.nutrition_flags:
        for f in result.nutrition_flags:
            if f.level == "high":
                if f.nutrient in ("sugar", "saturated_fat"):
                    score -= 10
                elif f.nutrient == "salt":
                    score -= 8
                else:
                    score -= 6
            elif f.level == "low":
                if f.nutrient in ("sugar", "salt"):
                    score += 4
                else:
                    score += 2

    # Adjust based on key nutrients if available
    if result.extract and result.extract.nutrition and result.extract.nutrition.values:
        vals = result.extract.nutrition.values
        if vals.added_sugar_g is not None:
            if vals.added_sugar_g == 0:
                score += 6
            elif vals.added_sugar_g > 15:
                score -= 12
        if vals.protein_g is not None and vals.protein_g >= 15:
            score += 8
        if vals.trans_fat_g is not None and vals.trans_fat_g == 0:
            score += 4
        if vals.fibre_g is not None and vals.fibre_g >= 6:
            score += 5

    # Check for palm oil in ingredients
    if result.extract and result.extract.ingredients:
        ing_lower = " ".join(result.extract.ingredients).lower()
        if "palm oil" in ing_lower or "palmolein" in ing_lower or "palm kernel" in ing_lower:
            score -= 12

    # Clamp score to reasonable range
    score = max(18, min(96, score))

    if score >= 80:
        verdict = "Clean & High Quality"
        color = "#16A34A"  # Green
        bg = "#DCFCE7"
        border = "#86EFAC"
        tier = "Whole Food / Minimally Processed"
    elif score >= 65:
        verdict = "Nutritious with Cautions"
        color = "#2563EB"  # Blue
        bg = "#DBEAFE"
        border = "#93C5FD"
        tier = "Moderately Processed"
    elif score >= 50:
        verdict = "Moderate · Watch Portions"
        color = "#D97706"  # Amber
        bg = "#FEF3C7"
        border = "#FCD34D"
        tier = "Processed Packaged Food"
    else:
        verdict = "Caution · Ultra-Processed"
        color = "#DC2626"  # Red
        bg = "#FEE2E2"
        border = "#FCA5A5"
        tier = "Ultra-Processed (Limit Consumption)"

    return {
        "score": score,
        "verdict": verdict,
        "color": color,
        "bg": bg,
        "border": border,
        "tier": tier,
    }


# ---------------------------------------------------------------------------
# HTML Tab Renderers
# ---------------------------------------------------------------------------

def render_summary_html(result: AnalysisResult) -> str:
    """Produces a comprehensive, bespoke HTML view for the Summary tab."""
    if result.refused:
        reason = html.escape(result.refusal_reason or "This image does not appear to be a packaged food label.")
        return clean_html(f"""
        <div style="background:#FEF2F2;border:2px solid #FCA5A5;border-radius:16px;padding:24px;margin:20px 0;color:#991B1B;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <span style="font-size:32px;">🚫</span>
                <div>
                    <h3 style="margin:0;font-size:20px;font-weight:800;color:#991B1B;">Analysis Refused</h3>
                    <p style="margin:4px 0 0;font-size:14px;color:#B91C1C;">PARAKH only analyzes packaged food labels.</p>
                </div>
            </div>
            <div style="background:#FFFFFF;border-radius:10px;padding:14px 18px;border:1px solid #FECACA;font-size:15px;line-height:1.6;color:#7F1D1D;">
                {reason}
            </div>
        </div>
        """)

    extract = result.extract
    summary = result.summary
    score_info = calculate_health_score(result)

    prod_name = html.escape((extract.product_name if extract else None) or "Packaged Food Item")
    brand_name = html.escape((extract.brand if extract else "") or "")
    net_qty = html.escape((extract.net_quantity if extract else "") or "")
    fssai_lic = html.escape((extract.fssai_license if extract else "") or "")
    veg_mark = extract.veg_mark if extract else "unknown"

    # Veg Mark Icon (Official Indian Packaging Standard)
    if veg_mark == "veg":
        veg_html = """
        <div style="display:inline-flex;align-items:center;gap:8px;background:#F0FDF4;border:1.5px solid #22C55E;border-radius:999px;padding:4px 14px;color:#15803D;font-weight:700;font-size:13px;">
            <span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:2px solid #16A34A;border-radius:3px;background:#FFFFFF;">
                <span style="width:9px;height:9px;border-radius:50%;background:#16A34A;"></span>
            </span>
            100% Vegetarian
        </div>
        """
    elif veg_mark == "non_veg":
        veg_html = """
        <div style="display:inline-flex;align-items:center;gap:8px;background:#FEF2F2;border:1.5px solid #EF4444;border-radius:999px;padding:4px 14px;color:#B91C1C;font-weight:700;font-size:13px;">
            <span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:2px solid #DC2626;border-radius:3px;background:#FFFFFF;">
                <span style="width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:9px solid #DC2626;"></span>
            </span>
            Non-Vegetarian
        </div>
        """
    else:
        veg_html = """
        <div style="display:inline-flex;align-items:center;gap:8px;background:#F1F5F9;border:1.5px solid #94A3B8;border-radius:999px;padding:4px 14px;color:#475569;font-weight:600;font-size:13px;">
            ⚪ Veg/Non-Veg Mark Not Detected
        </div>
        """

    # Warnings Banner
    warnings_html = ""
    if result.warnings:
        warn_items = "".join(f"<li style='margin-bottom:6px;'>{html.escape(w)}</li>" for w in result.warnings)
        warnings_html = f"""
        <div style="background:#FFFBEB;border:1.5px solid #FCD34D;border-radius:14px;padding:16px 20px;margin-bottom:20px;color:#92400E;">
            <div style="display:flex;align-items:center;gap:8px;font-weight:800;font-size:15px;margin-bottom:8px;">
                <span>⚠️</span> <span>Packaging Notice / Cautions</span>
            </div>
            <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.5;color:#78350F;">
                {warn_items}
            </ul>
        </div>
        """

    # Key Nutrition Metrics
    nut_tiles = ""
    if extract and extract.nutrition and extract.nutrition.values:
        vals = extract.nutrition.values
        basis_txt = extract.nutrition.basis.replace("_", " ").title() if extract.nutrition.basis else "Per Serving"

        # Energy
        energy_txt = f"{vals.energy_kcal:g} kcal" if vals.energy_kcal is not None else "Not listed"
        # Protein
        prot_txt = f"{vals.protein_g:g} g" if vals.protein_g is not None else "—"
        prot_badge = "High Protein" if (vals.protein_g and vals.protein_g >= 10) else "Protein"
        # Added Sugar
        sugar_txt = f"{vals.added_sugar_g:g} g" if vals.added_sugar_g is not None else (
            f"{vals.total_sugar_g:g} g (total)" if vals.total_sugar_g is not None else "—"
        )
        sugar_badge = "Zero Added Sugar" if vals.added_sugar_g == 0 else "Sugar"
        sugar_color = "#16A34A" if (vals.added_sugar_g == 0 or (vals.total_sugar_g and vals.total_sugar_g < 5)) else (
            "#DC2626" if (vals.total_sugar_g and vals.total_sugar_g > 15) else "#D97706"
        )
        # Sodium / Salt
        sod_txt = f"{vals.sodium_mg:g} mg" if vals.sodium_mg is not None else "—"

        nut_tiles = f"""
        <div style="margin:20px 0;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                <span style="font-size:13px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;">Nutrition Highlights ({basis_txt})</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:12px;">
                <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:12px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;">⚡ Energy</div>
                    <div style="font-size:20px;font-weight:800;color:#0F172A;margin:4px 0 2px;">{energy_txt}</div>
                    <div style="font-size:11px;color:#10B981;font-weight:600;">Fuel Value</div>
                </div>
                <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:12px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;">🥩 Protein</div>
                    <div style="font-size:20px;font-weight:800;color:#0F172A;margin:4px 0 2px;">{prot_txt}</div>
                    <div style="font-size:11px;color:#2563EB;font-weight:600;">{prot_badge}</div>
                </div>
                <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:12px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;">🍬 Sugar</div>
                    <div style="font-size:20px;font-weight:800;color:{sugar_color};margin:4px 0 2px;">{sugar_txt}</div>
                    <div style="font-size:11px;color:{sugar_color};font-weight:600;">{sugar_badge}</div>
                </div>
                <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:12px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;">🧂 Sodium</div>
                    <div style="font-size:20px;font-weight:800;color:#0F172A;margin:4px 0 2px;">{sod_txt}</div>
                    <div style="font-size:11px;color:#64748B;font-weight:600;">Salt Content</div>
                </div>
            </div>
        </div>
        """

    # Claims Badges
    claims_html = ""
    if extract and extract.claims:
        badges = "".join(
            f"""<span style="display:inline-flex;align-items:center;gap:5px;background:#F8FAFC;border:1px solid #CBD5E1;border-radius:999px;padding:4px 12px;font-size:12.5px;font-weight:600;color:#334155;">
                ✨ {html.escape(c)}
            </span>"""
            for c in extract.claims
        )
        claims_html = f"""
        <div style="margin:16px 0;display:flex;flex-wrap:wrap;gap:8px;">
            {badges}
        </div>
        """

    # What it is narrative
    what_it_is_html = ""
    if summary and summary.what_it_is:
        what_it_is_html = f"""
        <div style="background:#F8FAFC;border-left:4px solid #10B981;border-radius:0 12px 12px 0;padding:16px 20px;margin:18px 0;">
            <div style="font-size:12px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
                📋 Product Breakdown
            </div>
            <div style="font-size:15px;color:#1E293B;line-height:1.65;font-weight:500;">
                {html.escape(summary.what_it_is)}
            </div>
        </div>
        """

    # Good Things vs Things to Watch (2-Column Grid)
    good_items_html = ""
    if summary and summary.good_things:
        items = "".join(
            f"""
            <div style="display:flex;align-items:flex-start;gap:10px;background:#FFFFFF;border:1px solid #DCFCE7;border-radius:10px;padding:10px 14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
                <span style="color:#16A34A;font-size:16px;font-weight:800;line-height:1.2;">✓</span>
                <span style="font-size:14px;color:#14532D;font-weight:600;line-height:1.4;">{html.escape(item)}</span>
            </div>
            """
            for item in summary.good_things
        )
        good_items_html = f"""
        <div style="background:#F0FDF4;border:1.5px solid #86EFAC;border-radius:14px;padding:18px;display:flex;flex-direction:column;gap:10px;">
            <div style="display:flex;align-items:center;gap:8px;font-weight:800;font-size:15px;color:#166534;margin-bottom:4px;">
                <span style="background:#DCFCE7;width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:14px;">👍</span>
                Good Things
            </div>
            {items}
        </div>
        """

    watch_items_html = ""
    if summary and summary.watch_out:
        items = "".join(
            f"""
            <div style="display:flex;align-items:flex-start;gap:10px;background:#FFFFFF;border:1px solid #FEF3C7;border-radius:10px;padding:10px 14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
                <span style="color:#D97706;font-size:16px;font-weight:800;line-height:1.2;">!</span>
                <span style="font-size:14px;color:#78350F;font-weight:600;line-height:1.4;">{html.escape(item)}</span>
            </div>
            """
            for item in summary.watch_out
        )
        watch_items_html = f"""
        <div style="background:#FFFBEB;border:1.5px solid #FCD34D;border-radius:14px;padding:18px;display:flex;flex-direction:column;gap:10px;">
            <div style="display:flex;align-items:center;gap:8px;font-weight:800;font-size:15px;color:#92400E;margin-bottom:4px;">
                <span style="background:#FEF3C7;width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:14px;">⚠️</span>
                Things to Watch
            </div>
            {items}
        </div>
        """

    grid_section = ""
    if good_items_html or watch_items_html:
        grid_section = f"""
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:16px;margin:20px 0;">
            {good_items_html}
            {watch_items_html}
        </div>
        """

    # Who it Suits & Who Should Avoid
    suits_html = ""
    if summary and summary.suits:
        badges = "".join(
            f"""<span style="background:#EFF6FF;border:1px solid #BFDBFE;color:#1E40AF;border-radius:8px;padding:6px 12px;font-size:13px;font-weight:600;">
                {html.escape(s)}
            </span>"""
            for s in summary.suits
        )
        suits_html = f"""
        <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:14px;padding:16px 20px;margin-bottom:14px;">
            <div style="font-size:14px;font-weight:700;color:#1E3A8A;margin-bottom:10px;display:flex;align-items:center;gap:8px;">
                <span>👥</span> Who It Suits
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
                {badges}
            </div>
        </div>
        """

    avoid_html = ""
    if summary and summary.avoid_or_ask_doctor:
        badges = "".join(
            f"""<span style="background:#FEF2F2;border:1px solid #FECACA;color:#991B1B;border-radius:8px;padding:6px 12px;font-size:13px;font-weight:600;">
                {html.escape(a)}
            </span>"""
            for a in summary.avoid_or_ask_doctor
        )
        avoid_html = f"""
        <div style="background:#FFFFFF;border:1.5px solid #FECACA;border-radius:14px;padding:16px 20px;margin-bottom:14px;">
            <div style="font-size:14px;font-weight:700;color:#991B1B;margin-bottom:10px;display:flex;align-items:center;gap:8px;">
                <span>🩺</span> Who Should Avoid or Ask a Doctor
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
                {badges}
            </div>
        </div>
        """

    # Overall Note
    note_html = ""
    if summary and summary.overall_note:
        note_html = f"""
        <div style="background:#F0FDF4;border:1.5px solid #86EFAC;border-radius:14px;padding:18px 22px;margin:20px 0;">
            <div style="font-size:13px;font-weight:700;color:#166534;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                <span>💡</span> Nutritionist Verdict
            </div>
            <div style="font-size:15px;color:#14532D;line-height:1.6;font-weight:500;">
                {html.escape(summary.overall_note)}
            </div>
        </div>
        """

    # Expiry Card
    expiry_html = ""
    if result.expiry:
        exp_status = result.expiry.status
        exp_color = "#DC2626" if exp_status == "expired" else ("#D97706" if exp_status == "expires_soon" else "#16A34A")
        exp_bg = "#FEF2F2" if exp_status == "expired" else ("#FFFBEB" if exp_status == "expires_soon" else "#F0FDF4")
        exp_border = "#FCA5A5" if exp_status == "expired" else ("#FCD34D" if exp_status == "expires_soon" else "#86EFAC")
        exp_icon = "🔴" if exp_status == "expired" else ("🟡" if exp_status == "expires_soon" else "🟢")

        expiry_html = f"""
        <div style="background:{exp_bg};border:1.5px solid {exp_border};border-radius:12px;padding:14px 18px;margin:16px 0;display:flex;align-items:center;gap:12px;">
            <span style="font-size:22px;">{exp_icon}</span>
            <div>
                <div style="font-size:12px;font-weight:700;color:{exp_color};text-transform:uppercase;">Expiry & Shelf Life</div>
                <div style="font-size:14px;font-weight:600;color:#0F172A;margin-top:2px;">{html.escape(result.expiry.explanation)}</div>
            </div>
        </div>
        """

    # Allergen Notice
    if result.verified_allergens:
        allergen_names = ", ".join(f"<strong>{html.escape(a.text)}</strong>" for a in result.verified_allergens)
        allergen_html = f"""
        <div style="background:#FEF2F2;border:2px solid #F87171;border-radius:12px;padding:14px 18px;margin:16px 0;color:#991B1B;">
            <div style="display:flex;align-items:center;gap:8px;font-weight:800;font-size:14px;margin-bottom:4px;">
                <span>⚠️</span> <span>ALLERGEN WARNING DETECTED</span>
            </div>
            <div style="font-size:14px;line-height:1.5;">Contains / May Contain: {allergen_names}</div>
        </div>
        """
    else:
        allergen_html = """
        <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:12px 16px;margin:16px 0;font-size:13px;color:#64748B;">
            ℹ️ No explicit allergen declaration found on photographed panels. Always inspect the physical packaging.
        </div>
        """

    # Package metadata chips (FSSAI, net qty)
    meta_chips = []
    if brand_name:
        meta_chips.append(f"<strong>Brand:</strong> {brand_name}")
    if net_qty:
        meta_chips.append(f"<strong>Net Qty:</strong> {net_qty}")
    if fssai_lic:
        meta_chips.append(f"<strong>FSSAI Lic:</strong> {fssai_lic}")
    meta_row = " &nbsp;·&nbsp; ".join(meta_chips)
    meta_row_html = f"<div style='font-size:13px;color:#64748B;margin-top:4px;'>{meta_row}</div>" if meta_chips else ""

    # Footer
    footer_html = f"""
    <div style="margin-top:28px;padding-top:16px;border-top:1px solid #E2E8F0;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;font-size:12px;color:#94A3B8;">
        <span>🤖 Analyzed by Gemma 4 · Google AI Studio</span>
        <span>⏱️ Processed in {result.seconds_taken:.1f}s</span>
        <span>{DISCLAIMER_H10}</span>
    </div>
    """

    return clean_html(f"""
    <div style="font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;color:#0F172A;padding:4px;">
        {warnings_html}

        <!-- Top Product Header & Health Score Card -->
        <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:18px;padding:24px;box-shadow:0 4px 20px -2px rgba(15,23,42,0.06);margin-bottom:20px;">
            <div style="display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:16px;">
                <div style="flex:1;min-width:260px;">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                        {veg_html}
                        <span style="background:{score_info['bg']};border:1px solid {score_info['border']};color:{score_info['color']};border-radius:999px;padding:4px 12px;font-size:12px;font-weight:700;">
                            {score_info['tier']}
                        </span>
                    </div>
                    <h2 style="font-size:26px;font-weight:800;color:#0F172A;margin:8px 0 4px;letter-spacing:-0.5px;">
                        {prod_name}
                    </h2>
                    {meta_row_html}
                    {claims_html}
                </div>

                <!-- Scorecard Badge -->
                <div style="background:{score_info['bg']};border:2px solid {score_info['border']};border-radius:16px;padding:16px 22px;text-align:center;min-width:140px;box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                    <div style="font-size:11px;font-weight:800;color:{score_info['color']};text-transform:uppercase;letter-spacing:0.5px;">Health Score</div>
                    <div style="font-size:38px;font-weight:900;color:{score_info['color']};line-height:1.1;margin:4px 0;">
                        {score_info['score']}<span style="font-size:18px;font-weight:600;opacity:0.7;">/100</span>
                    </div>
                    <div style="font-size:12.5px;font-weight:700;color:{score_info['color']};">
                        {score_info['verdict']}
                    </div>
                </div>
            </div>
        </div>

        {nut_tiles}
        {what_it_is_html}
        {grid_section}

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:14px;margin:16px 0;">
            {suits_html}
            {avoid_html}
        </div>

        {expiry_html}
        {allergen_html}
        {note_html}
        {footer_html}
    </div>
    """)


def render_ingredients_html(result: AnalysisResult) -> str:
    """Produces a clean, visual card view for all ingredients and additives."""
    if not result.ratings:
        if result.refused:
            return clean_html("<div style='padding:24px;text-align:center;color:#64748B;'>Analysis refused. No ingredients analyzed.</div>")
        return clean_html("<div style='padding:24px;text-align:center;color:#64748B;'>No ingredients found on photographed panels. Check pack.</div>")

    good_count = sum(1 for r in result.ratings if r.level == "good")
    neutral_count = sum(1 for r in result.ratings if r.level == "neutral")
    watch_count = sum(1 for r in result.ratings if r.level == "watch")
    limit_count = sum(1 for r in result.ratings if r.level == "limit")
    total_count = len(result.ratings)

    # Ingredients Summary Banner
    summary_strip = f"""
    <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:14px;padding:16px 20px;margin-bottom:20px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;box-shadow:0 2px 6px rgba(0,0,0,0.03);">
        <div>
            <div style="font-size:12px;font-weight:700;color:#64748B;text-transform:uppercase;">Ingredients Audit</div>
            <div style="font-size:18px;font-weight:800;color:#0F172A;margin-top:2px;">{total_count} Identified Ingredients</div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">
            <span style="background:#DCFCE7;border:1px solid #86EFAC;color:#166534;font-size:12.5px;font-weight:700;padding:4px 12px;border-radius:999px;">
                🟢 {good_count} Good
            </span>
            <span style="background:#F1F5F9;border:1px solid #CBD5E1;color:#475569;font-size:12.5px;font-weight:700;padding:4px 12px;border-radius:999px;">
                🟡 {neutral_count} Neutral
            </span>
            <span style="background:#FEF3C7;border:1px solid #FCD34D;color:#92400E;font-size:12.5px;font-weight:700;padding:4px 12px;border-radius:999px;">
                🟠 {watch_count} Watch
            </span>
            <span style="background:#FEE2E2;border:1px solid #FCA5A5;color:#991B1B;font-size:12.5px;font-weight:700;padding:4px 12px;border-radius:999px;">
                🔴 {limit_count} Limit
            </span>
        </div>
    </div>
    """

    # Individual Ingredient Cards
    cards = []
    for r in result.ratings:
        lvl = r.level
        if lvl == "good":
            lvl_badge = "🟢 Good"
            lvl_color = "#16A34A"
            lvl_bg = "#DCFCE7"
            lvl_bd = "#86EFAC"
        elif lvl == "watch":
            lvl_badge = "🟠 Watch"
            lvl_color = "#D97706"
            lvl_bg = "#FEF3C7"
            lvl_bd = "#FCD34D"
        elif lvl == "limit":
            lvl_badge = "🔴 Limit"
            lvl_color = "#DC2626"
            lvl_bg = "#FEE2E2"
            lvl_bd = "#FCA5A5"
        else:
            lvl_badge = "🟡 Neutral"
            lvl_color = "#475569"
            lvl_bg = "#F1F5F9"
            lvl_bd = "#CBD5E1"

        ins_badge = f"<span style='background:#F1F5F9;border:1px solid #E2E8F0;color:#64748B;font-size:11px;font-weight:600;padding:2px 8px;border-radius:4px;'>INS {html.escape(r.ins_number)}</span>" if r.ins_number else ""
        verified_mark = "✓ <span style='font-size:11px;opacity:0.8;'>Verified on pack</span>" if r.verified else ""

        cards.append(f"""
        <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:14px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.03);display:flex;flex-direction:column;gap:8px;transition:transform 0.15s ease;">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:16px;font-weight:800;color:#0F172A;">{html.escape(r.name)}</span>
                    {ins_badge}
                </div>
                <span style="background:{lvl_bg};border:1px solid {lvl_bd};color:{lvl_color};font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;">
                    {lvl_badge}
                </span>
            </div>
            <div style="font-size:14px;color:#334155;line-height:1.5;font-weight:500;">
                {html.escape(r.reason)}
            </div>
            <div style="font-size:11.5px;color:#10B981;font-weight:600;margin-top:2px;">
                {verified_mark}
            </div>
        </div>
        """)

    cards_grid = f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:14px;">
        {''.join(cards)}
    </div>
    """

    return clean_html(f"""
    <div style="font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;padding:4px;">
        {summary_strip}
        {cards_grid}
        <div style="margin-top:24px;font-size:12px;color:#94A3B8;text-align:center;">
            * Ratings grounded in curated food science benchmarks and label ingredient order.
        </div>
    </div>
    """)


def render_nutrition_html(result: AnalysisResult) -> str:
    """Produces the Nutrition facts tab with traffic lights and full nutrient breakdown."""
    if not result.extract or not result.extract.nutrition:
        return clean_html("<div style='padding:24px;text-align:center;color:#64748B;'>No nutrition information extracted from label. Check pack.</div>")

    nut = result.extract.nutrition
    basis = nut.basis.replace("_", " ").title() if nut.basis else "Per 100g"
    vals = nut.values

    # Traffic Light Cards (UK FSA / FSSAI)
    traffic_cards = []
    if result.nutrition_flags:
        for flag in result.nutrition_flags:
            lvl = flag.level
            if lvl == "low":
                pill = "🟢 LOW"
                col = "#16A34A"
                bg = "#DCFCE7"
                bd = "#86EFAC"
            elif lvl == "medium":
                pill = "🟡 MEDIUM"
                col = "#D97706"
                bg = "#FEF3C7"
                bd = "#FCD34D"
            else:
                pill = "🔴 HIGH"
                col = "#DC2626"
                bg = "#FEE2E2"
                bd = "#FCA5A5"

            traffic_cards.append(f"""
            <div style="background:#FFFFFF;border:1.5px solid {bd};border-radius:14px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                    <span style="font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">{html.escape(flag.nutrient.title())}</span>
                    <span style="background:{bg};border:1px solid {bd};color:{col};font-size:11.5px;font-weight:800;padding:2px 8px;border-radius:999px;">
                        {pill}
                    </span>
                </div>
                <div style="font-size:24px;font-weight:900;color:#0F172A;margin:2px 0;">
                    {flag.value:g} <span style="font-size:14px;font-weight:600;color:#64748B;">{html.escape(flag.unit)}</span>
                </div>
                <div style="font-size:12px;color:#64748B;line-height:1.4;margin-top:4px;">
                    {html.escape(flag.threshold_note)}
                </div>
            </div>
            """)

    traffic_strip = ""
    if traffic_cards:
        traffic_strip = f"""
        <div style="margin-bottom:24px;">
            <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:12px;display:flex;align-items:center;gap:8px;">
                <span>🚦</span> Traffic Light Assessment (UK FSA / FSSAI Reference)
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;">
                {''.join(traffic_cards)}
            </div>
        </div>
        """

    # Official-style Nutrition Table
    field_labels = [
        ("Energy", vals.energy_kcal, "kcal"),
        ("Protein", vals.protein_g, "g"),
        ("Carbohydrates", vals.carbohydrate_g, "g"),
        ("Total Sugar", vals.total_sugar_g, "g"),
        ("Added Sugar", vals.added_sugar_g, "g"),
        ("Total Fat", vals.total_fat_g, "g"),
        ("Saturated Fat", vals.saturated_fat_g, "g"),
        ("Trans Fat", vals.trans_fat_g, "g"),
        ("Dietary Fibre", vals.fibre_g, "g"),
        ("Sodium", vals.sodium_mg, "mg"),
        ("Cholesterol", vals.cholesterol_mg, "mg"),
    ]

    rows = []
    for label, val, unit in field_labels:
        if val is not None:
            is_bold = label in ("Energy", "Protein", "Total Sugar", "Total Fat")
            weight = "800" if is_bold else "500"
            color = "#0F172A" if is_bold else "#334155"
            rows.append(f"""
            <tr style="border-bottom:1px solid #E2E8F0;">
                <td style="padding:12px 16px;font-weight:{weight};color:{color};font-size:14px;">{label}</td>
                <td style="padding:12px 16px;text-align:right;font-weight:{weight};color:{color};font-size:14px;">{val:g} {unit}</td>
            </tr>
            """)

    serving_txt = f" · Serving size: {html.escape(nut.serving_size_text)}" if nut.serving_size_text else ""

    table_html = f"""
    <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:14px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.03);">
        <div style="background:#F8FAFC;padding:14px 20px;border-bottom:1.5px solid #E2E8F0;display:flex;align-items:center;justify-content:space-between;">
            <div>
                <span style="font-size:15px;font-weight:800;color:#0F172A;">Nutrition Facts</span>
                <span style="font-size:13px;color:#64748B;">({basis}{serving_txt})</span>
            </div>
            <span style="font-size:12px;font-weight:700;color:#10B981;background:#ECFDF5;padding:4px 10px;border-radius:6px;">Verified From Pack</span>
        </div>
        <table style="width:100%;border-collapse:collapse;">
            {''.join(rows) if rows else "<tr><td colspan='2' style='padding:20px;text-align:center;color:#64748B;'>No numeric nutrient values found on label.</td></tr>"}
        </table>
    </div>
    """

    return clean_html(f"""
    <div style="font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;padding:4px;">
        {traffic_strip}
        {table_html}
    </div>
    """)


def render_qa_html(result: AnalysisResult) -> str:
    """Produces the evidence-backed Q&A response card."""
    if not result.qa:
        return clean_html("<div style='padding:24px;text-align:center;color:#64748B;'>No question was asked during analysis. Enter a question above to get a sourced answer.</div>")

    qa = result.qa
    badge = QA_BADGES.get(qa.source, "❓ General Knowledge")
    downgrade_note = " <span style='font-size:11px;color:#D97706;font-weight:600;'>(Evidence unverified on label; answered via general nutritional science)</span>" if qa.downgraded else ""

    evidence_html = ""
    if qa.evidence:
        quotes = "".join(
            f"""
            <div style="background:#F8FAFC;border-left:3px solid #10B981;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px;font-size:13.5px;color:#334155;font-style:italic;">
                "{html.escape(ev)}"
            </div>
            """
            for ev in qa.evidence
        )
        evidence_html = f"""
        <div style="margin-top:18px;">
            <div style="font-size:12px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                📄 Exact Quoted Evidence from Pack
            </div>
            {quotes}
        </div>
        """

    return clean_html(f"""
    <div style="font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;padding:4px;">
        <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:16px;padding:24px;box-shadow:0 4px 16px -2px rgba(15,23,42,0.05);">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid #E2E8F0;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:20px;">💬</span>
                    <span style="font-size:16px;font-weight:800;color:#0F172A;">{html.escape(qa.question)}</span>
                </div>
                <span style="background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;font-size:12px;font-weight:700;padding:4px 12px;border-radius:999px;">
                    {badge}
                </span>
            </div>

            {downgrade_note}

            <div style="font-size:15.5px;color:#1E293B;line-height:1.7;font-weight:500;margin:14px 0;">
                {html.escape(qa.answer)}
            </div>

            {evidence_html}
        </div>
    </div>
    """)


def render_transcription_html(result: AnalysisResult) -> str:
    """Produces the formatted transcription view for pack cross-checking."""
    raw_text = (result.extract.raw_transcription if result.extract else "") or "No text could be extracted."
    word_count = len(raw_text.split())

    return clean_html(f"""
    <div style="font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;padding:4px;">
        <div style="background:#FFFFFF;border:1.5px solid #E2E8F0;border-radius:14px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.03);">
            <div style="background:#F8FAFC;padding:12px 18px;border-bottom:1px solid #E2E8F0;display:flex;align-items:center;justify-content:space-between;">
                <span style="font-size:13px;font-weight:700;color:#475569;">Raw OCR / Pack Extraction ({word_count} words)</span>
                <span style="font-size:11.5px;color:#10B981;font-weight:600;">100% Verifiable</span>
            </div>
            <pre style="margin:0;padding:20px;font-family:'DM Mono', monospace;font-size:13px;color:#1E293B;line-height:1.6;white-space:pre-wrap;background:#FFFFFF;overflow-x:auto;">{html.escape(raw_text)}</pre>
        </div>
    </div>
    """)


# ---------------------------------------------------------------------------
# Backward-Compatible Markdown Renderers (For .md Report Download & CLI)
# ---------------------------------------------------------------------------

def _render_meta_footer(result: AnalysisResult) -> str:
    lines = [
        "---",
        DISCLAIMER_H10,
        f"\n*Mode: {result.backend_used} | Model: {result.model_used} | Processed in {result.seconds_taken:.1f} s*",
    ]
    return "\n".join(lines)


def render_summary(result: AnalysisResult) -> str:
    """Renders Markdown for the summary report."""
    if result.refused:
        return f"### 🚫 Analysis Refused\n{result.refusal_reason or 'This label cannot be analyzed.'}\n\n{_render_meta_footer(result)}"

    extract = result.extract
    summary = result.summary
    sections: list[str] = []

    prod_name = (extract.product_name if extract else None) or "Packaged Food"
    brand_str = f"by **{extract.brand}**" if (extract and extract.brand) else ""
    veg_icon = "🟢 **Vegetarian**" if (extract and extract.veg_mark == "veg") else (
        "🔴 **Non-Vegetarian**" if (extract and extract.veg_mark == "non_veg") else "⚪ **Veg/Non-Veg: Unknown**"
    )

    sections.append(f"## {prod_name} {brand_str}\n\n{veg_icon}\n")

    if summary:
        if summary.what_it_is:
            sections.append(f"### 📋 What it is\n{summary.what_it_is}\n")
        if summary.good_things:
            items = "\n".join(f"- {item}" for item in summary.good_things)
            sections.append(f"### 👍 Good Things\n{items}\n")
        if summary.watch_out:
            items = "\n".join(f"- {item}" for item in summary.watch_out)
            sections.append(f"### ⚠️ Things to Watch\n{items}\n")
        if summary.suits:
            items = "\n".join(f"- {item}" for item in summary.suits)
            sections.append(f"### 👤 Who it suits\n{items}\n")
        if summary.avoid_or_ask_doctor:
            items = "\n".join(f"- {item}" for item in summary.avoid_or_ask_doctor)
            sections.append(f"### 🩺 Who should avoid or ask a doctor\n{items}\n")
        if summary.overall_note:
            sections.append(f"### 💡 Overall Note\n{summary.overall_note}\n")

    if result.expiry:
        sections.append(f"**Expiry Status:** {result.expiry.explanation}\n")

    if result.verified_allergens:
        allergen_texts = ", ".join(f"**{a.text}**" for a in result.verified_allergens)
        sections.append(f"**⚠️ Allergen Notice:** {allergen_texts}\n")

    sections.append(_render_meta_footer(result))
    return "\n".join(sections)


def render_ingredient_rows(result: AnalysisResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for r in result.ratings:
        rating_display = RATING_ICONS.get(r.level, "⚪ Not rated")
        source_display = "Curated table" if r.source == "table" else "General knowledge"
        rows.append([r.name, rating_display, r.reason, source_display])
    return rows


def render_ingredients_table(result: AnalysisResult) -> str:
    if not result.ratings:
        return "No ingredients found on photographed panels."
    lines = [
        "### 🧪 Ingredient Breakdown & Health Ratings\n",
        "| Ingredient (from label) | Health Rating | Why | Source |",
        "|:---|:---|:---|:---|",
    ]
    for r in result.ratings:
        rating_display = RATING_ICONS.get(r.level, "⚪ Not rated")
        source_display = "Curated table" if r.source == "table" else "General knowledge"
        lines.append(f"| **{r.name}** | {rating_display} | {r.reason} | *{source_display}* |")
    lines.append("\n" + _render_meta_footer(result))
    return "\n".join(lines)


def render_nutrition(result: AnalysisResult) -> str:
    if not result.extract or not result.extract.nutrition:
        return "No nutrition information extracted from label."
    nut = result.extract.nutrition
    lines = [f"### 🥗 Nutrition Facts ({nut.basis.replace('_', ' ')})\n"]
    if nut.serving_size_text:
        lines.append(f"*Serving size: {nut.serving_size_text}*\n")
    if result.nutrition_flags:
        lines.append("#### Traffic Light Flags")
        for flag in result.nutrition_flags:
            badge_icon = "🔴 High" if flag.level == "high" else ("🟡 Medium" if flag.level == "medium" else "🟢 Low")
            lines.append(f"- **{flag.nutrient.title()}:** {badge_icon} ({flag.value:g} {flag.unit}) - *{flag.threshold_note}*")
        lines.append("")
    lines.append(_render_meta_footer(result))
    return "\n".join(lines)


def render_qa(result: AnalysisResult) -> str:
    if not result.qa:
        return "No question asked."
    qa = result.qa
    badge = QA_BADGES.get(qa.source, "❓ Cannot tell")
    lines = [
        f"### ❓ Question\n**{qa.question}**\n",
        f"**Source:** {badge}\n",
        f"### 💬 Answer\n{qa.answer}\n",
    ]
    if qa.evidence:
        lines.append("### 📄 Quoted Evidence from Label")
        for ev in qa.evidence:
            lines.append(f"> \"{ev}\"")
        lines.append("")
    lines.append(_render_meta_footer(result))
    return "\n".join(lines)


def render_report(result: AnalysisResult) -> str:
    """Generates a complete markdown report and writes it to a temporary file."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_filename = f"label_report_{timestamp}.md"
    target_dir = BASE_DIR
    target_file = target_dir / report_filename

    # Clean up old report files
    for old_file in glob.glob(str(target_dir / "label_report_*.md")):
        try:
            if Path(old_file) != target_file:
                os.remove(old_file)
        except Exception:
            pass

    content_parts = [
        f"# PARAKH Label Intelligence Report",
        f"*Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}*\n",
        render_summary(result),
        "\n## Ingredient Ratings Table\n",
        render_ingredients_table(result),
        "\n" + render_nutrition(result),
        "\n" + render_qa(result),
    ]

    if result.extract and result.extract.raw_transcription:
        content_parts.extend([
            "\n## Raw Transcription\n",
            "```text",
            result.extract.raw_transcription,
            "```",
        ])

    full_md = "\n".join(content_parts)
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(full_md)

    return str(target_file)
