# Google AI Studio Available Models

These models are active and available on the Google AI Studio OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`) for project `367534403742`.

---

## 1. Recommended for Smoke Testing & Tool Calling (Fast & High Quota)

These models have low latency and the highest token-per-minute throughput on the free tier:

| Model ID | Description | Recommended Usage |
| :--- | :--- | :--- |
| `gemini-2.5-flash-lite` | Ultra-fast lightweight model | Smoke testing, JSON extraction, low latency |
| `gemini-2.5-flash` | Stable, balanced multimodal model | Core agent loop, tool calling, fast reasoning |
| `gemini-flash-latest` | Rolling alias for latest stable Flash | Production routing |
| `gemini-flash-lite-latest` | Rolling alias for latest Flash-Lite | Production routing |
| `gemini-3.5-flash-lite` | Next-gen high-efficiency lightweight | Fast preview |
| `gemini-3.5-flash` | Next-gen general purpose Flash | Fast reasoning |

### Example Command
```powershell
python smoke_test.py --backend openai --models gemini-2.5-flash-lite --trials 1
```

---

## 2. High-Capability Reasoning Models (Pro Tier)

Higher capability and reasoning depth (note: more subject to rate limits on free tier):

| Model ID | Description |
| :--- | :--- |
| `gemini-2.5-pro` | Flagship complex reasoning and coding model |
| `gemini-pro-latest` | Rolling alias for latest stable Pro model |
| `gemini-3.1-pro-preview` | Enhanced reasoning and complex problem solving |
| `gemini-3.1-pro-preview-customtools` | Specialized preview optimized for complex custom tools |

---

## 3. Gemma Open-Weight Models

Open-weight instruction-tuned models hosted on Google AI Studio:

| Model ID | Description |
| :--- | :--- |
| `gemma-4-26b-a4b-it` | 26B instruction-tuned open weights |
| `gemma-4-31b-it` | 31B instruction-tuned open weights |

---

## 4. Next-Generation & Preview Models

| Model ID | Category |
| :--- | :--- |
| `gemini-3-flash-preview` | Generation 3 Flash preview |
| `gemini-3.1-flash-lite` | Generation 3.1 Flash-Lite |
| `gemini-3.1-flash-lite-preview` | Generation 3.1 Flash-Lite preview |
| `gemini-3.6-flash` | Generation 3.6 Flash |
| `gemini-3.7-flash` | Generation 3.7 Flash |
| `gemini-3.8-flash` | Generation 3.8 Flash preview |
| `gemini-4-argon` | Experimental architecture |
| `gemini-omni-flash-preview` | Omni-modal Flash preview |
| `gemini-omni-1.1-flash` | Omni-modal v1.1 Flash |
| `gemini-nano-banana-2.1` | Compact edge preview |
| `nano-banana-pro-preview` | High-efficiency edge Pro preview |

---

## 5. Research & Specialized Agent Models

| Model ID | Specialized Task |
| :--- | :--- |
| `deep-research-preview-04-2026` | Autonomous multi-step deep research agent |
| `deep-research-pro-preview-12-2025` | Deep research Pro tier |
| `deep-research-max-preview-04-2026` | Deep research maximum compute |
| `antigravity-preview-latest` | Antigravity agentic preview |
| `antigravity-preview-09-2026` | Antigravity snapshot |
| `antigravity-preview-05-2026` | Antigravity snapshot |
| `gemini-2.5-computer-use-preview-10-2025` | OS/Desktop UI automation and computer use |
| `gemini-robotics-er-2-preview` | Embodied reasoning and robotics |
| `gemini-robotics-er-2-streaming-preview` | Real-time robotics streaming |

---

## 6. Audio, Speech & Multimodal Models

| Model ID | Functionality |
| :--- | :--- |
| `gemini-2.5-flash-image` | Flash image understanding and generation |
| `gemini-3-pro-image` | High-fidelity image processing |
| `gemini-3.1-flash-image` | Fast image processing |
| `gemini-3.5-transcribe` | High-accuracy speech transcription |
| `gemini-3.5-transcribe-live` | Real-time live audio transcription |
| `gemini-2.5-flash-preview-tts` | Text-to-speech audio synthesis |
| `gemini-3.8-flash-tts` | Text-to-speech audio synthesis |
| `gemini-3.8-live` | Real-time bidirectional live speech |
| `gemini-3.8-live-extended-thinking` | Real-time bidirectional speech with reasoning |
| `lyria-3.5` / `lyria-realtime-exp` | Music & audio generation |
| `gemini-embedding-2` | Text and multimodal embeddings |
