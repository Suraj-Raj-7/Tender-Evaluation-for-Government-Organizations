"""
backend/tests/test_rules_engine.py
--------------------------------------
Purpose: Unit tests for the deterministic rules engine
(services/rules_engine.py). Tests each of the 8 rule types with a
clear PASS case, a clear FAIL case, a low-confidence REVIEW case, and
relevant edge cases (MSME exemption, young-company scaling, composite
always-REVIEW).

Why this file exists: Phase 4's exit conditions require every rule
type to be independently verified before moving to Phase 5 -- this
engine is what makes the whole platform's decisions reproducible and
defensible, so it must be proven correct in isolation, not just
observed working once in a live demo.

NOTE ON SCOPE: these tests exercise the pure check_*()/evaluate_evidence()
functions directly, using lightweight stand-in objects instead of real
database rows -- no database connection is needed to run this file.
calculate_overall_verdict() is NOT covered here since it requires a
real database session (SQLAlchemy query joins across Verdict/Evidence/
Criterion) -- that would need a test database fixture, which is a
separate, larger piece of test infrastructure this codebase doesn't
have yet. Flagged here rather than silently skipped.

Run with: pytest backend/tests/test_rules_engine.py -v
"""

from types import SimpleNamespace

from app.models.bidder import BidderCategory
from app.models.criterion import RuleType
from app.models.verdict import VerdictEnum
from app.services import rules_engine as re_engine


