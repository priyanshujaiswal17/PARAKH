<p align="center">
  <img src="https://img.shields.io/badge/Powered%20by-Gemma%204%20%2826B%29-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Built%20with-Gradio%206-F97316?style=for-the-badge&logo=gradio&logoColor=white" />
  <img src="https://img.shields.io/badge/Language-Python%203.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-72%20passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-94A3B8?style=for-the-badge" />
</p>

<h1 align="center">🏷️ PARAKH (परख)</h1>
<h3 align="center">Food Safety & Nutrition Intelligence for India</h3>

<p align="center">
  <strong>Snap any Indian packaged food label — get an honest, AI-powered health audit in under 30 seconds.</strong><br/>
  Powered by <strong>Gemma 4 (26B)</strong> via Google AI Studio · Supports <strong>English</strong> &amp; <strong>Hinglish</strong><br/>
  <em>100% private · in-memory processing · no data stored</em>
</p>

---

## ✨ What Is PARAKH?

**PARAKH** (Hindi: परख, meaning *"to scrutinise"*) is an open-source, privacy-first food label intelligence system built specifically for India's packaged food ecosystem.

Upload 1–3 photos of any food package and within 30 seconds you receive:

| Feature | What you get |
|---|---|
| 🧪 **Ingredient Audit** | Every ingredient rated Good / Moderate / Avoid with evidence |
| 🥗 **Nutrition Traffic Lights** | Sugar, salt, fat graded against UK FSA reference thresholds |
| 📅 **Expiry Verification** | Deterministic Python expiry calculation with days-remaining countdown |
| 🌱 **Veg / Non-Veg** | FSSAI mark detection (green circle / red/brown triangle) |
| ✅ **Claim Verification** | Manufacturer claims cross-checked against actual label text |
| 💬 **Q&A** | Ask anything — "Safe during pregnancy?", "Contains palm oil?" |
| 📄 **Report Download** | Full Markdown health report downloadable in one click |

---

## 🖼️ Screenshots

> Upload a food label photo → get a full structured health breakdown in seconds.

```
┌─────────────────────────────────────────────────────────┐
│  📸 Upload Packaging Photos                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Front Panel (Required)  [height=180px preview]  │   │
│  └─────────────────────────────────────────────────┘   │
│  ✅ Photo 1 Uploaded (3024×4032px) · Ready for AI Scan  │
│                                                         │
│  [ 🔍 Analyze Food Label ]   [ ✕ Clear All ]           │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

```
[ Label Photos (1–3) ]
         │
         ▼
 1. Preprocess          ─ EXIF strip, orientation fix, Lanczos resize,
                          sharpness detection, blur enhancement
         │
         ▼
 2. Vision Extraction   ─ Gemma 4 transcribes raw text, nutrition,
                          dates, veg mark, claims (structured JSON)
         │
         ▼
 3. Safety Guards       ─ Refuse medicines / non-food items;
                          advisory notice for blurry / partial labels
         │
         ▼
 4. Honesty Validation  ─ Fuzzy-match every ingredient against raw
                          label text (RapidFuzz ≥ 70%); drop hallucinations
         │
         ▼
 5. Deterministic Logic ─ Pure-Python expiry date math;
                          FSA nutrition threshold evaluation
         │
         ▼
 6. Ingredient Ratings  ─ Curated additives.json table lookup
                          + Gemma 4 fallback rating
         │
         ▼
 7. Summary Generation  ─ Structured explanation in English or Hinglish
         │
         ▼
 8. Grounded Q&A        ─ Evidence-cited answers; ungrounded claims
                          downgraded to "general knowledge"
         │
         ▼
 9. Safety Filter       ─ Strip absolute claims ("100% safe", "cures X")
         │
         ▼
10. Render & Export     ─ Tabbed UI (Overview, Ingredients, Nutrition,
                          Q&A, Raw Text) + Markdown report download
