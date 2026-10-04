# Architecture & Implementation Decisions

- **Dedicated Cloud AI Studio Engine**: Powered exclusively by Google AI Studio API with `gemma-4-26b-a4b-it` (Gemma 4 26B parameter model) for fast (~15-20s) and high-fidelity multimodal image comprehension.
- **Removed Local Ollama / Offline Fallback**: Transitioned fully to Google AI Studio API key architecture.
- **Expiry Reference Choice**: Month-only MFG/PKD date (e.g. 03/25) treats first of month as starting reference when adding duration.
- **Privacy & Security**: Zero disk retention of uploaded photos; label analysis processed strictly in-memory.
- **Logging Config**: Clean stream logging avoiding secrets/image bytes per section 6.
