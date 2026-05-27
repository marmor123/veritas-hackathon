# FOR TEAMMATES — Everything You Need to Know

## Why This Project Is Worth Your Time

Here's the situation. 200 million people get blood tests every year. When results come back, they see something like this:

```
GLUCOSE     102 mg/dL    H     (70-100)
CHOLESTEROL 228 mg/dL    H     (<200)
HDL          36 mg/dL    L     (>40)
TRIGLYCERIDES 198 mg/dL  H     (<150)
ALT          48 U/L      H     (<35)
URIC ACID    7.4 mg/dL   H     (3.5-7.2)
```

A consumer app sees these and generates six separate "Something is wrong!" alerts. The user panics. They Google each one. They end up in a WebMD spiral, convinced they have three different diseases.

**The reality:** This isn't six separate problems. It's one pattern — metabolic syndrome. The underlying issue is insulin resistance. Everything else is a downstream effect of the same root cause.

**Our innovation:** We don't just explain individual markers. We verify whether the results are trustworthy (drug interference? collection error?), identify clinical patterns (parent-child correlation), assign real urgency (Warning/Caution/Advisory — not everything is equally red), and cite our sources so every claim is traceable to established medical literature.

**The core metaphor:** A blood test is a sensor network from an industrial system (your body). Current apps treat it like a report card with red ink. We treat it like a control room — analyzing sensor data, suppressing false alarms, correlating events, and escalating only what actually matters.

**The hackathon pitch in one sentence:** We applied industrial alarm management to human biology, so you stop getting 40 alerts and start understanding what's actually happening.

---

## 1. What You're Actually Building

You upload a blood test PDF. The system:

```
[PDF drops]
    │
    ├─→ "Reading your report..."           (OCR: your code)
    ├─→ "Checking if results are reliable" (Verification: your code)
    ├─→ "Matching against clinical knowledge" (RAG: your code)
    ├─→ "Generating your summary..."       (LLM: your prompt)
    │
    ▼
[3 pattern cards, not 40 red alerts]
[+ specific questions for your doctor visit]
```

Every module is **your code** + **deterministic rules from medical textbooks** + **a small local LLM that runs on a laptop**. Nothing goes to the cloud. Nothing is a black box.

### The Secret Weapon: The Question Generator

Most apps stop at "here's what's happening." We add **"here's what to ask your doctor about it."**

For every clinical pattern identified, the LLM generates 2-3 specific, actionable questions. Not generic "ask your doctor about your iron" — actual, well-formed clinical questions:

- *"My ferritin is 12 ng/mL — at what level would you recommend iron supplementation and what formulation?"*
- *"My resting heart rate has trended up from 68 to 76 bpm over the past month — is this related to my low hemoglobin?"*
- *"Should we investigate the cause of my iron deficiency — diet, absorption, or blood loss?"*

This bridges the gap between "I see something is off" and "I know what to do about it." Oracle is adding this to hospital patient portals in 2026. **No consumer app has it.**

---

## 2. The Medical Stuff, Translated

### Blood Test = Sensor Array

A blood test measures 30-40 substances in your blood. Each one is a **biomarker** — a sensor reading from a specific biological system.

| Panel | What It Measures | Like Monitoring... |
|---|---|---|
| **CBC** | Red/white blood cells, platelets, hemoglobin, MCV | System health — CPU load, memory usage |
| **CMP** | Glucose, electrolytes, kidney values, liver enzymes | Resource utilization — power draw, thermal sensors |
| **Lipids** | Cholesterol, HDL, LDL, triglycerides | Network throughput — bandwidth, packet loss |
| **Thyroid** | TSH, T3, T4 | Clock signal — everything's timing depends on this |
| **Iron Panel** | Ferritin, serum iron, transferrin, saturation | Resource reserves — cache levels, buffer capacity |

### Patterns > Individual Values

One bad sensor reading might be noise. Five related bad readings pointing in the same direction? That's a **clinical pattern**. The underlying cause (root cause) explains all the effects (child events).

**Real example:** Iron deficiency cascade
```
Root cause: Low ferritin (12 ng/mL)        ← iron storage tanks empty
    └─→ Low serum iron (35 µg/dL)          ← not enough iron in circulation
        └─→ Low MCV (78 fL)                ← red blood cells are getting smaller
            └─→ Low hemoglobin (11.2 g/dL) ← anemia — less oxygen capacity
                └─→ Resting HR trending ↑  ← heart compensating (wearable data!)
```

