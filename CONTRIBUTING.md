# Contributing to PARAKH

Thank you for your interest in contributing! 🙏

## Quick Start for Contributors

```bash
git clone https://github.com/priyanshujaiswal17/PARAKH.git
cd PARAKH
python -m venv .venv && source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Add your Google AI Studio key
```

## Running Tests Before You Submit

Always run the full test suite before opening a PR:

```bash
pytest -v
```

All 72 tests must pass.

## Types of Contributions Welcome

| Area | Examples |
|---|---|
| 🐛 Bug fixes | Incorrect expiry parsing, wrong nutrition thresholds |
| 🧪 New tests | Edge cases for expiry dates, new product types |
| 📊 Additives database | Adding/correcting entries in `data/additives.json` |
| 🌐 Languages | Adding regional language support beyond English/Hinglish |
| 🎨 UI improvements | CSS, layout, accessibility |

## Honesty Rules — Don't Break Them

PARAKH's core promise is **honest, grounded analysis**. Do not modify code in a way that:

- Allows ingredient hallucinations to pass validation
- Weakens the medicine/non-food rejection guard
- Permits absolute safety claims ("100% safe", "cures X")
- Stores user-uploaded images to disk

## Code Style

- Follow existing code style (PEP 8 compatible)
- Keep functions focused and testable
- Add a test for any new pipeline logic

## Pull Request Checklist

- [ ] `pytest -v` passes (all 72+ tests green)
- [ ] New tests added for new logic
- [ ] `data/additives.json` entries include a `source` field
- [ ] No `.env` or API keys committed
- [ ] PR description explains *why* the change is needed
