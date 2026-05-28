# Implementation Plan: Post-Upload Health Form

## Overview

Add a health context form between OCR completion and verification. The form collects supplements and diseases, then sends them with biomarkers to `POST /api/verify`. Implementation is frontend-only using React 19 + TypeScript + Tailwind CSS 4.

## Tasks

- [x] 1. Update types and create verify API client
  - [x] 1.1 Add `'health_form'` to the `PipelineStage` union type in `src/types/index.ts`
    - Add `'health_form'` between `'ocr'` and `'verification'` in the type definition
    - _Requirements: 1.1_
  - [x] 1.2 Create `src/api/verify.ts` API client
    - Define `VerifyPayload` interface with `biomarkers`, `supplements`, and `medications` fields
    - Implement `verifyBiomarkers(payload: VerifyPayload): Promise<VerificationResponse>` function
    - Follow the same pattern as `src/api/ocr.ts` (use `API_BASE`, throw on non-ok response)
    - _Requirements: 4.3_

- [x] 2. Implement HealthForm components
  - [x] 2.1 Create `src/components/HealthForm/SupplementSelector.tsx`
    - Define `PREDEFINED_SUPPLEMENTS` constant array: Vitamin D, Vitamin B12, Iron, Omega-3, Magnesium, Zinc, Calcium, Biotin, Folic Acid, Multivitamin
    - Render each supplement as a toggle chip/button with selected/unselected visual states
    - Support multi-select: clicking toggles selection on/off
    - Include an "Other" option that reveals a free-text input when selected
    - Props: `selected: string[]`, `onChange: (selected: string[]) => void`
    - Use semantic HTML with `role="group"`, `aria-label`, and visible labels for each option
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 7.1, 7.4_
  - [x] 2.2 Create `src/components/HealthForm/DiseaseInput.tsx`
    - Render a textarea with descriptive label and placeholder text
    - Enforce 500-character `maxLength` attribute
    - Show remaining character count when input length > 400
    - Props: `value: string`, `onChange: (value: string) => void`
    - Use semantic HTML with `<label>` associated to the textarea via `htmlFor`/`id`
    - _Requirements: 3.1, 3.2, 3.3, 7.1_
  - [x] 2.3 Create `src/components/HealthForm/HealthForm.tsx`
    - Manage local state: `selectedSupplements: string[]`, `otherSupplement: string`, `showOtherInput: boolean`, `diseases: string`
    - Render heading explaining the purpose of the form
    - Render `SupplementSelector` and `DiseaseInput` sub-components
    - Render "Submit" button (always enabled) and "I don't want to answer" skip button/link
    - On submit: collect supplements (predefined selected + other if non-empty), call `onSubmit(supplements, diseases)`
    - On skip: call `onSkip()`
    - Props: `onSubmit: (supplements: string[], diseases: string) => void`, `onSkip: () => void`
    - Ensure keyboard navigability (Tab, Enter, Space)
    - _Requirements: 1.3, 4.1, 5.1, 7.1, 7.2, 7.3_

