"""
OCR Extraction Engine — PDF/Image to structured biomarker data.

Uses PyMuPDF for PDF rendering, OpenCV for image preprocessing,
and Tesseract for OCR. Parses extracted text against a comprehensive
lab test mapping to produce structured biomarker results.
"""

import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import pytesseract
import re
import os

# Configure Tesseract path for Windows
if os.name == "nt":
    _tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = _tesseract_path

LAB_TEST_MAPPING = {
    # --- Complete Blood Count (CBC) ---
    "WBC-LEUCOCYTES": "WBC", "WBC COUNT": "WBC", "TOTAL WBC AND DIFFERENTIAL COUNT": "WBC", "WBC": "WBC",
    "PLATELETS": "PLATELETS", "PLATELET COUNT": "PLATELETS", "PLT": "PLATELETS",
    "HEMOGLOBIN": "HEMOGLOBIN", "HGB": "HEMOGLOBIN", "HB": "HEMOGLOBIN", "TOTAL HB": "HEMOGLOBIN",
    "RBC COUNT": "RBC", "RBC": "RBC", "RED BLOOD CELLS": "RBC",
    "HEMATOCRIT": "HEMATOCRIT", "HCT": "HEMATOCRIT",
    "MCV": "MCV", "MCH": "MCH", "MCHC": "MCHC", "RDW CV": "RDW", "RDW": "RDW",
    "NEUTROPHILS": "NEUTROPHILS", "NEUT": "NEUTROPHILS", "LYMPHOCYTES": "LYMPHOCYTES", "LYMP": "LYMPHOCYTES",
    "EOSINOPHILS": "EOSINOPHILS", "EOS": "EOSINOPHILS", "MONOCYTES": "MONOCYTES", "MONO": "MONOCYTES",
    "BASOPHILS": "BASOPHILS", "BASO": "BASOPHILS", "MPV": "MPV", "ESR": "ESR",
    "ERYTHROCYTE SEDIMENTATION RATE": "ESR",

    # --- Metabolic, Liver & Kidney Function ---
    "FASTING BLOOD SUGAR": "GLUCOSE", "GLUCOSE (B)": "GLUCOSE", "GLUCOSE": "GLUCOSE", "HBA1C": "HBA1C",
    "CREATININE, SERUM": "CREATININE", "CREATININE (B)": "CREATININE", "CREATININE": "CREATININE",
    "UREA (B)": "UREA", "UREA": "UREA", "BLOOD UREA NITROGEN": "BUN", "URIC ACID": "URIC_ACID",
    "SGPT": "ALT", "ALT (GPT)": "ALT", "ALT": "ALT", "SGOT": "AST", "AST (GOT)": "AST", "AST": "AST",
    "ALKP-ALKALINE PHOSPHATASE": "ALKP", "ALKALINE PHOSPHATASE": "ALKP", "ALKP": "ALKP",
    "TOTAL PROTEIN": "TOTAL_PROTEIN", "ALBUMIN": "ALBUMIN", "GLOBULIN": "GLOBULIN", "A/G RATIO": "AG_RATIO",
    "TOTAL BILIRUBIN": "BILIRUBIN_TOTAL", "CONJUGATED BILIRUBIN": "BILIRUBIN_CONJUGATED",
    "UNCONGUGATED BILIRUBIN": "BILIRUBIN_UNCONJUGATED", "UNCONJUGATED BILIRUBIN": "BILIRUBIN_UNCONJUGATED",
    "DELTA BILIRUBIN": "BILIRUBIN_DELTA",

    # --- Lipid Profile ---
    "CHOLESTEROL": "CHOLESTEROL", "TRIGLYCERIDE": "TRIGLYCERIDES", "TRIGLYCERIDES": "TRIGLYCERIDES",
    "HDL CHOLESTEROL": "HDL", "DIRECT LDL": "LDL", "VLDL": "VLDL",
    "CHOL/HDL RATIO": "CHOL_HDL_RATIO", "LDL/HDL RATIO": "LDL_HDL_RATIO",

    # --- Electrolytes & Minerals ---
    "SODIUM (NA+)": "SODIUM", "SODIUM": "SODIUM",
    "POTASSIUM (K+)": "POTASSIUM", "POTASSIUM": "POTASSIUM",
    "CHLORIDE (CL-)": "CHLORIDE", "CHLORIDE": "CHLORIDE",
    "CALCIUM": "CALCIUM", "IRON": "IRON", "TOTAL IRON BINDING CAPACITY (TIBC)": "TIBC",
    "TRANSFERRIN SATURATION": "TRANSFERRIN_SATURATION",

    # --- Thyroid Panel ---
    "T3 - TRIIODOTHYRONINE": "T3", "T3": "T3",
    "T4 - THYROXINE": "T4", "T4": "T4",
    "TSH - THYROID STIMULATING HORMONE": "TSH", "TSH": "TSH",

    # --- Vitamins, Immunoassays & Special Markers ---
    "25(OH) VITAMIN D": "VITAMIN_D", "VITAMIN B12": "VITAMIN_B12", "HOMOCYSTEINE, SERUM": "HOMOCYSTEINE",
    "PSA-PROSTATE SPECIFIC ANTIGEN, TOTAL": "PSA", "IGE": "IGE", "CRP": "CRP",
    "HIV I & II AB/AG": "HIV", "HBSAG": "HEPATITIS_B", "RH (D) TYPE": "RH_TYPE", "ABO TYPE": "ABO_TYPE",
    "MALARIAL PARASITE": "MALARIA", "MALARIA": "MALARIA", "PARASITES": "PARASITES",
    "MICROALBUMIN (PER URINE VOLUME)": "MICROALBUMIN", "MICROALBUMIN": "MICROALBUMIN",
    "URINE GLUCOSE": "URINE_GLUCOSE", "URINE PROTEIN": "URINE_PROTEIN",
    "SPECIFIC GRAVITY": "URINE_SPECIFIC_GRAVITY",
}

