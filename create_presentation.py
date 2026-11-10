import os
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt

# Paths
PROJECT_ROOT = Path(__file__).parent
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTPUT_PPTX = PROJECT_ROOT / "Project_Presentation.pptx"

# Helper to add a slide with title and optional bullet points and image
def add_slide(prs, layout_idx, title_text, bullet_points=None, image_path=None):
    slide = prs.slides.add_slide(prs.slide_layouts[layout_idx])
    title = slide.shapes.title
    title.text = title_text
    if bullet_points:
        # Use the content placeholder (usually index 1) for body text
        body = slide.shapes.placeholders[1]
        tf = body.text_frame
        for i, point in enumerate(bullet_points):
            if i == 0:
                tf.text = point
            else:
                p = tf.add_paragraph()
                p.text = point
                p.level = 0
                p.font.size = Pt(14)
    if image_path:
        # Insert image on the right side of the slide
        left = Inches(5)  # adjust as needed
        top = Inches(1.5)
        height = Inches(4.5)
        slide.shapes.add_picture(str(image_path), left, top, height=height)
    return slide

# Create presentation
prs = Presentation()

# Slide 1: Title slide (layout 0)
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Centralized Cloud Blood Bank & Emergency Registry"
subtitle = slide.placeholders[1]
subtitle.text = "Academic Project Presentation\nGenerated automatically"

# Slide 2: Problem Statement
add_slide(
    prs,
    layout_idx=1,
    title_text="Problem Statement",
    bullet_points=[
        "Blood banks and hospitals operate in isolation, causing delays during emergencies.",
        "Lack of real‑time inventory visibility across organizations.",
        "Need for a coordinated platform to share blood inventory and emergency requests.",
    ],
)

# Slide 3: Solution Overview
add_slide(
    prs,
    layout_idx=1,
    title_text="Solution Overview",
    bullet_points=[
        "Web‑based cloud platform for blood bank inventory management.",
        "Emergency request registry with auto‑refresh and escalation.",
        "Role‑based access (Admin, Blood Bank, Hospital).",
        "Sync between local SQLite and PostgreSQL for cloud readiness.",
    ],
)

# Slide 4: Technology Stack
add_slide(
    prs,
    layout_idx=1,
    title_text="Technology Stack",
    bullet_points=[
        "Python 3.11+",
        "Streamlit – UI front‑end",
        "FastAPI – REST API (OpenAPI docs at /docs)",
        "SQLAlchemy ORM – SQLite (dev) / PostgreSQL (cloud)",
        "Docker Compose – multi‑service deployment",
        "GitHub Actions – CI/CD with pytest & coverage",
    ],
)

# Slide 5: Architecture Diagram (use placeholder image of architecture if available)
arch_img = ASSETS_DIR / "01_homepage.png"  # using homepage as placeholder for now
add_slide(
    prs,
    layout_idx=1,
    title_text="Architecture",
    bullet_points=[
        "Browser ↔ Streamlit (port 8501) – presentation layer",
        "Streamlit ↔ Service layer – business logic",
        "FastAPI (port 8000) – API layer, JWT auth",
        "SQLAlchemy ↔ SQLite / PostgreSQL – persistent storage",
    ],
    image_path=arch_img,
)

# Slide 6: Login & Home UI
add_slide(
    prs,
    layout_idx=1,
    title_text="Login & Home UI",
    bullet_points=["Demo accounts provided for Admin, Blood Bank and Hospital.", "Secure password hashing with bcrypt."],
    image_path=ASSETS_DIR / "01_login_validation.png",
)

# Slide 7: Hospital Registration
add_slide(
    prs,
    layout_idx=1,
    title_text="Hospital Registration",
    bullet_points=["Register hospitals with location data for geospatial search."],
    image_path=ASSETS_DIR / "02_hospital_registered.png",
)

# Slide 8: Hospital Dashboard
add_slide(
    prs,
    layout_idx=1,
    title_text="Hospital Dashboard",
    bullet_points=["View own requests, inventory status, and alerts."],
    image_path=ASSETS_DIR / "03_hospital_dashboard.png",
)

# Slide 9: Emergency Request Registry
add_slide(
    prs,
    layout_idx=1,
    title_text="Emergency Request Registry",
    bullet_points=["Create, track, and cancel emergency requests.", "Auto‑refresh every 15 s, overdue badge, escalation radius."],
    image_path=ASSETS_DIR / "04_emergency_request_created.png",
)

# Slide 10: Blood Bank Search
add_slide(
    prs,
    layout_idx=1,
    title_text="Blood Bank Search",
    bullet_points=["Geolocation‑based search with distance filter.", "Live inventory view by blood group and city."],
    image_path=ASSETS_DIR / "05_blood_bank_search.png",
)

# Slide 11: Admin Dashboard
add_slide(
    prs,
    layout_idx=1,
    title_text="Admin Dashboard",
    bullet_points=["Overall metrics, charts, and alerts across all organizations."],
    image_path=ASSETS_DIR / "07_admin_dashboard.png",
)

# Slide 12: Blood Inventory Management
add_slide(
    prs,
    layout_idx=1,
    title_text="Blood Inventory Management",
    bullet_points=["Lot creation, expiry tracking, FEFO workflow.", "Atomic reservations to avoid overselling."],
    image_path=ASSETS_DIR / "08_blood_inventory.png",
)

# Slide 13: Donor Registry
add_slide(
    prs,
    layout_idx=1,
    title_text="Donor Registry",
    bullet_points=["Voluntary donor registration and appointment booking.", "Eligibility checks (56‑day rule)."],
    image_path=ASSETS_DIR / "09_donor_registry.png",
)

# Slide 14: Reports & Forecasting
add_slide(
    prs,
    layout_idx=1,
    title_text="Reports & Forecasting",
    bullet_points=["CSV exports, printable HTML, demand trend charts (Plotly)."],
    image_path=ASSETS_DIR / "10_reports_and_forecasting.png",
)

# Slide 15: CI / CD Pipeline
add_slide(
    prs,
    layout_idx=1,
    title_text="CI / CD Pipeline",
    bullet_points=[
        "GitHub Actions workflow runs pytest with coverage.",
        "Fails if coverage < 80 %.",
        "Docker build verified on each push.",
    ],
)

# Slide 16: Deployment Options
add_slide(
    prs,
    layout_idx=1,
    title_text="Deployment Options",
    bullet_points=[
        "Local development with virtualenv and Docker Compose.",
        "Streamlit Community Cloud (SQLite → PostgreSQL for persistence).",
        "Self‑hosted Docker on any cloud provider.",
    ],
)

# Slide 17: Future Work
add_slide(
    prs,
    layout_idx=1,
    title_text="Future Work",
    bullet_points=[
        "Real‑time notifications via websockets.",
        "Role‑based multi‑tenant scalability.",
        "Integration with external blood‑bank networks.",
        "Enhanced security (OAuth, 2FA).",
    ],
)

# Slide 18: Contact / Q&A
add_slide(
    prs,
    layout_idx=1,
    title_text="Contact / Q&A",
    bullet_points=["GitHub: https://github.com/<your‑username>/blood-bank-cloud",
                   "Demo credentials are in README.md.",
                   "Feel free to raise issues or contribute!"],
)

# Save presentation
prs.save(str(OUTPUT_PPTX))
print(f"Presentation saved to {OUTPUT_PPTX}")