def make_evidence(**overrides):
    """Builds a lightweight stand-in for an Evidence row, with sensible
    defaults so each test only needs to override the fields it cares about."""
    defaults = dict(
        raw_value="184 Lakhs",
        confidence=0.9,
        document_id=1,
        ai_rationale="test rationale",
        page_number=1,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_criterion(**overrides):
    """Builds a lightweight stand-in for a Criterion row."""
    defaults = dict(
        operator=">=",
        threshold_json={"value": 128, "unit": "Lakhs", "years": 3},
        mandatory=True,
        msme_exempt=False,
        rule_type=RuleType.NUMERIC_THRESHOLD,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_bidder(**overrides):
    """Builds a lightweight stand-in for a Bidder row."""
    defaults = dict(category=BidderCategory.GENERAL, company_age_years=5.0)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_tender(**overrides):
    """Builds a lightweight stand-in for a Tender row."""
    defaults = dict(estimated_value=200.0)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------
# Type 1 -- Numeric Threshold
# ---------------------------------------------------------------------

def test_numeric_threshold_pass():
    evidence = make_evidence(raw_value="184 Lakhs")
    criterion = make_criterion(threshold_json={"value": 128})
    verdict, rationale = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.PASS
    assert "184" in rationale and "128" in rationale


def test_numeric_threshold_fail():
    evidence = make_evidence(raw_value="90 Lakhs")
    criterion = make_criterion(threshold_json={"value": 128})
    verdict, _ = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.FAIL


def test_numeric_threshold_review_low_confidence():
    evidence = make_evidence(raw_value="184 Lakhs", confidence=0.4)
    criterion = make_criterion(threshold_json={"value": 128})
    verdict, rationale = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.REVIEW
    assert "confidence" in rationale.lower()


def test_numeric_threshold_review_unparseable():
    evidence = make_evidence(raw_value="not a number at all", confidence=0.9)
    criterion = make_criterion(threshold_json={"value": 128})
    verdict, _ = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.REVIEW


def test_numeric_threshold_crore_conversion():
    # 1.5 Crore = 150 Lakhs, should PASS a 128 Lakh threshold.
    evidence = make_evidence(raw_value="Rs 1.5 Crore turnover")
    criterion = make_criterion(threshold_json={"value": 128})
    verdict, _ = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.PASS


def test_numeric_threshold_non_money_unit_days_pass():
    evidence = make_evidence(raw_value="Bid validity confirmed for 180 days")
    criterion = make_criterion(threshold_json={"value": 180, "unit": "days"}, operator=">=")
    verdict, rationale = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.PASS
    assert "days" in rationale


def test_numeric_threshold_non_money_unit_years_fail():
    evidence = make_evidence(raw_value="Work completed 9 years ago")
    criterion = make_criterion(threshold_json={"value": 7, "unit": "years"}, operator="<=")
    verdict, rationale = re_engine.check_numeric_threshold(evidence, criterion)
    assert verdict == VerdictEnum.FAIL
    assert "years" in rationale

# ---------------------------------------------------------------------
# Type 2 -- Conditional Threshold
# ---------------------------------------------------------------------

def test_conditional_threshold_msme_exemption():
    evidence = make_evidence(raw_value="50 Lakhs")
    criterion = make_criterion(threshold_json={"value": 128}, msme_exempt=True)
    bidder = make_bidder(category=BidderCategory.MSME)
    verdict, rationale = re_engine.check_conditional_threshold(evidence, criterion, bidder)
    assert verdict == VerdictEnum.PASS
    assert "exemption" in rationale.lower()


def test_conditional_threshold_young_company_scaling():
    # Company is 1.5 years old against a 3-year/128L requirement ->
    # scaled threshold should be 64L. Bidder reports 70L -> PASS.
    evidence = make_evidence(raw_value="70 Lakhs")
    criterion = make_criterion(threshold_json={"value": 128, "years": 3}, msme_exempt=False)
    bidder = make_bidder(category=BidderCategory.GENERAL, company_age_years=1.5)
    verdict, rationale = re_engine.check_conditional_threshold(evidence, criterion, bidder)
    assert verdict == VerdictEnum.PASS
    assert "scaled" in rationale.lower()


def test_conditional_threshold_no_exemption_no_scaling_needed():
    evidence = make_evidence(raw_value="184 Lakhs")
    criterion = make_criterion(threshold_json={"value": 128, "years": 3}, msme_exempt=False)
    bidder = make_bidder(category=BidderCategory.GENERAL, company_age_years=5.0)
    verdict, _ = re_engine.check_conditional_threshold(evidence, criterion, bidder)
    assert verdict == VerdictEnum.PASS


# ---------------------------------------------------------------------
# Type 3 -- No-Loss Check
# ---------------------------------------------------------------------

def test_no_loss_pass_explicit_statement():
    evidence = make_evidence(raw_value="No losses reported in the last 5 years", confidence=0.9)
    criterion = make_criterion()
    verdict, _ = re_engine.check_no_loss(evidence, criterion)
    assert verdict == VerdictEnum.PASS


def test_no_loss_fail_too_many_loss_years():
    evidence = make_evidence(raw_value="Losses reported in FY2020, FY2021, and FY2022", confidence=0.9)
    criterion = make_criterion(threshold_json={"max_loss_years": 2})
    verdict, _ = re_engine.check_no_loss(evidence, criterion)
    assert verdict == VerdictEnum.FAIL


def test_no_loss_review_low_confidence():
    evidence = make_evidence(raw_value="Losses reported in FY2020", confidence=0.5)
    criterion = make_criterion()
    verdict, _ = re_engine.check_no_loss(evidence, criterion)
    assert verdict == VerdictEnum.REVIEW


# ---------------------------------------------------------------------
# Type 4 -- Quantity / Percentage
# ---------------------------------------------------------------------

def test_quantity_pct_pass_simple_threshold():
    evidence = make_evidence(raw_value="180 Lakhs completed work")
    criterion = make_criterion(threshold_json={"pct": 80})
    tender = make_tender(estimated_value=200.0)
    verdict, _ = re_engine.check_quantity_pct(evidence, criterion, tender)
    assert verdict == VerdictEnum.PASS


def test_quantity_pct_pass_single_work_combination():
    evidence = make_evidence(raw_value="170 Lakhs completed work")  # 85% of 200
    criterion = make_criterion(threshold_json={"combinations": [80, 60, 40]})
    tender = make_tender(estimated_value=200.0)
    verdict, _ = re_engine.check_quantity_pct(evidence, criterion, tender)
    assert verdict == VerdictEnum.PASS


def test_quantity_pct_review_below_single_work_combination():
    evidence = make_evidence(raw_value="100 Lakhs completed work")  # 50% of 200
    criterion = make_criterion(threshold_json={"combinations": [80, 60, 40]})
    tender = make_tender(estimated_value=200.0)
    verdict, rationale = re_engine.check_quantity_pct(evidence, criterion, tender)
    assert verdict == VerdictEnum.REVIEW
    assert "manual" in rationale.lower()


# ---------------------------------------------------------------------
# Type 5 -- Boolean Declaration
# ---------------------------------------------------------------------

def test_boolean_pass():
    evidence = make_evidence(raw_value="Declaration of non-blacklisting confirmed", confidence=0.9)
    criterion = make_criterion()
    verdict, _ = re_engine.check_boolean(evidence, criterion)
    assert verdict == VerdictEnum.PASS


def test_boolean_fail_missing():
    evidence = make_evidence(raw_value=None, confidence=0.9)
    criterion = make_criterion()
    verdict, _ = re_engine.check_boolean(evidence, criterion)
    assert verdict == VerdictEnum.FAIL


def test_boolean_review_low_confidence():
    evidence = make_evidence(raw_value="some declaration text", confidence=0.4)
    criterion = make_criterion()
    verdict, _ = re_engine.check_boolean(evidence, criterion)
    assert verdict == VerdictEnum.REVIEW


# ---------------------------------------------------------------------
# Type 6 -- Document Presence
# ---------------------------------------------------------------------

def test_doc_presence_pass():
    evidence = make_evidence(raw_value="GSTIN 27ABCDE1234F1Z5", confidence=0.9, document_id=5)
    criterion = make_criterion()
    verdict, _ = re_engine.check_doc_presence(evidence, criterion)
    assert verdict == VerdictEnum.PASS


def test_doc_presence_fail_missing_document():
    evidence = make_evidence(raw_value=None, confidence=0.9, document_id=None)
    criterion = make_criterion()
    verdict, _ = re_engine.check_doc_presence(evidence, criterion)
    assert verdict == VerdictEnum.FAIL


def test_doc_presence_review_low_confidence():
    evidence = make_evidence(raw_value="blurry GST text", confidence=0.5, document_id=5)
    criterion = make_criterion()
    verdict, _ = re_engine.check_doc_presence(evidence, criterion)
    assert verdict == VerdictEnum.REVIEW


# ---------------------------------------------------------------------
# Type 7 -- Classification Check
# ---------------------------------------------------------------------

def test_classification_class1_pass():
    evidence = make_evidence(raw_value="Local content is 55%", confidence=0.9)
    criterion = make_criterion(threshold_json={"class_1_pct": 50, "class_2_pct": 20})
    verdict, rationale = re_engine.check_classification(evidence, criterion)
    assert verdict == VerdictEnum.PASS
    assert "Class I" in rationale


def test_classification_class2_pass():
    evidence = make_evidence(raw_value="Local content is 25%", confidence=0.9)
    criterion = make_criterion(threshold_json={"class_1_pct": 50, "class_2_pct": 20})
    verdict, rationale = re_engine.check_classification(evidence, criterion)
    assert verdict == VerdictEnum.PASS
    assert "Class II" in rationale


def test_classification_fail_below_threshold():
    evidence = make_evidence(raw_value="Local content is 10%", confidence=0.9)
    criterion = make_criterion(threshold_json={"class_1_pct": 50, "class_2_pct": 20})
    verdict, _ = re_engine.check_classification(evidence, criterion)
    assert verdict == VerdictEnum.FAIL


# ---------------------------------------------------------------------
# Type 8 -- Composite (always REVIEW, documented limitation)
# ---------------------------------------------------------------------

def test_composite_always_review():
    evidence = make_evidence()
    criterion = make_criterion()
    bidder = make_bidder()
    verdict, rationale = re_engine.check_composite(evidence, criterion, bidder)
    assert verdict == VerdictEnum.REVIEW
    assert "not yet automated" in rationale.lower()


# ---------------------------------------------------------------------
# Dispatcher -- evaluate_evidence()
# ---------------------------------------------------------------------

def test_evaluate_evidence_dispatches_correctly():
    evidence = make_evidence(raw_value="184 Lakhs")
    criterion = make_criterion(rule_type=RuleType.NUMERIC_THRESHOLD, threshold_json={"value": 128})
    bidder = make_bidder()
    tender = make_tender()
    verdict, _ = re_engine.evaluate_evidence(evidence, criterion, bidder, tender)
    assert verdict == VerdictEnum.PASS


def test_evaluate_evidence_unknown_rule_type_is_review():
    evidence = make_evidence()
    criterion = make_criterion(rule_type="SOMETHING_UNDEFINED")
    bidder = make_bidder()
    tender = make_tender()
    verdict, rationale = re_engine.evaluate_evidence(evidence, criterion, bidder, tender)
    assert verdict == VerdictEnum.REVIEW
    assert "unknown rule_type" in rationale.lower()


def test_evaluate_evidence_never_crashes_on_bad_data():
    # threshold_json is None, which would break naive dict access if
    # not handled -- confirms the dispatcher's own try/except also
    # protects against a check function raising unexpectedly.
    evidence = make_evidence(raw_value="184 Lakhs")
    criterion = make_criterion(rule_type=RuleType.NUMERIC_THRESHOLD, threshold_json=None)
    bidder = make_bidder()
    tender = make_tender()
    verdict, _ = re_engine.evaluate_evidence(evidence, criterion, bidder, tender)
    assert verdict == VerdictEnum.REVIEW