# Words that indicate explanation/footnote lines — skip these
EXPLANATION_BLACKLIST = [
    "SYNTHESIZED", "REFLECTS THE AVERAGE", "SUGGESTED INTERPRETATION",
    "ABSORPTION", "EXCRETION", "DEFINED AS", "TRAIT", "DIETARY",
    "INTOXICATION", "EVALUATED", "CONCENTRATION", "Synthesized",
]


def process_pdf_to_spatial_text(pdf_path: str) -> str:
    """
    Convert a PDF file to spatially-reconstructed text using OCR.

    Renders each page at 300 DPI, applies adaptive thresholding,
    runs Tesseract OCR, and reconstructs lines preserving column layout.
    """
    doc = fitz.open(pdf_path)
    all_reconstructed_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Render page to high-res image
        pix = page.get_pixmap(dpi=300)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        img_ready = Image.fromarray(thresh)

        # Run Tesseract with word-level bounding boxes
        ocr_data = pytesseract.image_to_data(
            img_ready, lang="eng", output_type=pytesseract.Output.DICT
        )

        # Group words into lines by Y-coordinate proximity
        lines = {}
        for i in range(len(ocr_data["text"])):
            if int(ocr_data["conf"][i]) > 40:
                text = ocr_data["text"][i].strip()
                if text:
                    top = ocr_data["top"][i]
                    left = ocr_data["left"][i]

                    matched_line = False
                    for y_coord in lines.keys():
                        if abs(top - y_coord) <= 15:
                            lines[y_coord].append((left, text))
                            matched_line = True
                            break
                    if not matched_line:
                        lines[top] = [(left, text)]

        # Reconstruct lines sorted by Y then X
        reconstructed_lines = []
        for y_coord in sorted(lines.keys()):
            sorted_words = sorted(lines[y_coord], key=lambda x: x[0])
            line_text = " ".join([word[1] for word in sorted_words])
            reconstructed_lines.append(line_text)

        all_reconstructed_text.append("\n".join(reconstructed_lines))

    doc.close()
    return "\n".join(all_reconstructed_text)


