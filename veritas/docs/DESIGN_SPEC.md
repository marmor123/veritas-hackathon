# DESIGN SPEC — UI Requirements for VERITAS

## What We're Building (One Paragraph)

A blood test analyzer that takes a PDF upload, verifies the results, identifies clinical patterns, and displays them as severity-ranked cards with citations and doctor questions. The core UX principle: don't show 40 red alerts in a table. Show 3-5 pattern cards with real urgency levels. Everything runs on-device. Every screen says "this is not a diagnosis."

---

## User Flow

```
UPLOAD PAGE                    DASHBOARD (progressive)
────────────                   ────────────────────────
                               
[Drag PDF here]                [Summary statement]
       │                              │
       ▼                              ▼
[OCR results appear]            [Pattern cards]
  "We found 35 biomarkers"        sorted by severity
       │                              │
       ▼                              ▼
[Optional: Add context]         [Verification alerts]
  Meds checklist                  (if any flags)
  Connect wearable                   │
       │                              ▼
       ▼                         [Doctor questions]
[Click "Analyze"]                    │
       │                              ▼
       ▼                         [View all biomarkers]
[Dashboard loads                  (expandable table)
 progressively]                      │
       │                              ▼
       ▼                         [Disclaimer footer]
[Demo button always
 visible in header]

[Clear Data button
 always visible in header]
```

**Key flow constraint:** The user uploads a PDF and sees OCR results within ~5 seconds. Everything after that (medications, wearable, analysis) is optional enhancement. The user should never feel blocked.

---

## Page 1: Upload

### Purpose
Get a blood test PDF into the system and show immediate value (extracted biomarkers). Collect optional context.

### Required Elements

| Element | Description | States |
|---|---|---|
| **Drop zone** | Large, obvious. Accepts PDF and images (phone photo of a printout). "Drag your blood test report here or click to browse." | Default, drag-over (highlighted border), processing (spinner + "Reading your report...") |
| **Mobile camera button** | "Or take a photo." Opens device camera. | Default, disabled (desktop without camera) |
| **OCR results panel** | Appears after OCR completes (~5s). Shows: number of biomarkers found, a mini-table of key results (top 5-8 most important ones), parse confidence indicator, and any validation warnings ("3 biomarker names couldn't be recognized — please verify"). | Hidden (before upload), loading (during OCR), populated, warning (low confidence or unrecognized names), error ("Couldn't read this report. Try a clearer photo.") |
| **Context panel** | Appears after OCR results. "Enhance your analysis (optional)." Contains medication checklist and wearable connect button. Can be skipped entirely. | Hidden, expanded, collapsed |
| **Medication checklist** | Searchable list of common drugs/supplements that interfere with blood tests. Grouped by category (Supplements, Prescription). Free-text "other medications" field at bottom. | Empty, partially filled, fully filled |
| **Wearable connect** | Button: "Connect Apple Health" or "Connect Google Fit." Shows last sync date if connected. | Disconnected, connecting, connected (shows data summary), error ("Couldn't access health data") |
| **Analyze button** | "Analyze Results." Triggers verification + RAG + LLM pipeline. | Enabled (file uploaded), disabled (no file), loading (pipeline running — shows stage progress) |
| **Progress indicator** | Shows pipeline stages as they complete: "Reading report... ✓" → "Checking for errors... ◌" → "Identifying patterns... ◌" → "Generating insights... ◌" | Hidden (before analysis), visible (during pipeline) |

### Header Elements (Always Visible)
| Element | Description |
|---|---|
| **Demo button** | "View Example" — dropdown with 5 scenarios. Loads pre-cached analysis instantly. |
| **Clear Data** | Trash icon. "Delete all uploaded reports and analysis results." Confirmation dialog. |

### States
- **Fresh:** Drop zone prominent. Demo button visible for curious users.
- **After upload, before OCR:** Drop zone replaced by progress spinner.
- **After OCR, before analysis:** Results panel visible. Context panel available. Analyze button enabled.
- **During analysis:** Progress indicator shows pipeline stages completing.
- **Error:** Clear error message with actionable suggestion ("Try a clearer photo," "This format may not be supported").

