import type { OcrResponse, VerificationResponse, AnalysisResponse } from '../types';

// Demo Scenario 1: Iron Deficiency + Wearable Correlation
export const mockOcrIronDeficiency: OcrResponse = {
  biomarkers: [
    { name: 'Ferritin', value: 12, unit: 'ng/mL', ref_low: 20, ref_high: 200, flag: 'low' },
    { name: 'Iron', value: 35, unit: 'µg/dL', ref_low: 60, ref_high: 170, flag: 'low' },
    { name: 'MCV', value: 78, unit: 'fL', ref_low: 80, ref_high: 100, flag: 'low' },
    { name: 'Hemoglobin', value: 11.2, unit: 'g/dL', ref_low: 12, ref_high: 16, flag: 'low' },
    { name: 'WBC', value: 6.5, unit: '10³/µL', ref_low: 4.5, ref_high: 11, flag: 'normal' },
    { name: 'Platelets', value: 250, unit: '10³/µL', ref_low: 150, ref_high: 400, flag: 'normal' },
    { name: 'Glucose', value: 92, unit: 'mg/dL', ref_low: 70, ref_high: 100, flag: 'normal' },
    { name: 'Creatinine', value: 0.9, unit: 'mg/dL', ref_low: 0.6, ref_high: 1.2, flag: 'normal' },
    { name: 'ALT', value: 22, unit: 'U/L', ref_low: 7, ref_high: 56, flag: 'normal' },
    { name: 'TSH', value: 2.1, unit: 'mIU/L', ref_low: 0.4, ref_high: 4.0, flag: 'normal' },
  ],
  raw_text: 'COMPLETE BLOOD COUNT...',
  parse_confidence: 0.94,
};

export const mockVerificationIronDeficiency: VerificationResponse = {
  verified_results: mockOcrIronDeficiency.biomarkers,
  drug_interferences: [],
  corrected_values: {},
  quality_flags: [],
};

export const mockAnalysisIronDeficiency: AnalysisResponse = {
  summary: 'Your results show a pattern consistent with iron deficiency. Four related markers are below normal range, forming a recognizable clinical pattern rather than isolated abnormalities.',
  patterns: [
    {
      name: 'Iron Deficiency Pattern',
      severity: 'CAUTION',
      confidence: 0.92,
      explanation: 'Severely depleted iron stores (ferritin 12 ng/mL) with microcytosis (MCV 78 fL) and mild anemia (hemoglobin 11.2 g/dL). This combination of low ferritin, low serum iron, reduced MCV, and decreased hemoglobin is the hallmark pattern of iron deficiency anemia. Wearable data shows elevated resting heart rate (76 bpm, up from 68 over 30 days), which may indicate your body is compensating for reduced oxygen-carrying capacity.',
      citations: [
        { chunk_id: 'wallach_ch3_iron_def_01', source: "Wallach's Interpretation of Diagnostic Tests", chapter: 'Chapter 3: Hematologic Disorders' },
        { chunk_id: 'wallach_ch3_iron_def_02', source: "Wallach's Interpretation of Diagnostic Tests", chapter: 'Chapter 3: Hematologic Disorders' },
      ],
      doctor_questions: [
        'Could my iron deficiency be related to dietary intake, or should we investigate other causes like occult blood loss?',
        'Given my trending heart rate increase, should we start iron supplementation now or run additional tests first?',
        'What follow-up timeline would you recommend to recheck my ferritin and hemoglobin levels?',
      ],
      biomarkers: ['Ferritin', 'Iron', 'MCV', 'Hemoglobin'],
    },
  ],
  verification_alerts: [],
  disclaimer: 'This analysis is for informational purposes only and does not constitute medical advice. Please discuss these results with your healthcare provider.',
};