def process_image_to_text(image_path: str) -> str:
    """
    Run OCR on a standalone image file (PNG, JPG).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    img_ready = Image.fromarray(thresh)

    ocr_data = pytesseract.image_to_data(
        img_ready, lang="eng", output_type=pytesseract.Output.DICT
    )

    lines = {}
    for i in range(len(ocr_data["text"])):
        if int(ocr_data["conf"][i]) > 40:
            text = ocr_data["text"][i].strip()
            if text:
                top = ocr_data["top"][i]
                left = ocr_data["left"][i]

                matched_line = False
                for y_coord in lines.keys():
                    if abs(top - y_coord) <= 15:
                        lines[y_coord].append((left, text))
                        matched_line = True
                        break
                if not matched_line:
                    lines[top] = [(left, text)]

    reconstructed_lines = []
    for y_coord in sorted(lines.keys()):
        sorted_words = sorted(lines[y_coord], key=lambda x: x[0])
        line_text = " ".join([word[1] for word in sorted_words])
        reconstructed_lines.append(line_text)

    return "\n".join(reconstructed_lines)


def parse_text_to_json(raw_text: str) -> dict:
    """
    Parse OCR text to extract biomarker values.

    Uses the LAB_TEST_MAPPING to identify biomarker names in text,
    then extracts numeric or qualitative values from the same line.
    Returns a dict of {canonical_name: value}.
    """
    results = {}
    sorted_keywords = sorted(LAB_TEST_MAPPING.keys(), key=len, reverse=True)

    for line in raw_text.split("\n"):
        line_normalized = re.sub(r"\s+", " ", line).strip()
        line_upper = line_normalized.upper()

        # Skip explanation/footnote lines
        if any(word in line_upper for word in EXPLANATION_BLACKLIST):
            continue

        matched_keyword = None
        for keyword in sorted_keywords:
            if keyword in line_upper:
                matched_keyword = keyword
                break

        if matched_keyword:
            canonical_name = LAB_TEST_MAPPING[matched_keyword]

            # Isolate text to the right of the keyword
            start_idx = line_upper.find(matched_keyword)
            right_of_keyword = line_normalized[start_idx + len(matched_keyword):].strip()
            right_of_keyword_upper = right_of_keyword.upper()

            # Remove reference ranges, dates, and artifacts
            right_of_keyword = re.sub(r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?", "", right_of_keyword)
            right_of_keyword = re.sub(r"\d{2}/\d{2}/\d{4}", "", right_of_keyword)
            right_of_keyword = re.sub(r"\d{2}-[A-Za-z]{3}-\d{4}", "", right_of_keyword)
            right_of_keyword = re.sub(r"\d+\*\d+", "", right_of_keyword)
            right_of_keyword = re.sub(r"\b\d+hr\b", "", right_of_keyword, flags=re.IGNORECASE)

            # Fix decimal points that became spaces (e.g., "4 79" -> "4.79")
            right_of_keyword = re.sub(r"(\d+)\s+(\d{2})\b", r"\1.\2", right_of_keyword)

            # Try numeric extraction first
            numbers_with_prefixes = re.findall(r"([<>]?\s*\d+(?:\.\d+)?)", right_of_keyword)

            if numbers_with_prefixes and canonical_name not in ["URINE_GLUCOSE", "URINE_PROTEIN"]:
                raw_val = numbers_with_prefixes[0].replace(" ", "")
                try:
                    value = float(raw_val)
                except ValueError:
                    value = raw_val

                # Skip year-like numbers
                if value in [2023.0, 2202.0, 1982.0]:
                    continue

                results[canonical_name] = value
                continue

            # Qualitative results
            if canonical_name == "ABO_TYPE":
                blood_type_match = re.search(r'["\']?([ABO]{1,2})["\']?\s*$', line_normalized)
                if blood_type_match:
                    results[canonical_name] = blood_type_match.group(1)
                    continue

            if re.search(r"\bNEGATIVE\b", right_of_keyword_upper) or \
               re.search(r"\bABSENT\b", right_of_keyword_upper) or \
               re.search(r"\bNON\s*-?\s*REACTIVE\b", right_of_keyword_upper):
                results[canonical_name] = "Negative"
                continue
            elif re.search(r"\bPOSITIVE\b", right_of_keyword_upper) or \
                 re.search(r"\bPRESENT\b", right_of_keyword_upper) or \
                 re.search(r"\bREACTIVE\b", right_of_keyword_upper):
                results[canonical_name] = "Positive"
                continue

    return results
