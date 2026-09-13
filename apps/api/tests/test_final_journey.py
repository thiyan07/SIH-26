"""Final journey regression tests (requirements §20).

Covers: plain-English -> form, dashboard, scheme, age, eligibility,
BusinessSetup, Re-analyse, Finance, Simulator Skip, Report, download, Videos, history immutability.
"""
from app.engines.nlp_parser import parse_free_text
from app.services.analysis import run_analysis
from app.schemas import AnalysisRequest

def test_dashboard_no_ai_suggested():
    # Dashboard should not contain AI Suggested Opportunities component - verify via file content
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Dashboard.tsx")
    text = p.read_text()
    # Check that the actual JSX component block for AI Suggested is removed (not just comment)
    assert "suggested.slice(0, 6)" not in text, "Dashboard should not contain AI Suggested Opportunities component"
    assert "aiSuggestedOpportunities" not in text, "Dashboard should not import AI Suggested"
    assert "Business Setup" in text, "Dashboard should have Business Setup card"
    assert "Go to Business Setup" in text, "Dashboard should have Go to Business Setup button"
    # Budget Allocation should be removed from Dashboard (detailed split lives on Business Setup)
    assert "Budget Allocation" not in text, "Dashboard should not contain Budget Allocation"
    # Weather/Climate Evidence should be removed from Dashboard
    assert "Weather & Climate Evidence" not in text and "weatherClimate" not in text, "Dashboard should not contain Weather/Climate Evidence"

def test_business_setup_has_budget_split():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/BusinessSetup.tsx")
    text = p.read_text()
    assert "Suggested Budget Split" in text
    assert "Is this budget split okay?" in text
    assert "Yes, Continue" in text
    assert "Change Business Analysis" in text, "No should go to Analyze (Change Business Analysis)"
    assert "Back to Dashboard" not in text, "BusinessSetup No should not go to Dashboard"
    assert "Data status:" not in text and "Data Status" not in text, "Data Status: Estimated should be removed"
    # Check for i18n key or rendered title
    assert "whatYouNeedToStart" in text or "What You Need to Start" in text
    assert "howToOperate" not in text.lower(), "BusinessSetup should not have How to Operate"

def test_scheme_requires_selection_and_age():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Schemes.tsx")
    text = p.read_text()
    # Age is now single source on Analyze; Schemes must NOT have separate age input
    assert "Using age from Analyze" in text or "age from Analyze" in text.lower()
    assert "Confirm Scheme" in text
    assert "Eligibility Result" in text
    # Ensure old separate age input was removed
    assert text.count("Enter your age") == 0, "Schemes should not have separate age input"
    # Also verify Analyze has age
    p2 = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Analyze.tsx")
    text2 = p2.read_text()
    assert "Applicant Age" in text2
    assert "applicant_age" in text2

def test_finance_has_confirmation():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Finance.tsx")
    text = p.read_text()
    assert "Is this financing plan okay?" in text
    assert "Okay / Continue" in text
    assert "Back" in text

def test_simulator_has_skip():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Simulator.tsx")
    text = p.read_text()
    assert "Skip" in text
    assert 'data-testid="sim-skip"' in text

def test_report_has_all_sections():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Report.tsx")
    text = p.read_text()
    required = [
        "GramBiz AI — Business Feasibility Report",
        "Selected Business",
        "Applicant Details",
        "Dashboard Analysis",
        "Selected Location",
        "Market Summary",
        "Market Reach",
        "Data Confidence Score",
        "Financial Plan & Profitability",
        "EMI Calculation",
        "Selected Scheme",
        "Executive Summary",
        "Strategic AI Advice",
        "Official GramBiz AI Declaration",
        "Watch Video to Apply Loan",
        "Download PDF",
    ]
    for sec in required:
        assert sec in text, f"Report missing section: {sec}"
    assert "Copy Link" not in text
    assert "QR" not in text

def test_routing_guards_exist():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/App.tsx")
    text = p.read_text()
    assert "RequireAnalysis" in text
    assert "RequireBusinessSetup" in text
    assert "RequireFinanceEligible" in text
    assert "RequireFinance" in text
    assert "RequireReport" in text
    assert "/compare" not in text
    assert "/data-sources" not in text

def test_sidebar_no_compare_or_datasource():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/components/layout/Sidebar.tsx")
    text = p.read_text()
    assert "/compare" not in text
    assert "/data-sources" not in text
    assert "navCompare" not in text
    assert "navData" not in text

def test_analysis_store_extended():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/lib/analysisStore.tsx")
    text = p.read_text()
    assert "businessSetupConfirmed" in text
    assert "applicantDetails" in text
    assert "applicantAge" in text
    assert "eligibilityResult" in text
    assert "clearJourney" in text

def test_no_emi_reminder_ui():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Finance.tsx")
    text = p.read_text()
    assert "CalendarReminders" not in text
    p2 = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/components/CalendarReminders.tsx")
    assert "return null" in p2.read_text()

def test_market_go_on_and_radius():
    import pathlib
    p = pathlib.Path("/home/thiyan/projects/sih/grambiz-ai/apps/web/src/pages/Market.tsx")
    text = p.read_text()
    assert "Go On" in text
    assert "radiusKm" in text
    assert "radius_km" in text

def test_history_immutability(session):
    # Use locations that exist in test DB (Perundurai and Sathyamangalam are seeded)
    from app.schemas import AnalysisRequest
    req1 = AnalysisRequest(state="Tamil Nadu", district="Erode", block="Perundurai", village="Perundurai", capital_available=100000, category_code="dairy", preferred_scale="small")
    _, run1 = run_analysis(session, req1)
    id1 = run1.id
    req2 = AnalysisRequest(state="Tamil Nadu", district="Erode", block="Sathyamangalam", village="Sathyamangalam", capital_available=150000, category_code="grocery", preferred_scale="small")
    _, run2 = run_analysis(session, req2)
    # Fetch history
    from app.db.models import AnalysisRun
    from sqlalchemy import select
    runs = list(session.execute(select(AnalysisRun).where(AnalysisRun.id.in_([id1, run2.id]))).scalars())
    assert len(runs) == 2
    # Old report should still be retrievable
    old = session.get(AnalysisRun, id1)
    assert old is not None
    assert old.result["location"]["village"] == "Perundurai"