---

## Page 2: Dashboard (Progressive)

### Purpose
Show analysis results. NOT a table of 40 biomarkers. Pattern cards first, details on demand.

### Progressive Loading Behavior
The dashboard populates as each pipeline stage completes:
1. After OCR: biomarker summary visible
2. After Verification: verification alerts appear (if any)
3. After RAG+LLM: pattern cards appear, summary statement appears, doctor questions appear
4. Each section animates in smoothly — not a jarring full-page refresh

### Required Elements (Top to Bottom)

#### 2a. Summary Statement
| Attribute | Detail |
|---|---|
| **Content** | 1-2 sentences. Overall assessment. "Your blood test shows a pattern consistent with low iron stores. Your smartwatch data suggests this may already be affecting your resting heart rate." |
| **States** | Hidden (before analysis completes), populated, "All results in normal range" (green, positive tone) |

#### 2b. Pattern Cards (Primary Content)
| Attribute | Detail |
|---|---|
| **Quantity** | 0 (all normal) to ~5 patterns. Most cases: 1-3. |
| **Sort order** | WARNINGs first, then CAUTIONs, then ADVISORIES. Within same severity: higher confidence first. |
| **Collapsed state** | Pattern name (patient-friendly: "Low Iron Pattern"), severity badge (color + icon + label), confidence pill ("High Confidence"), "Symptomatic" tag if wearable data corroborates, expand chevron. |
| **Expanded state** | Plain-language explanation (2-3 sentences), list of supporting biomarkers with values and mini bar charts showing where they fall in reference range, source citations (expandable accordion — "Wallach's Interpretation of Diagnostic Tests, Chapter 3: Anemia"), doctor questions (see 2c), "What affects this" note (medication interferences, lifestyle factors). |
| **Edge cases** | Single abnormal biomarker with no pattern match → show as "Isolated Finding" card with ADVISORY severity. No patterns at all → show green "All Clear" card. |

#### 2c. Doctor Questions (Per Pattern)
| Attribute | Detail |
|---|---|
| **Content** | 2-3 specific, actionable questions the user should ask their doctor. "Based on my ferritin of 12 ng/mL, what iron supplementation strategy would you recommend?" NOT generic "ask your doctor about iron." |
| **Interactions** | Each question has a copy button (clipboard). "Copy All Questions" button copies all questions from all patterns. |
| **States** | Populated (2-3 questions), missing (graceful: no questions section shown) |

#### 2d. Verification Alerts
| Attribute | Detail |
|---|---|
| **When shown** | Only if there are quality flags (hemolysis, drug interference, physiological implausibility). |
| **Tone** | Warning — amber/yellow. Not alarming. Informative. |
| **Content per alert** | Type icon (blood drop for hemolysis, pill for drug, scale for plausibility), human-readable description, specific recommendation. |
| **Placement** | Above pattern cards if results may be unreliable. Below pattern cards if flags are minor. |
| **Edge case** | Multiple alerts → stacked. No alerts → section not rendered at all. |

#### 2e. View All Biomarkers (Expandable)
| Attribute | Detail |
|---|---|
| **Content** | Full table of all extracted biomarkers: name, value, unit, reference range, flag (H/L/none), verification status (flagged or clean). Sorted by organ system groups with section headers (Hematologic, Metabolic, Hepatic, etc.). |
| **Default state** | Collapsed. "View All 35 Biomarkers" button. Most users won't need this — power users and the curious will expand. |
| **Expanded state** | Full table. Green/amber/red color coding on values. Flagged biomarkers highlighted. |

#### 2f. Disclaimer Footer
| Attribute | Detail |
|---|---|
| **Content** | "This is not a medical diagnosis. All identified patterns should be discussed with a qualified healthcare provider. This tool provides educational information only." |
| **Placement** | Bottom of every page that shows clinical content. Always visible (not hidden behind a scroll). |