// Demo Scenario 2: Metabolic Syndrome
export const mockOcrMetabolic: OcrResponse = {
  biomarkers: [
    { name: 'Glucose', value: 108, unit: 'mg/dL', ref_low: 70, ref_high: 100, flag: 'high' },
    { name: 'HDL', value: 34, unit: 'mg/dL', ref_low: 40, ref_high: 60, flag: 'low' },
    { name: 'Triglycerides', value: 195, unit: 'mg/dL', ref_low: 0, ref_high: 150, flag: 'high' },
    { name: 'ALT', value: 48, unit: 'U/L', ref_low: 7, ref_high: 40, flag: 'high' },
    { name: 'Uric Acid', value: 7.8, unit: 'mg/dL', ref_low: 3.5, ref_high: 7.2, flag: 'high' },
    { name: 'Hemoglobin', value: 14.5, unit: 'g/dL', ref_low: 12, ref_high: 16, flag: 'normal' },
    { name: 'Creatinine', value: 1.0, unit: 'mg/dL', ref_low: 0.6, ref_high: 1.2, flag: 'normal' },
    { name: 'TSH', value: 1.8, unit: 'mIU/L', ref_low: 0.4, ref_high: 4.0, flag: 'normal' },
  ],
  raw_text: 'METABOLIC PANEL...',
  parse_confidence: 0.96,
};

export const mockAnalysisMetabolic: AnalysisResponse = {
  summary: 'Your results show a cluster of metabolic markers that together suggest insulin resistance. These five values form a single pattern rather than five separate problems.',
  patterns: [
    {
      name: 'Metabolic Syndrome Pattern',
      severity: 'CAUTION',
      confidence: 0.88,
      explanation: 'Elevated fasting glucose (108 mg/dL), low HDL cholesterol (34 mg/dL), high triglycerides (195 mg/dL), borderline elevated ALT (48 U/L suggesting early fatty liver), and elevated uric acid (7.8 mg/dL) together form the metabolic syndrome pattern. These markers are interconnected through insulin resistance — treating them as five separate issues misses the underlying mechanism.',
      citations: [
        { chunk_id: 'wallach_ch5_metabolic_01', source: "Wallach's Interpretation of Diagnostic Tests", chapter: 'Chapter 5: Metabolic Disorders' },
        { chunk_id: 'aha_lipids_guideline_02', source: 'AHA Lipid Management Guidelines', chapter: 'Metabolic Syndrome Criteria' },
      ],
      doctor_questions: [
        'Do these results meet the criteria for metabolic syndrome, and should we measure waist circumference and blood pressure to confirm?',
        'Would lifestyle interventions alone be appropriate at this stage, or should we consider medication?',
        'Should we order a HbA1c to assess longer-term glucose control?',
      ],
      biomarkers: ['Glucose', 'HDL', 'Triglycerides', 'ALT', 'Uric Acid'],
    },
  ],
  verification_alerts: [],
  disclaimer: 'This analysis is for informational purposes only and does not constitute medical advice. Please discuss these results with your healthcare provider.',
};

// Demo Scenario 3: Biotin Interference
export const mockOcrBiotin: OcrResponse = {
  biomarkers: [
    { name: 'TSH', value: 0.15, unit: 'mIU/L', ref_low: 0.4, ref_high: 4.0, flag: 'low' },
    { name: 'Free T4', value: 1.3, unit: 'ng/dL', ref_low: 0.8, ref_high: 1.8, flag: 'normal' },
    { name: 'Hemoglobin', value: 13.8, unit: 'g/dL', ref_low: 12, ref_high: 16, flag: 'normal' },
    { name: 'Glucose', value: 88, unit: 'mg/dL', ref_low: 70, ref_high: 100, flag: 'normal' },
  ],
  raw_text: 'THYROID PANEL...',
  parse_confidence: 0.91,
};

export const mockAnalysisBiotin: AnalysisResponse = {
  summary: 'Your TSH appears low, but this result may not be trustworthy. Biotin supplementation is known to interfere with thyroid immunoassays, producing falsely abnormal TSH values.',
  patterns: [
    {
      name: 'Possible Biotin Interference',
      severity: 'ADVISORY',
      confidence: 0.85,
      explanation: 'Your TSH (0.15 mIU/L) is below normal range, but your Free T4 (1.3 ng/dL) is completely normal. In true hyperthyroidism, we would expect elevated Free T4. This discordance, combined with your reported biotin supplementation, strongly suggests biotin interference with the TSH immunoassay rather than actual thyroid disease. Biotin competes with the assay reagents, producing falsely low TSH readings.',
      citations: [
        { chunk_id: 'wallach_ch7_thyroid_interference_01', source: "Wallach's Interpretation of Diagnostic Tests", chapter: 'Chapter 7: Endocrine Disorders' },
      ],
      doctor_questions: [
        'Should I stop biotin for 48-72 hours and repeat the TSH test to confirm this is interference?',
        'Are any of my other test results potentially affected by biotin interference?',
        'Is there an alternative assay method that is not affected by biotin?',
      ],
      biomarkers: ['TSH', 'Free T4'],
    },
  ],
  verification_alerts: [
    'Drug interference detected: Biotin supplementation may cause falsely low TSH in immunoassays. Consider repeating test after 48-72h biotin washout.',
  ],
  disclaimer: 'This analysis is for informational purposes only and does not constitute medical advice. Please discuss these results with your healthcare provider.',
};

