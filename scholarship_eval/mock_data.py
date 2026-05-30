"""
Simulated scholarship applications — 10 diverse candidates spanning
all confidence tiers (high / medium / low) and all outcomes.
"""
from .models import Application

APPLICATIONS: list[Application] = [

    # ── 1. Strong candidate — expected HIGH confidence APPROVED ──────────────
    Application(
        id="APP-001",
        name="Sofia Marchetti",
        age=20,
        gpa=3.95,
        major="Biomedical Engineering",
        year="Junior",
        annual_household_income=34_000,
        dependents=3,
        essay=(
            "Growing up as the eldest of four children in a single-parent household, "
            "I learned early that resources are finite but determination is not. My mother "
            "worked two jobs while I managed evening homework sessions for my siblings. "
            "This experience shaped my commitment to biomedical engineering — I want to "
            "design low-cost diagnostic devices for underserved communities. Last summer "
            "I interned at a nonprofit hospital where I prototyped a $12 pulse oximeter "
            "that is now in clinical trials in rural Guatemala. I plan to use this "
            "scholarship to fund my senior capstone, which extends that project to "
            "neonatal monitoring. My goal is to prove that life-saving technology need not "
            "be a luxury."
        ),
        extracurriculars=[
            "Society of Women Engineers (chapter president)",
            "Volunteer EMT — 200+ hours",
            "STEM tutoring program founder",
        ],
        work_experience="Research assistant, Biomedical Devices Lab (2 years)",
        recommendation_summary=(
            "Dr. Reyes describes Sofia as 'the most motivated student I have supervised "
            "in 20 years.' She consistently exceeds expectations, leads peers, and "
            "demonstrates rare engineering intuition. Unreserved recommendation."
        ),
        awards=["National Merit Scholar", "Dean's List (5 semesters)", "NSF REU Award"],
    ),

    # ── 2. Borderline case — expected MEDIUM confidence WAITLISTED ────────────
    Application(
        id="APP-002",
        name="Marcus Thompson",
        age=22,
        gpa=3.20,
        major="Political Science",
        year="Senior",
        annual_household_income=52_000,
        dependents=1,
        essay=(
            "I transferred from community college after two years of full-time work to "
            "support my family following my father's illness. My GPA does not fully "
            "reflect my capability — my first semester back I earned a 3.8 while managing "
            "20 hours per week of caregiving. I am passionate about criminal justice reform "
            "and have spent three years volunteering with a reentry program for formerly "
            "incarcerated youth. After graduation I plan to attend law school. This "
            "scholarship would allow me to reduce my work hours and focus on my thesis, "
            "which examines disparities in juvenile sentencing."
        ),
        extracurriculars=[
            "Prison reentry volunteer program",
            "Mock trial team",
            "First-generation student mentor",
        ],
        work_experience="Paralegal intern, Public Defender's Office (1 year)",
        recommendation_summary=(
            "Professor Walsh notes Marcus's exceptional analytical writing and genuine "
            "commitment to social justice, but acknowledges inconsistent early grades. "
            "Strong recommendation with context provided."
        ),
        awards=["Transfer Student Achievement Award"],
    ),

    # ── 3. Weak candidate — expected HIGH confidence DECLINED ────────────────
    Application(
        id="APP-003",
        name="Tyler Brooks",
        age=19,
        gpa=2.45,
        major="Undecided",
        year="Freshman",
        annual_household_income=120_000,
        dependents=0,
        essay=(
            "I want this scholarship because college is expensive and I could use the "
            "money. I enjoy playing video games and hanging out with friends. I haven't "
            "decided on a major yet but I'm thinking maybe business or something. "
            "My grades weren't great in high school but I'm hoping they will improve. "
            "I think I deserve this scholarship because everyone deserves a chance."
        ),
        extracurriculars=[],
        work_experience=None,
        recommendation_summary=(
            "Guidance counselor provides a generic letter noting Tyler is 'a pleasant "
            "student who attends class regularly.' No specific achievements cited."
        ),
        awards=[],
    ),

    # ── 4. Ambiguous — expected LOW confidence, human-led ────────────────────
    Application(
        id="APP-004",
        name="Aisha Okonkwo",
        age=23,
        gpa=3.55,
        major="Public Health",
        year="Senior",
        annual_household_income=41_000,
        dependents=2,
        essay=(
            "My application is unconventional. I took a two-year leave of absence to care "
            "for my mother through cancer treatment. During that time I became a certified "
            "community health worker and organized a neighborhood vaccination drive that "
            "reached 400 residents. I returned to university last year with renewed purpose. "
            "My academic record reflects a tale of two periods — a 2.9 before my leave and "
            "a 3.9 since returning. I believe my lived experience strengthens my capacity "
            "to serve communities. However, I understand reviewers may weigh my full GPA "
            "differently. I am asking for this scholarship to complete my MPH applications "
            "and attend a global health conference where I have an accepted abstract."
        ),
        extracurriculars=[
            "Community Health Worker (certified)",
            "Vaccination outreach organizer",
            "University Global Health Club",
        ],
        work_experience="Community health navigator, county health department (part-time)",
        recommendation_summary=(
            "Dr. Patel notes a dramatic academic turnaround and exceptional community "
            "health work, but flags the two-year gap and split GPA as factors requiring "
            "holistic review. Recommends with caveats."
        ),
        awards=["Community Impact Award — City Health Department"],
    ),

    # ── 5. Strong STEM candidate — expected HIGH confidence APPROVED ──────────
    Application(
        id="APP-005",
        name="Priya Nair",
        age=21,
        gpa=3.88,
        major="Computer Science",
        year="Junior",
        annual_household_income=29_000,
        dependents=4,
        essay=(
            "My parents immigrated from Kerala with $800 and a belief in education. "
            "I am the first in my family to attend a four-year university. I study "
            "computer science because I want to build tools that help people like my "
            "parents navigate bureaucratic systems — tax filing, visa renewals, benefits "
            "enrollment. I have already built a free multilingual benefits calculator "
            "used by 1,200 households in our city. I lead a coding club that has taught "
            "Python to 60 high-school students from low-income backgrounds. This "
            "scholarship will fund my open-source project full time over the summer."
        ),
        extracurriculars=[
            "Coding club founder and lead instructor",
            "Hackathon organizer (3 events)",
            "University AI Ethics reading group",
        ],
        work_experience="Software engineering intern, civic tech nonprofit (2 summers)",
        recommendation_summary=(
            "Professor Chen calls Priya 'a natural systems thinker with rare social "
            "conscience.' The benefits calculator project is cited as graduate-level work "
            "done as a sophomore. Highest recommendation."
        ),
        awards=["Congressional App Challenge — Regional Winner", "Dean's List (4 semesters)"],
    ),

    # ── 6. Moderate candidate — expected MEDIUM confidence APPROVED ──────────
    Application(
        id="APP-006",
        name="James Kowalski",
        age=21,
        gpa=3.40,
        major="Environmental Science",
        year="Junior",
        annual_household_income=47_000,
        dependents=1,
        essay=(
            "I grew up near a Superfund site and watched my neighborhood deal with "
            "elevated lead levels for years. That experience made environmental science "
            "personal for me. I am conducting independent research on soil remediation "
            "using biochar, and I presented preliminary findings at a regional conference "
            "last spring. My GPA reflects a rough first year adjusting to university life, "
            "but I have maintained a 3.7 over the past four semesters. I hope to pursue "
            "a PhD and focus on environmental justice in industrial corridors."
        ),
        extracurriculars=[
            "Environmental Justice Coalition (secretary)",
            "Creek cleanup volunteer (150+ hours)",
            "Undergraduate research symposium presenter",
        ],
        work_experience="Lab assistant, Environmental Chemistry Lab (18 months)",
        recommendation_summary=(
            "Dr. Nguyen highlights James's research initiative and improvement trajectory. "
            "Notes he is 'more prepared for graduate research than most seniors.' "
            "Strong recommendation."
        ),
        awards=["Best Undergraduate Poster — Regional Environmental Conference"],
    ),

    # ── 7. Low financial need, high merit — expected MEDIUM confidence ────────
    Application(
        id="APP-007",
        name="Claire Hoffman",
        age=20,
        gpa=3.92,
        major="Neuroscience",
        year="Sophomore",
        annual_household_income=145_000,
        dependents=0,
        essay=(
            "I am applying despite knowing my family's income may disadvantage my "
            "application. My research commitment speaks for itself: I have co-authored "
            "two peer-reviewed papers on hippocampal neurogenesis as an undergraduate. "
            "I plan to pursue an MD-PhD and focus on early Alzheimer's detection. "
            "The scholarship funds would go entirely toward conference travel and "
            "research consumables — not living expenses. I believe merit should also "
            "be considered alongside need."
        ),
        extracurriculars=[
            "Neuroscience research lab (25 hrs/week)",
            "Alzheimer's Association volunteer",
            "Science Olympiad coach",
        ],
        work_experience="Undergraduate researcher (co-first author, 2 publications)",
        recommendation_summary=(
            "Dr. Osei describes Claire as 'the most productive undergraduate researcher "
            "I have ever supervised' but acknowledges the scholarship committee's "
            "financial need mandate. Strong academic endorsement."
        ),
        awards=["Phi Beta Kappa", "Outstanding Undergraduate Researcher Award"],
    ),

    # ── 8. Late-stage career changer — expected LOW confidence ───────────────
    Application(
        id="APP-008",
        name="Roberto Vásquez",
        age=35,
        gpa=3.70,
        major="Nursing",
        year="Junior",
        annual_household_income=38_000,
        dependents=3,
        essay=(
            "After 12 years as a construction foreman I returned to school to become a "
            "nurse. My father died of a preventable complication because of a language "
            "barrier with his care team. I want to be the bilingual nurse who bridges "
            "that gap. Balancing school with three children under 10 is hard. My GPA "
            "of 3.7 represents work done after 10-hour days. My clinical supervisors "
            "say I have the best patient communication skills they have seen in a "
            "pre-licensure student. I need this scholarship to replace the income I "
            "lose by reducing shifts during my final clinical rotations."
        ),
        extracurriculars=[
            "Spanish-language patient navigation volunteer",
            "Nursing students association",
        ],
        work_experience=(
            "Construction foreman (12 years); Current: part-time patient care technician"
        ),
        recommendation_summary=(
            "Clinical supervisor emphasizes Roberto's extraordinary empathy and "
            "communication, and the unusual context of his non-traditional path. "
            "Enthusiastic recommendation with note that rubric criteria may undervalue "
            "his profile."
        ),
        awards=["Clinical Excellence Recognition — University Hospital"],
    ),

    # ── 9. Solid all-rounder — expected HIGH confidence APPROVED ─────────────
    Application(
        id="APP-009",
        name="Destiny Washington",
        age=22,
        gpa=3.75,
        major="Social Work",
        year="Senior",
        annual_household_income=31_000,
        dependents=2,
        essay=(
            "I aged out of foster care at 18 and enrolled in university three weeks later. "
            "I have since built a life I'm proud of: a 3.75 GPA, a published op-ed on "
            "foster care reform in the state newspaper, and a practicum at a child welfare "
            "agency where I helped redesign their youth transition checklist. I want to "
            "become a licensed clinical social worker specializing in adolescent trauma. "
            "This scholarship would close the gap between my aid package and actual cost "
            "of attendance so I can graduate debt-free and enter public service without "
            "financial pressure forcing me toward private practice."
        ),
        extracurriculars=[
            "Foster Youth Advocacy Network (co-founder)",
            "University trauma-informed care workshop facilitator",
            "Big Brothers Big Sisters mentor",
        ],
        work_experience="Child welfare practicum intern (400 hours)",
        recommendation_summary=(
            "Field supervisor calls Destiny 'a future leader in social work' who brings "
            "lived experience and professional skill in equal measure. Strongest possible "
            "recommendation."
        ),
        awards=["NASW Student of the Year — State Chapter", "Dean's List (3 semesters)"],
    ),

    # ── 10. Incomplete / inconsistent — expected LOW confidence ──────────────
    Application(
        id="APP-010",
        name="Devon Calloway",
        age=20,
        gpa=3.10,
        major="Business Administration",
        year="Sophomore",
        annual_household_income=55_000,
        dependents=0,
        essay=(
            "I want to start a business one day. I think entrepreneurship is the key "
            "to success. I have some ideas but haven't had time to develop them. "
            "My grades are decent. I work part time at a coffee shop. I think this "
            "scholarship would be a good investment in my future. I am a hard worker "
            "and I think with the right support I could do great things."
        ),
        extracurriculars=["Intramural basketball"],
        work_experience="Barista, part-time (1 year)",
        recommendation_summary=(
            "Academic advisor provides a brief letter noting Devon 'shows up to meetings "
            "and is generally positive.' No substantive achievements or specific qualities "
            "described. Letter appears template-generated."
        ),
        awards=[],
    ),
]
