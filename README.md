# Tender Evaluation — AI-Assisted Decision Support


## What this is

This repository contains a working prototype of an AI-assisted tender evaluation system designed for the Government Organisations. The platform automates the extraction of eligibility criteria and bidder information while maintaining a human-in-the-loop approach for final decision-making.

## Project Overview
Government procurement involves cross-referencing hundreds of pages of legal and technical documents. Manual evaluation is slow and prone to inconsistency. This platform uses a "Human-in-the-Loop" approach where AI extracts information and deterministic rules decide eligibility.

## Features
Automatic Criteria Extraction: Understands complex tender documents to extract technical, financial, and compliance requirements.

Robust Document Parsing: Handles digital PDFs, scanned documents, and photographs using OCR (Tesseract) and layout-aware processing.

Explainable Verdicts: Every decision (Eligible, Not Eligible, or Manual Review) is linked back to a specific document and value.

End-to-End Auditability: Maintains a complete trail of extractions and human sign-offs, suitable for CAG audits or RTI queries.

Fail-Safe Design: The system never silently disqualifies; ambiguous cases are flagged for manual review.

## Prereqs (Windows 11)

1. Python 3.11 or 3.12 already installed (you have this).
2. Tesseract OCR for Windows. Download the installer from
   https://github.com/UB-Mannheim/tesseract/wiki and install to the default
   path `C:\Program Files\Tesseract-OCR\`. Add that path to your PATH or the
   app will pick it up from the default location.
3. Poppler for Windows (needed by pdf2image to rasterize PDFs for OCR).
   Download from https://github.com/oschwartz10612/poppler-windows/releases,
   unzip to `C:\poppler\`, add `C:\poppler\Library\bin` to PATH.
4. GTK runtime for WeasyPrint. Download the GTK3 runtime installer from
   https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
   and install with default options. Restart your terminal afterwards.

If any of (3) or (4) is painful, the app degrades gracefully:
- No Poppler → scanned PDFs cannot be OCRed; digital PDFs and images still work.
- No GTK → PDF report export disabled; HTML report still works.

## Setup

```cmd

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

python run.py