5 abnormal markers. 1 root cause. Our app shows **one pattern card**, not five panicked alerts.

### RAG = The LLM Can't Make Things Up

Our LLM (a small 1.7B model running locally) doesn't generate medical opinions from its training data. Our retrieval pipeline has 5 stages — this is state-of-the-art RAG, not a naive vector search:

1. **Query rewriting** — Before searching, the LLM transforms `"ferritin 12, MCV 78, Hb 11.2"` into a clinical query: `"Microcytic anemia pattern with depleted iron stores — differential: iron deficiency vs. ACD vs. thalassemia."` This framing dramatically improves what we find.
2. **Metadata-filtered search** — We only search chunks from relevant organ systems. An iron problem doesn't waste time searching thyroid or liver chapters. LanceDB filters before vector search.
3. **Cross-encoder re-ranking** — A small second model (~90MB) reads each (query, chunk) pair and directly scores relevance. Much more accurate than embedding similarity alone.
4. **Citation tracking** — Every chunk carries immutable source metadata (Wallach chapter, page).
5. **LLM synthesis** — The LLM receives the top-5 most relevant chunks and synthesizes an explanation citing each source.

The comparison to naive approaches:

| Naive RAG (what most apps would do) | Our RAG |
|---|---|
| Embed raw biomarker names → search → hope | Rewrite into clinical query → filter by organ system → hybrid search → cross-encoder re-rank → synthesize with citations |
| LLM sees low ferritin → generates plausible-sounding explanation from training data | LLM sees low ferritin → we retrieve Wallach's chapter on iron deficiency → LLM synthesizes "Wallach states that..." |
| "You may have iron deficiency anemia" | "Your pattern of low ferritin + low MCV + low hemoglobin is consistent with iron deficiency as described in Wallach's Interpretation of Diagnostic Tests, Ch. 3" |
| No way to verify the claim | Every claim has a citation you can trace |

The LLM is a **synthesis engine**, not an oracle. And our retrieval is smart enough to find the right chapter even when the user's biomarker names don't exactly match the textbook terminology.

### The Cross-Industry Framework (Our "Edge")

Healthcare has an alert fatigue crisis — too many alarms, not enough context. Three other industries solved this decades ago:

| Industry | Problem They Solved | What We Stole |
|---|---|---|
| **SIEM** (cybersecurity) | Millions of network events per day → analysts drowning | Event correlation: don't fire 40 alerts, find the attack chain. *We find the clinical pattern.* |
| **SCADA** (industrial control) | One pump failure triggers 50 downstream alarms | Parent-child suppression: show the root cause, not the cascade. *We group biomarkers under their root physiological cause.* |
| **Aviation** (cockpit design) | Pilots overwhelmed by simultaneous warnings | Warning/Caution/Advisory hierarchy. *Not everything is equally urgent. Critical potassium = Warning. Low Vitamin D = Advisory.* |

This is genuinely novel. No consumer health app has organized its alert system this way.

---

## 3. The Six Modules (What Goes Where)

```
                        ┌─────────────────────────┐
    [Blood Test PDF] ──→│  MODULE 1: OCR Pipeline  │  CV + regex
                        │  PDF → structured JSON   │  1 person
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  MODULE 2: Context       │  UI forms + wearable API
                        │  Meds, supplements,      │  1 person
                        │  smartwatch data         │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  MODULE 3: Verification  │  Rules engine
                        │  Error detection, drug   │  Med student + 1 CS
                        │  interference, plausibility│
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  MODULE 4: RAG Engine    │  Vector DB + embeddings
                        │  Retrieve clinical       │  2 people
                        │  patterns from Wallach   │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  MODULE 5: LLM Synthesis │  Prompt engineering
                        │  Pattern grouping +      │  1 person
                        │  severity + citations    │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  MODULE 6: Dashboard     │  React + D3.js
                        │  Pattern cards, network  │  2 people
                        │  graph, doctor questions │
                        └─────────────────────────┘
```

**You don't need medical knowledge for any of this.** The rules are encoded in lookup tables. The knowledge is in the vector database. The LLM handles explanation. You're building pipelines, APIs, prompts, and UI components.

---