### States
- **Pipeline running:** Sections appear progressively. Spinner/skeleton on sections not yet completed.
- **All normal:** Green summary. No pattern cards. No alerts. "All results in normal range. No clinical patterns detected." Biomarker table available if user wants to see raw values.
- **Patterns found:** Full dashboard with all sections.
- **Verification issues:** Alerts prominent. Patterns still shown but with caveat: "Some results may be unreliable. Review flagged items before discussing patterns with your doctor."
- **Partial failure:** If a pipeline stage fails, show what's available with a clear note about what couldn't be completed. E.g., "Analysis could not be completed. Here are your verified biomarker results to discuss with your doctor."

---

## Page 3: Pattern Detail (Could Be a Modal or Expand)

### Purpose
Deep dive into a single pattern. Full explanation, all citations, all related biomarkers.

### Required Elements
- Pattern name and severity badge
- Full explanation text (longer than the card summary)
- Complete supporting biomarkers list with values, reference ranges, and mini bar charts
- "How we identified this pattern": a simple visual showing which biomarkers contributed and how much
- All source citations (expandable, with full reference text)
- All doctor questions (copyable individually or all together)
- "What affects this" section — medication interferences, lifestyle factors, wearable data relevance
- Related patterns (if any — e.g., iron deficiency + vitamin D deficiency might both appear)
- "Back to Dashboard" navigation

---

## Biologically-Informed Network View (Stretch Feature)

### Purpose
Show biomarkers as nodes in a network, clustered by organ system, with color-coded severity. An alternative view to the pattern cards — users can switch between "Pattern View" and "Network View."

### Required Elements
- **Plan A (build first):** Simplified static layout. Organ system clusters (circles or groups) with biomarker names inside. Color = severity. Size = deviation magnitude. Hover shows full details.
- **Plan B (stretch):** Interactive D3.js force-directed graph with the same data.
- **Toggle:** "Pattern View" / "Network View" switch.
- **Accessible alternative:** Table view toggle (for screen readers and users who prefer it).
- **Mobile consideration:** Must not jank. 40 nodes on a phone screen is tight — consider showing only abnormal biomarkers in the graph.

---

## Shared Components

### Severity Badge
| Severity | Color | Icon | Label | Usage |
|---|---|---|---|---|
| WARNING | #DC2626 (red-600) | ⚠ or ! | "Needs Attention" | Reserved for clinically urgent findings |
| CAUTION | #D97706 (amber-600) | ⚡ or ▲ | "Follow Up" | Needs medical follow-up within days-weeks |
| ADVISORY | #2563EB (blue-600) | ℹ or ● | "Lifestyle" | Long-term awareness, no urgency |

**Rule:** If everything is red, nothing is. Most results should be blue or green. Red is rare. This is an aviation paradigm — urgency is triaged.

### Confidence Pill
Small pill/badge showing HIGH, MODERATE, or LOW confidence in a pattern match.
- HIGH: biomarkers clearly match textbook pattern
- MODERATE: some biomarkers match, some borderline
- LOW: weak match, treat as suggestion only

### Progress Indicator
Pipeline stages as a horizontal stepper or vertical list with checkmarks. Each stage lights up as it completes. Not a spinner — users should see exactly what's happening.

### Demo Mode Banner
When viewing a pre-cached demo scenario: subtle banner at top — "This is a demonstration scenario using sample data. Upload your own blood test to see your personal results."

### Clear Data Dialog
Confirmation modal: "This will permanently delete all uploaded reports, extracted results, and analysis data from this device. This cannot be undone." Cancel / Delete buttons.

---

## Data Shapes (What the Dashboard Receives)

The dashboard receives this JSON from the backend. Every field in the "patterns" array is something you can design UI for.