```

---

## 🛡️ Honesty Rules (Enforced by Code)

Honesty is the product. Every rule is enforced programmatically — not just prompted.

| # | Rule | Description | Module |
|---|---|---|---|
| H1 | **Ingredient Verification** | Every ingredient fuzz-verified against raw label text; hallucinations dropped | `pipeline/validate.py` |
| H2 | **Source Attribution** | Ratings cite `table` (curated DB) or `general_knowledge` (model fallback) | `pipeline/ratings.py` |
| H3 | **No Absolute Safety Claims** | "100% safe", "cures", "no side effects" stripped programmatically | `pipeline/safety_filter.py` |
| H4 | **Unclear Text Handling** | Illegible text tagged `[unclear]`; guessing prohibited | `prompts/extract.txt` |
| H5 | **Medicine Refusal** | Indian pharma keyword scoring refuses medicine labels | `pipeline/guards.py` |
| H6 | **Deterministic Expiry** | Expiry dates computed with pure Python `dateutil` math | `pipeline/expiry.py` |
| H7 | **Nutrition Traffic Lights** | High/Medium/Low flags computed against UK FSA reference values | `pipeline/nutrition.py` |
| H8 | **Grounded Q&A** | Answers cite verbatim label evidence; ungrounded claims downgraded | `pipeline/qa.py` |
| H9 | **Prompt-Injection Defence** | Label text sandboxed in `<label_text>` tags; printed instructions ignored | `pipeline/validate.py` |
| H10 | **Medical Disclaimer** | Mandatory disclaimer on every result and downloaded report | `pipeline/render.py` |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- A free **[Google AI Studio](https://aistudio.google.com/)** API key

### 1 · Clone & Install

```bash
git clone https://github.com/priyanshujaiswal17/PARAKH.git
cd PARAKH

python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2 · Configure API Key

```bash
cp .env.example .env
```

Open `.env` and set your key:

```env
GEMINI_API_KEY=your_google_ai_studio_api_key_here
GEMINI_MODEL=gemma-4-26b-a4b-it
APP_HOST=127.0.0.1
APP_PORT=8000
```

> **Get a free key** at https://aistudio.google.com/ — no credit card required for Gemma 4 access.

### 3 · Launch

```bash
# Windows (one-click)
run.bat

# macOS / Linux (one-click)
chmod +x run.sh && ./run.sh

# Manual
python app.py
```

Open **http://127.0.0.1:8000** in your browser. 🎉

---

## 📁 Repository Structure

```
PARAKH/
├── app.py                  # Gradio web application (UI + event bindings)
├── config.py               # Settings loader (dotenv → frozen dataclass)
├── llm.py                  # Google AI Studio / Gemma 4 client wrapper
│
├── pipeline/               # Core processing pipeline
│   ├── models.py           # Pydantic data models (ExtractResult, etc.)
│   ├── preprocess.py       # Image preprocessing, blur detection & enhancement
│   ├── extract.py          # Vision extraction (Gemma 4 → structured JSON)
│   ├── guards.py           # Safety guards (medicine refusal, non-food gate)
│   ├── validate.py         # Honesty validation (fuzzy-match, hallucination removal)
│   ├── expiry.py           # Deterministic Indian date-format expiry parser
│   ├── nutrition.py        # FSA nutrition traffic light evaluation
│   ├── ingredients.py      # Ingredient data helpers
│   ├── ratings.py          # Additive/ingredient rating engine
│   ├── qa.py               # Grounded Q&A with evidence citation
│   ├── explain.py          # Natural language explanation generator
│   ├── safety_filter.py    # Post-generation safety content filter
│   ├── run.py              # Orchestrator: ties all pipeline steps together
│   └── render.py           # HTML rendering for Gradio tabs + Markdown report
│
├── prompts/                # Gemma 4 prompt templates
│   ├── extract.txt         # Vision extraction & OCR prompt
│   ├── explain_en.txt      # English explanation prompt
│   ├── explain_hinglish.txt# Hinglish (Roman-script Hindi) prompt
│   ├── qa.txt              # Grounded Q&A prompt
│   └── ratings_fallback.txt# Ingredient rating fallback prompt
│
├── data/                   # Curated reference data
│   └── additives.json      # ∼300 Indian food additives with ratings & evidence
│
├── tests/                  # Test suite (72 tests, all passing)
│   ├── test_expiry.py      # 27 expiry date parsing scenarios
│   ├── test_guards.py      # 12 medicine/non-food guard tests
│   ├── test_ingredients.py # 7 ingredient parsing tests
│   ├── test_nutrition.py   # 9 FSA traffic light tests
│   ├── test_ratings.py     # 6 additive rating tests
│   ├── test_safety_filter.py # 4 safety filter tests
│   ├── test_validate.py    # 7 fuzzy validation tests
│   ├── eval.py             # Golden set evaluation runner
│   └── golden/             # Benchmark label images & expected outputs
│
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── pytest.ini              # Pytest configuration
├── run.bat                 # Windows one-click launcher
├── run.sh                  # macOS/Linux one-click launcher
├── DESIGN_SYSTEM.md        # UI/UX design tokens & component guide
└── DECISIONS.md            # Architecture decision log
```

