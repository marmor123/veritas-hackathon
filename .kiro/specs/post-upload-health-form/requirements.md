# Requirements Document

## Introduction

After a user uploads a blood test file and OCR extraction completes, a health context form is displayed. This form collects the user's current nutritional supplements (from a predefined list plus free-text "Other") and any diseases they have (free-text). The user may also skip the form entirely via an "I don't want to answer" option. Once submitted (or skipped), the frontend sends the OCR-extracted biomarker data along with the supplement and disease information to the existing `POST /api/verify` endpoint. While waiting for the verification response, the blood test results remain visible with a loading indicator below them. This feature is frontend-only; no backend changes are required.

## Glossary

- **Health_Form**: The React component displayed after OCR completes, collecting supplement and disease information from the user.
- **Supplement_Selector**: The UI control within the Health_Form that allows users to select predefined supplements or enter custom ones.
- **Disease_Input**: The free-text input field within the Health_Form where users enter any diseases they have.
- **Verification_Payload**: The JSON object sent to `POST /api/verify` containing biomarkers, supplements, and diseases.
- **Pipeline_Controller**: The App.tsx orchestration logic that manages pipeline stage transitions.
- **Verify_Endpoint**: The `POST /api/verify` FastAPI route that accepts biomarkers and health context for verification.

## Requirements

### Requirement 1: Display Health Form After OCR Completion

**User Story:** As a user, I want to see a health context form after my blood test is processed by OCR, so that I can provide additional information for more accurate analysis.

#### Acceptance Criteria

1. WHEN OCR extraction completes successfully, THE Pipeline_Controller SHALL transition the pipeline stage to a health form stage and THE Health_Form SHALL be displayed to the user.
2. WHILE the Health_Form is displayed, THE Pipeline_Controller SHALL retain the OCR-extracted biomarker data in application state.
3. THE Health_Form SHALL display a heading that communicates the purpose of collecting health context information.

### Requirement 2: Supplement Selection

**User Story:** As a user, I want to select which nutritional supplements I take from a predefined list or add custom ones, so that the system can account for supplement interference in my results.

#### Acceptance Criteria

1. THE Supplement_Selector SHALL display a predefined list of common nutritional supplements as selectable options (including at minimum: Vitamin D, Vitamin B12, Iron, Omega-3, Magnesium, Zinc, Calcium, Biotin, Folic Acid, Multivitamin).
2. THE Supplement_Selector SHALL allow the user to select zero or more supplements from the predefined list.
3. THE Supplement_Selector SHALL provide an "Other" option that, WHEN selected, reveals a free-text input field for entering a custom supplement name.
4. WHEN the user selects a supplement, THE Supplement_Selector SHALL visually indicate the selected state of that supplement.
5. WHEN the user deselects a supplement, THE Supplement_Selector SHALL remove the visual selection indicator and exclude that supplement from the collected data.

### Requirement 3: Disease Information Input

**User Story:** As a user, I want to enter any diseases I have, so that the system can consider my medical conditions during verification.

#### Acceptance Criteria

1. THE Disease_Input SHALL provide a free-text input field with a descriptive label and placeholder text indicating the expected input.
2. THE Disease_Input SHALL accept any text input without character restrictions beyond a reasonable maximum length of 500 characters.
3. THE Disease_Input SHALL allow the field to remain empty if the user has no diseases to report.

### Requirement 4: Form Submission and Payload Construction

**User Story:** As a user, I want to submit my health context so that the system can proceed with verification of my blood test results.

#### Acceptance Criteria

1. THE Health_Form SHALL display a submit button that is always enabled (since all fields are optional).
2. WHEN the user clicks the submit button, THE Health_Form SHALL construct a Verification_Payload containing the OCR-extracted biomarkers array, the selected supplements as a string array, and the disease text as a string.
3. WHEN the submit button is clicked, THE Pipeline_Controller SHALL send the Verification_Payload to the Verify_Endpoint via an HTTP POST request to `/api/verify`.
4. WHILE the verification request is in progress, THE Pipeline_Controller SHALL continue displaying the OCR-extracted biomarker results (blood test data) above a loading indicator for the verification step.
5. WHEN the Verify_Endpoint returns a successful response, THE Pipeline_Controller SHALL transition the pipeline stage to the next stage and store the verification result below the biomarker results.
6. IF the Verify_Endpoint returns an error response, THEN THE Pipeline_Controller SHALL display an error message to the user and allow resubmission while keeping the biomarker results visible.

### Requirement 5: Skip Option

**User Story:** As a user, I want to skip the health form if I prefer not to answer, so that I can still get my blood test results verified without providing additional context.

#### Acceptance Criteria

1. THE Health_Form SHALL display a clearly visible "I don't want to answer" button or link alongside the submit button.
2. WHEN the user clicks "I don't want to answer", THE Pipeline_Controller SHALL send the Verification_Payload to the Verify_Endpoint with an empty supplements array and an empty diseases string.
3. WHEN the user clicks "I don't want to answer", THE Pipeline_Controller SHALL transition the pipeline to the verification-loading stage identically to a normal form submission.

### Requirement 6: Post-Submission Display

**User Story:** As a user, I want to see my blood test results while waiting for verification, so that I can review my data without interruption.

#### Acceptance Criteria

1. WHEN the Health_Form is submitted or skipped, THE Pipeline_Controller SHALL immediately display the OCR-extracted biomarker list (blood test results) on screen.
2. WHILE the verification API request is in progress, THE Pipeline_Controller SHALL display a loading indicator below the biomarker results indicating that verification is processing.
3. WHEN the verification response is received, THE Pipeline_Controller SHALL replace the loading indicator with the verification results displayed below the biomarker list.

### Requirement 7: Form Accessibility and Responsiveness

**User Story:** As a user, I want the health form to be accessible and usable on different screen sizes, so that I can provide my health context regardless of my device or assistive technology.

#### Acceptance Criteria

1. THE Health_Form SHALL use semantic HTML elements and appropriate ARIA labels for all interactive controls.
2. THE Health_Form SHALL be navigable using keyboard-only input (Tab, Enter, Space).
3. THE Health_Form SHALL render correctly on viewport widths from 320px to 1920px.
4. THE Supplement_Selector SHALL associate each selectable option with a visible label.