## 4. Your Tech Stack (One Sentence Each)

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Tailwind | You already know this |
| Visualization | D3.js | Full control over the network graph |
| Backend | Python FastAPI | Lightweight, auto-generated docs, strong typing via Pydantic |
| OCR | Tesseract (local) | No cloud needed, English + Hebrew support |
| Vector DB | LanceDB | Embedded — no separate server, runs in-process |
| Embeddings | all-MiniLM-L6-v2 | Small, fast, good enough for medical text retrieval |
| LLM | QVAC MedPsy 1.7B (GGUF via Ollama) | Medical-specific, ~1.2GB RAM, runs on any laptop |
| Storage | SQLite | Zero configuration, embedded |
| Wearable | Apple HealthKit / Google Health Connect | Standard APIs, mock data fallback |

---

## 5. What You DON'T Need to Know

- **Clinical accuracy** — the medical student validates outputs and tunes severity assignments
- **Medical terminology** — you need pattern names and biomarker lists, not pathophysiology
- **Regulatory compliance** — hackathon scope; every screen says "discuss with your doctor"
- **Whether ferritin should be high or low** — the knowledge base stores that; your job is retrieval quality
- **What "microcytic hypochromic anemia" means** — the LLM translates it to "small, pale red blood cells from low iron"

---

## 6. The Demo Scenarios We'll Show

### Scenario A: "The Five-Alert Problem, Solved"
**Input:** Metabolic syndrome blood panel (6 abnormal values)
**What happens:** System groups all 6 into one "Metabolic Pattern" card with CAUTION severity
**The pitch:** "A normal app gives you 6 reasons to panic. We give you 1 thing to discuss with your doctor."

### Scenario B: "Your Watch Already Knows"
**Input:** Iron deficiency panel + smartwatch data showing rising resting heart rate
**What happens:** Pattern card shows "potentially symptomatic" tag — the deficiency is already affecting daily physiology. Card expands to reveal 3 specific questions for the doctor visit, including: *"Is my rising resting heart rate (68→76 bpm) related to my low hemoglobin, and at what hemoglobin level would you recommend iron supplementation?"*
**The pitch:** "We don't just tell you what's happening — we tell you what to ask your doctor about it."

### Scenario C: "Your Supplement Is Lying to You"
**Input:** Abnormal thyroid panel + user checked "Biotin supplement"
**What happens:** System flags drug interference BEFORE interpreting the thyroid result as a problem
**The pitch:** "We verify results before we explain them. Biotin makes thyroid tests lie."

### Scenario D: "This Result Is Probably Wrong"
**Input:** Very high potassium with completely normal kidney function
**What happens:** System detects physiological inconsistency, suggests possible hemolysis artifact
**The pitch:** "Sometimes the most important insight is: this result might not be real."

---

## 7. Severity Colors (Use These Everywhere)

```
🔴 WARNING  #DC2626  — Needs urgent medical attention (hours-days)
🟡 CAUTION  #D97706  — Needs follow-up (days-weeks)
🔵 ADVISORY #2563EB  — Lifestyle awareness (weeks-months)
🟢 NORMAL   #16A34A  — In range, nothing to do
```

**Rule:** If everything is red, nothing is. Most results should be blue or green. Red is reserved for genuinely dangerous values.

---

## 8. FAQ

**Q: Why local AI instead of calling GPT-4?**
A: Privacy is the feature. "Your blood test never leaves your device" is a powerful claim judges understand. Also, a 1.7B medical-specific model now matches GPT-4 on clinical benchmarks — the tech is ready.

**Q: What if the local LLM is too slow?**
A: It won't be. QVAC MedPsy 1.7B runs at ~22 tokens/sec on laptop hardware. A full synthesis takes 10-15 seconds. For a hackathon demo, that's fast enough.

**Q: What if we don't have Wallach's book?**
A: We need excerpts for the knowledge base. The medical student handles sourcing. For the demo, we need ~30 clinical pattern descriptions covering the most common blood test findings.

**Q: What if the wearable API is a pain?**
A: Mock data fallback. We pre-generate realistic 30-day datasets for our demo scenarios. The real API integration is bonus points.

**Q: Which module should I pick?**
A: Frontend person → Module 6 (Dashboard). Backend/ML person → Module 4 (RAG). CV/regex person → Module 1 (OCR). Full-stack → Module 2 + 3. Prompt engineer → Module 5.

---

## 9. The One Thing to Remember

We're not building a blood test explainer. There are 20 of those. We're building a **verification and correlation engine** that applies industrial alarm management to human biology. The pitch isn't "we explain your labs nicely." The pitch is **"current blood test apps are lying to you by treating every abnormal value as an independent crisis. We verify, correlate, and prioritize — so you know what actually matters."**