// Demo Scenario 4: Hemolysis Artifact
export const mockOcrHemolysis: OcrResponse = {
  biomarkers: [
    { name: 'Potassium', value: 6.8, unit: 'mEq/L', ref_low: 3.5, ref_high: 5.0, flag: 'high' },
    { name: 'LDH', value: 380, unit: 'U/L', ref_low: 140, ref_high: 280, flag: 'high' },
    { name: 'Creatinine', value: 0.9, unit: 'mg/dL', ref_low: 0.6, ref_high: 1.2, flag: 'normal' },
    { name: 'eGFR', value: 95, unit: 'mL/min', ref_low: 90, ref_high: null, flag: 'normal' },
    { name: 'Hemoglobin', value: 14.2, unit: 'g/dL', ref_low: 12, ref_high: 16, flag: 'normal' },
    { name: 'Glucose', value: 45, unit: 'mg/dL', ref_low: 70, ref_high: 100, flag: 'low' },
  ],
  raw_text: 'BASIC METABOLIC PANEL...',
  parse_confidence: 0.93,
};

export const mockAnalysisHemolysis: AnalysisResponse = {
  summary: 'Your potassium appears dangerously high, but this is likely a sample collection error (hemolysis), not a true medical emergency. Your kidney function is completely normal, which makes true hyperkalemia very unlikely.',
  patterns: [
    {
      name: 'Suspected Hemolysis Artifact',
      severity: 'WARNING',
      confidence: 0.91,
      explanation: 'Extremely elevated potassium (6.8 mEq/L) with completely normal kidney function (eGFR 95, creatinine 0.9) is a classic hemolysis pattern. When red blood cells rupture during blood draw or transport, they release intracellular potassium and LDH into the sample. Your elevated LDH (380 U/L) and very low glucose (45 mg/dL — glucose is consumed by lysed cells) further confirm this is a sample quality issue, not a true electrolyte emergency.',
      citations: [
        { chunk_id: 'wallach_ch1_preanalytical_01', source: "Wallach's Interpretation of Diagnostic Tests", chapter: 'Chapter 1: Pre-analytical Errors' },
      ],
      doctor_questions: [
        'Should I have my potassium rechecked with a fresh blood draw to confirm this was hemolysis?',
        'Is there anything about my veins or the draw technique that might have caused this?',
        'Are any other values in this panel potentially affected by the hemolyzed sample?',
      ],
      biomarkers: ['Potassium', 'LDH', 'Glucose', 'eGFR', 'Creatinine'],
    },
  ],
  verification_alerts: [
    'Possible hemolysis detected: Very high K+ (6.8) with normal kidney function (eGFR 95) suggests sample collection artifact. Recommend repeat draw.',
  ],
  disclaimer: 'This analysis is for informational purposes only and does not constitute medical advice. Please discuss these results with your healthcare provider.',
};

export type DemoScenario = 'iron_deficiency' | 'metabolic_syndrome' | 'biotin_interference' | 'hemolysis_artifact';

export const demoScenarios: Record<DemoScenario, { label: string; ocr: OcrResponse; analysis: AnalysisResponse }> = {
  iron_deficiency: { label: 'Iron Deficiency + Wearable', ocr: mockOcrIronDeficiency, analysis: mockAnalysisIronDeficiency },
  metabolic_syndrome: { label: 'Metabolic Syndrome Cluster', ocr: mockOcrMetabolic, analysis: mockAnalysisMetabolic },
  biotin_interference: { label: 'Biotin Interference', ocr: mockOcrBiotin, analysis: mockAnalysisBiotin },
  hemolysis_artifact: { label: 'Hemolysis Artifact', ocr: mockOcrHemolysis, analysis: mockAnalysisHemolysis },
};