- [x] 3. Integrate HealthForm into App.tsx pipeline
  - [x] 3.1 Update `handleFileSelected` to transition to `'health_form'` after OCR
    - In the mock/demo path: after setting `ocrResult`, set stage to `'health_form'` instead of `'analysis'`
    - In the real API path: after OCR succeeds, set stage to `'health_form'` instead of `'complete'`
    - _Requirements: 1.1, 1.2_
  - [x] 3.2 Update `handleDemoScenario` to include `'health_form'` stage
    - After setting `ocrResult`, set stage to `'health_form'` and stop (don't auto-advance to analysis)
    - _Requirements: 1.1_
  - [x] 3.3 Add `handleHealthFormSubmit` and `handleHealthFormSkip` handlers in App.tsx
    - `handleHealthFormSubmit(supplements, diseases)`: set stage to `'verification'`, call `verifyBiomarkers`, on success store result and advance to `'complete'`/`'analysis'`, on error set error state
    - `handleHealthFormSkip()`: call `handleHealthFormSubmit([], '')`
    - Import and use `verifyBiomarkers` from `src/api/verify.ts`
    - _Requirements: 4.2, 4.3, 4.5, 4.6, 5.2, 5.3_
  - [x] 3.4 Render HealthForm conditionally in App.tsx JSX
    - Show `<HealthForm>` when `stage === 'health_form'`
    - Show biomarker results (`BiomarkerList`) when `ocrResult` exists AND stage is `'health_form'` or later
    - Show loading indicator when stage is `'verification'`
    - Show verification results when stage is `'complete'` or `'analysis'`
    - _Requirements: 6.1, 6.2, 6.3, 4.4_

- [x] 4. Checkpoint - Verify integration works
  - Ensure the app builds without errors (`npm run build`)
  - Ensure all existing lint rules pass (`npm run lint`)
  - Ask the user if questions arise.

- [ ]* 5. Write property tests
  - [ ]* 5.1 Install `fast-check` as a dev dependency and set up Vitest (if not already present)
    - Add `fast-check` and `vitest` + `@testing-library/react` + `jsdom` to devDependencies
    - Create `vitest.config.ts` if not present
    - _Requirements: Testing infrastructure_
  - [ ]* 5.2 Write property test for supplement selection state consistency
    - **Property 1: Supplement selection state consistency**
    - Generate random subsets of PREDEFINED_SUPPLEMENTS + optional custom "Other" text
    - Verify the collected supplements array matches exactly the selected subset + custom text
    - Minimum 100 iterations
    - **Validates: Requirements 2.2, 2.5**
  - [ ]* 5.3 Write property test for disease input length constraint
    - **Property 2: Disease input length constraint**
    - Generate arbitrary strings of varying lengths (0 to 1000+ chars)
    - Verify stored value length is always ≤ 500 characters
    - Verify strings ≤ 500 are stored verbatim
    - Minimum 100 iterations
    - **Validates: Requirements 3.2**
  - [ ]* 5.4 Write property test for payload construction correctness
    - **Property 3: Payload construction correctness**
    - Generate random biomarker arrays, supplement arrays, and disease strings
    - Verify the constructed VerifyPayload contains exact values with no mutation
    - Minimum 100 iterations
    - **Validates: Requirements 4.2**

- [ ]* 6. Write unit tests
  - [ ]* 6.1 Write unit tests for HealthForm component
    - Test: form renders heading, submit button, skip button
    - Test: submit calls onSubmit with correct data
    - Test: skip calls onSkip
    - Test: submit button is always enabled regardless of form state
    - _Requirements: 1.3, 4.1, 5.1_
  - [ ]* 6.2 Write unit tests for SupplementSelector
    - Test: all predefined supplements are rendered
    - Test: clicking "Other" reveals free-text input
    - Test: selecting a supplement adds visual indicator
    - _Requirements: 2.1, 2.3, 2.4_
  - [ ]* 6.3 Write unit tests for App.tsx pipeline integration
    - Test: OCR complete → stage transitions to 'health_form'
    - Test: form submit → stage transitions to 'verification' → API called → 'complete'
    - Test: form skip → same flow as submit with empty data
    - Test: API error → error displayed, biomarkers still visible
    - _Requirements: 1.1, 4.5, 4.6, 5.2, 5.3, 6.1, 6.2, 6.3_

- [x] 7. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Verify the build succeeds with `npm run build`

## Task Dependency Graph

```json
{
  "waves": [
    { "tasks": ["1"] },
    { "tasks": ["2"] },
    { "tasks": ["3"] },
    { "tasks": ["4"] },
    { "tasks": ["5", "6"] },
    { "tasks": ["7"] }
  ]
}
```

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The implementation language is TypeScript (React 19 + Tailwind CSS 4)
- No backend changes are needed — the existing `POST /api/verify` endpoint already accepts supplements and medications
- Property tests use `fast-check` library with minimum 100 iterations each
- The form state is local to HealthForm; pipeline orchestration stays in App.tsx