```typescript
interface AnalysisOutput {
  summary: string;                    // 1-2 sentence overall assessment
  patterns: PatternResult[];          // 0-5 pattern cards
  verification_alerts: Alert[];       // 0-n quality/drug flags
  disclaimer: string;                 // Always present, always shown
}

interface PatternResult {
  name: string;                       // Patient-friendly: "Low Iron Pattern"
  severity: "WARNING" | "CAUTION" | "ADVISORY";
  confidence: "HIGH" | "MODERATE" | "LOW";
  explanation: string;                // 2-3 sentences, plain language
  symptomatic_note: string | null;    // E.g., "Your rising resting HR may be related"
  supporting_markers: string[];       // E.g., ["Ferritin: 12 ng/mL (Low)", ...]
  citations: string[];                // E.g., ["Wallach Ch.3: Iron Deficiency Anemia"]
  doctor_questions: string[];         // 2-3 specific questions
}

interface Alert {
  biomarker: string;
  issue: string;                      // E.g., "Possible hemolysis artifact"
  recommendation: string;             // E.g., "Consider repeat testing"
}
```

### Content Length Guidelines
| Field | Typical Length | Design Implication |
|---|---|---|
| `summary` | 1-2 sentences, ~30-80 words | One line on desktop, 2-3 on mobile |
| `name` | 2-5 words | Fits in a card title |
| `severity` | Enum: WARNING/CAUTION/ADVISORY | Badge, not text |
| `confidence` | Enum: HIGH/MODERATE/LOW | Small pill |
| `explanation` | 2-4 sentences, ~50-120 words | Needs space — a short paragraph |
| `symptomatic_note` | 1 sentence or null | Conditional — design for presence AND absence |
| `supporting_markers` | 1-8 items, each ~20-40 chars | List with mini bar charts |
| `citations` | 1-5 items, each ~30-80 chars | Expandable accordion |
| `doctor_questions` | 2-3 items, each ~50-150 chars | Numbered list, copy buttons |
| `disclaimer` | 1 sentence, ~30 words | Footer, always present |

---

## Design Constraints (What's Fixed)

### Locked (Don't Change)
- **Severity color system:** WARNING = #DC2626, CAUTION = #D97706, ADVISORY = #2563EB, Normal = #16A34A. These are aviation-derived and carry clinical meaning. You can adjust shades slightly but the red/amber/blue/green distinction must be obvious.
- **Severity icons:** Must include icon + text + color. Not color alone (accessibility).
- **Mobile-first:** Everything must work at 375px width first. Desktop is an enhancement.
- **WCAG AA:** All text meets contrast ratios. All interactive elements are keyboard-navigable. Severity is never communicated by color alone.
- **Disclaimer:** Must appear on every screen showing clinical content. Not hideable.

### Yours to Define
- Typography (font families, scale, weights)
- Spacing and layout grid
- Iconography (beyond the severity indicators)
- Component shapes (border radius, shadows, card style)
- Transitions and animations (how sections appear, how cards expand)
- Empty states and loading skeletons
- Color palette beyond the severity system (backgrounds, surfaces, text hierarchy)
- Illustration style (if you want illustrations for the upload page, empty states, etc.)
- Logo and branding
- Demo mode banner style

---

## What You DON'T Need to Design

- **The OCR pipeline UI** — it's a progress indicator. You just need to know it takes ~5 seconds.
- **The medication checklist content** — the medical student provides the list. You're designing the searchable checklist component pattern.
- **The network graph data model** — it's nodes and edges. You're designing how a network graph looks; the data comes from the backend.
- **Backend error messages** — the backend team provides exact text. You need error state containers with consistent styling.
- **The medical content** — all clinical text comes from the LLM. You're designing containers for text of varying lengths.

---

## Quick Reference: All Required UI States

Every element that shows data must have these states designed:

| State | When | Example |
|---|---|---|
| **Hidden** | Element not relevant yet | Pattern cards before analysis completes |
| **Loading** | Data being fetched/computed | Skeleton cards, progress indicator |
| **Populated** | Data available, normal case | Pattern card with explanation |
| **Empty** | Data is empty but expected | "No patterns detected" (all normal) |
| **Error** | Something went wrong | "Could not complete analysis" |
| **Edge case** | Unusual but valid data | Single isolated abnormal biomarker, very long explanation text, 0 doctor questions |

Not every element needs every state — just the ones that apply.