---

## 🧪 Testing

```bash
# Run the full unit test suite (72 tests)
pytest -v

# Run golden-set evaluation on benchmark label images
python -m tests.eval --backend gemini --dir tests/golden
```

Test coverage includes:
- **27** Indian date-format expiry parsing scenarios (DD/MM/YY, MM/YY, "Best Before 6 months from MFG", etc.)
- **12** medicine/non-food label guard scenarios
- **9** FSA nutrition traffic light threshold tests
- **7** fuzzy validation & hallucination-removal tests
- **4** safety filter (absolute claim removal) tests

---

## 🔒 Privacy by Design

| Guarantee | Implementation |
|---|---|
| **Zero disk storage** | Images processed in-memory with Pillow; never written to disk or DB |
| **EXIF scrubbing** | GPS, device model, timestamp metadata stripped during preprocessing |
| **No accounts / tracking** | No cookies, sessions, logins, or telemetry |
| **Key isolation** | API key loaded from `.env` (excluded from git); optional UI override |

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| AI Model | **Gemma 4 26B** (`gemma-4-26b-a4b-it`) via Google AI Studio API |
| Python SDK | `google-genai` ≥ 1.0 |
| Web UI | **Gradio** ≥ 6.0 with custom CSS (emerald design system) |
| Image Processing | **Pillow** + NumPy (deblur, EXIF strip, Lanczos resize) |
| Fuzzy Validation | **RapidFuzz** ≥ 3.6 |
| Data Validation | **Pydantic** v2 |
| HTTP Client | **httpx** |
| Date Parsing | **python-dateutil** |
| Testing | **pytest** |

---

## 🌐 Languages Supported

| Language | Description |
|---|---|
| **English** | Full clinical-grade detail — ingredient science, nutrition analysis, claim verification |
| **Hinglish** | Roman-script Hindi + English hybrid — colloquial, accessible for everyday Indian users |

---

## ⚠️ Limitations

- **Image Quality:** Severe motion blur, flash glare, or very low resolution may produce `[unclear]` tags. Use the multi-panel upload (optional accordion) for blurry packaging.
- **Scope:** Designed for **Indian packaged foods** under FSSAI. Non-food items, medicines, and bills are rejected.
- **Nutrition Reference:** FSA traffic lights are an informative guide; they are not FSSAI statutory grades.
- **Response Time:** Typically 15–30 seconds depending on Google AI Studio API load.

---

## 🤖 AI Disclosure

```
AI tools used in building PARAKH:
  • Gemma 4 (runtime, inside the product) — reads label images, generates summaries
  • Antigravity / Gemini (coding assistant) — implemented Python codebase, pipeline modules,
    unit tests, and Gradio interface

Manually authored by the team:
  • Strict fuzzy validation engine (pipeline/validate.py)
  • Indian date-format expiry parser (pipeline/expiry.py)
  • Curated additive database (data/additives.json, ~300 entries)
  • Deterministic nutrition evaluation (pipeline/nutrition.py)
  • All 72 unit tests
```

---

## 📄 License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for Indian consumers · FSSAI-aware · Privacy-first<br/>
  <a href="http://127.0.0.1:8000">Try locally</a> ·
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-repository-structure">Project Structure</a>
</p>
