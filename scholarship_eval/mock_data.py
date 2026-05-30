"""
Simulated scholarship applications — 10 high school seniors (or equivalent)
applying for college. Profiles span all confidence tiers and all three outcomes.
"""
from .models import Application

APPLICATIONS: list[Application] = [

    # ── 1. Strong candidate — HIGH confidence APPROVED ───────────────────────
    Application(
        id="APP-001",
        name="Sofia Marchetti",
        age=18,
        gpa=3.95,
        major="Intended: Biomedical Engineering",
        year="High School Senior",
        annual_household_income=34_000,
        dependents=3,
        essay=(
            "Growing up as the eldest of four children in a single-parent household, "
            "I learned early that resources are finite but determination is not. While my "
            "mother worked two jobs, I managed evening homework sessions for my younger "
            "siblings and maintained a 3.95 GPA throughout high school. Last summer I "
            "volunteered at a free clinic where I shadowed a physician and helped patients "
            "navigate appointment scheduling. That experience crystallised my goal: to study "
            "biomedical engineering and design low-cost diagnostic devices for underserved "
            "communities. Without this scholarship, I will need to defer enrollment to work "
            "full-time for a year. With it, I can begin the path toward that mission "
            "immediately. I do not take that opportunity for granted."
        ),
        extracurriculars=[
            "STEM Club (founder and president)",
            "Volunteer, Community Free Clinic — 180 hours",
            "Peer tutoring programme — 3 years",
        ],
        work_experience="Part-time cashier, 15 hrs/week throughout junior and senior year",
        recommendation_summary=(
            "Mr. Torres, AP Biology teacher, describes Sofia as 'the most driven student "
            "I have taught in 22 years.' He highlights her ability to explain complex concepts "
            "to peers and her genuine commitment to community health. Unreserved recommendation."
        ),
        awards=["Valedictorian", "National Merit Commended Scholar", "State Science Fair — 2nd Place"],
    ),

    # ── 2. Borderline — MEDIUM confidence WAITLISTED ─────────────────────────
    Application(
        id="APP-002",
        name="Marcus Thompson",
        age=18,
        gpa=3.20,
        major="Intended: Political Science / Pre-Law",
        year="High School Senior",
        annual_household_income=52_000,
        dependents=1,
        essay=(
            "My junior year was supposed to be my strongest. Instead, I spent four months "
            "driving my father to chemotherapy appointments three times a week. My GPA dropped "
            "from a 3.6 to a 2.9 that year — a dip my transcript does not fully explain. "
            "This year I rebuilt my average to 3.5 in the second semester and was accepted "
            "to two universities. I want to study political science and eventually become a "
            "public defender. I have spent two summers volunteering with a reentry programme "
            "for formerly incarcerated youth and know firsthand how much legal representation "
            "matters. This scholarship would allow me to focus on my studies rather than "
            "working 30 hours a week to contribute to household expenses."
        ),
        extracurriculars=[
            "Mock Trial team (captain, senior year)",
            "Reentry programme volunteer — 2 summers",
            "First-generation college student mentor",
        ],
        work_experience="Grocery store stock associate, 30 hrs/week (junior and senior year)",
        recommendation_summary=(
            "Ms. Walsh, AP Government teacher, notes Marcus's exceptional analytical writing "
            "and the context behind his junior-year grades. She acknowledges the dip but calls "
            "his recovery 'remarkable under the circumstances.' Strong recommendation."
        ),
        awards=["Regional Mock Trial — Outstanding Advocate"],
    ),

    # ── 3. Weak candidate — HIGH confidence DECLINED ─────────────────────────
    Application(
        id="APP-003",
        name="Tyler Brooks",
        age=18,
        gpa=2.45,
        major="Undecided",
        year="High School Senior",
        annual_household_income=120_000,
        dependents=0,
        essay=(
            "I want to go to college because I think it will help me get a good job. "
            "I am not sure what I want to study yet but I am thinking maybe business "
            "or something related to sports. My grades were not great but I have been "
            "improving. I enjoy hanging out with my friends and playing video games. "
            "I think I deserve this scholarship because college is expensive and everyone "
            "deserves a chance to succeed."
        ),
        extracurriculars=[],
        work_experience=None,
        recommendation_summary=(
            "School counselor provides a brief form letter noting Tyler 'attends class "
            "regularly and is polite.' No specific academic strengths or achievements cited."
        ),
        awards=[],
    ),

    # ── 4. Ambiguous gap year — LOW confidence, human-led ────────────────────
    Application(
        id="APP-004",
        name="Aisha Okonkwo",
        age=19,
        gpa=3.55,
        major="Intended: Public Health",
        year="High School Graduate (gap year)",
        annual_household_income=41_000,
        dependents=2,
        essay=(
            "I graduated high school last spring with a 3.6 GPA and deferred enrollment "
            "to care for my mother during cancer treatment. During that year I became a "
            "certified community health worker and organised a neighbourhood vaccination "
            "drive that reached over 400 residents. I now hold an acceptance at State "
            "University and am applying for this scholarship to make attendance financially "
            "possible. My gap year was not planned, but it deepened my commitment to public "
            "health more than any classroom could have. I understand my profile is "
            "unconventional and I welcome the committee's careful review."
        ),
        extracurriculars=[
            "Community Health Worker (certified during gap year)",
            "Vaccination outreach organiser — 400+ residents reached",
            "High school: Science National Honour Society",
        ],
        work_experience="Community health navigator, county health department (part-time, gap year)",
        recommendation_summary=(
            "Dr. Patel, county health department supervisor, calls Aisha 'one of the most "
            "capable community health workers I have supervised, regardless of age.' Notes "
            "the gap year was family-driven and recommends strongly."
        ),
        awards=["Community Impact Award — City Health Department (gap year)"],
    ),

    # ── 5. Strong STEM — HIGH confidence APPROVED ────────────────────────────
    Application(
        id="APP-005",
        name="Priya Nair",
        age=17,
        gpa=3.88,
        major="Intended: Computer Science",
        year="High School Senior",
        annual_household_income=29_000,
        dependents=4,
        essay=(
            "My parents immigrated from Kerala with very little, believing education was "
            "the path forward. I am the first in my family to apply to a four-year university. "
            "In tenth grade I taught myself Python using free online resources and built a "
            "multilingual benefits calculator that 600 households in my city now use to find "
            "food assistance and housing support. Last year I started a coding club at my "
            "high school that has introduced 45 students to programming. I have been accepted "
            "to a computer science programme and want to spend my career building civic "
            "technology for immigrant and low-income communities. This scholarship is the "
            "difference between attending and deferring."
        ),
        extracurriculars=[
            "Coding club founder and instructor",
            "Hackathon participant — 2 regional events",
            "School newspaper (technology editor)",
        ],
        work_experience="Informal tech support for neighbours and babysitting, ongoing",
        recommendation_summary=(
            "Ms. Chen, AP Computer Science teacher, calls Priya 'the most self-directed "
            "learner I have encountered in a high school classroom.' The benefits calculator "
            "is cited as work typically done by university students. Highest recommendation."
        ),
        awards=["Congressional App Challenge — Regional Finalist", "AP Scholar with Distinction"],
    ),

    # ── 6. Moderate candidate — MEDIUM confidence APPROVED ───────────────────
    Application(
        id="APP-006",
        name="James Kowalski",
        age=18,
        gpa=3.40,
        major="Intended: Environmental Science",
        year="High School Senior",
        annual_household_income=47_000,
        dependents=1,
        essay=(
            "I grew up two miles from a Superfund site. When I was twelve, our neighbourhood "
            "received notices about elevated lead levels in the soil. That letter is why I "
            "want to study environmental science. My freshman grades were poor — I was dealing "
            "with a family move and changing schools mid-year. Since sophomore year I have "
            "maintained a 3.7 average and independently designed a biochar experiment for our "
            "school's science fair that earned a regional award. I have been accepted to a "
            "university with a strong environmental programme and intend to pursue graduate "
            "research in soil remediation. This scholarship would cover the gap between my "
            "financial aid package and actual cost of attendance."
        ),
        extracurriculars=[
            "Environmental Club (secretary)",
            "Creek and park cleanup volunteer — 140 hours",
            "Science fair competitor — 3 years",
        ],
        work_experience="Lawn care and yard work, self-employed since age 14",
        recommendation_summary=(
            "Dr. Nguyen, AP Environmental Science teacher, highlights James's academic "
            "turnaround and his independent research instinct. Notes his biochar project "
            "showed 'genuine scientific curiosity beyond the curriculum.' Strong recommendation."
        ),
        awards=["Regional Science Fair — Best Environmental Project"],
    ),

    # ── 7. High merit, lower need — MEDIUM confidence ────────────────────────
    Application(
        id="APP-007",
        name="Claire Hoffman",
        age=17,
        gpa=3.92,
        major="Intended: Neuroscience",
        year="High School Senior",
        annual_household_income=145_000,
        dependents=0,
        essay=(
            "I am applying knowing my household income may work against me in a needs-based "
            "review. I want to make the case on merit. At 16, I joined a university "
            "neuroscience lab through a summer research programme and co-authored a paper "
            "on adolescent sleep patterns that has been accepted for publication. I plan to "
            "pursue an MD-PhD focused on early Alzheimer's detection. The scholarship funds "
            "would go entirely toward research expenses and conference travel — not living "
            "costs, which my family can cover. I believe exceptional achievement and clear "
            "scientific purpose should weigh alongside financial need."
        ),
        extracurriculars=[
            "University neuroscience lab (summer research programme, 2 years)",
            "Alzheimer's Association volunteer",
            "Science Olympiad (team captain)",
        ],
        work_experience="Research assistant, university lab (unpaid, summers)",
        recommendation_summary=(
            "Dr. Osei, university lab supervisor, calls Claire 'the most capable high school "
            "researcher I have mentored.' Notes the publication is genuine co-authorship. "
            "Acknowledges the financial need question but endorses strongly on academic merit."
        ),
        awards=["National Merit Scholar", "Science Olympiad — State Finalist", "Pending publication co-author"],
    ),

    # ── 8. Non-traditional GED — LOW confidence ──────────────────────────────
    Application(
        id="APP-008",
        name="Roberto Vásquez",
        age=21,
        gpa=3.70,
        major="Intended: Nursing",
        year="GED Graduate (non-traditional)",
        annual_household_income=38_000,
        dependents=3,
        essay=(
            "I left high school at 17 to work construction and help support my family after "
            "my father was injured on the job. At 20 I completed my GED with a 3.7 weighted "
            "score and was accepted into a nursing programme starting this fall. My father "
            "died last year from a preventable complication because no one on his care team "
            "spoke Spanish. I want to be the bilingual nurse who closes that gap. I have "
            "spent the past year volunteering as a patient navigator at a community clinic "
            "and the staff there encouraged me to pursue nursing formally. I know my path "
            "here was not straight. I believe it makes me a better candidate for this work, "
            "not a worse one."
        ),
        extracurriculars=[
            "Spanish-language patient navigator, community clinic (volunteer)",
            "Construction crew lead — managed 3-person team",
        ],
        work_experience="Construction worker, full-time 3 years; patient navigator, part-time 1 year",
        recommendation_summary=(
            "Clinic director emphasises Roberto's empathy, language skills, and reliability. "
            "Notes his non-traditional background is an asset for community health work. "
            "Enthusiastic recommendation with candid acknowledgement that standard rubric "
            "criteria may undervalue this profile."
        ),
        awards=["GED with Distinction — Adult Education Programme"],
    ),

    # ── 9. Solid all-rounder — HIGH confidence APPROVED ──────────────────────
    Application(
        id="APP-009",
        name="Destiny Washington",
        age=18,
        gpa=3.75,
        major="Intended: Social Work",
        year="High School Senior",
        annual_household_income=31_000,
        dependents=2,
        essay=(
            "I have been in the foster care system since I was nine. I aged out at eighteen "
            "and enrolled in my senior year of high school six weeks later. I graduated with "
            "a 3.75 GPA, was accepted to three universities, and was told by my placement "
            "social worker that I was 'one of the success stories.' I do not feel like a "
            "success story. I feel like someone who did not have enough support and got lucky. "
            "I want to study social work so I can redesign the systems that failed me and the "
            "other kids I grew up alongside. I have published an op-ed on foster care reform "
            "in our city newspaper and co-founded a peer mentorship group for current foster "
            "youth. This scholarship means I can attend university without debt that would "
            "force me into private practice instead of public service."
        ),
        extracurriculars=[
            "Foster Youth Peer Mentorship Network (co-founder)",
            "Big Brothers Big Sisters — youth mentor",
            "School newspaper (opinion editor)",
        ],
        work_experience="Part-time retail, 20 hrs/week (senior year)",
        recommendation_summary=(
            "Ms. Rivera, school counselor, calls Destiny 'the most resilient and purposeful "
            "student I have worked with in 15 years.' Highlights the op-ed, the mentorship "
            "programme, and the context of aging out of foster care while maintaining academic "
            "excellence. Strongest possible recommendation."
        ),
        awards=["Published op-ed — City Newspaper", "NASW Youth Leadership Award"],
    ),

    # ── 10. Vague / incomplete — MEDIUM confidence DECLINED ──────────────────
    Application(
        id="APP-010",
        name="Devon Calloway",
        age=18,
        gpa=3.10,
        major="Intended: Business",
        year="High School Senior",
        annual_household_income=55_000,
        dependents=0,
        essay=(
            "I want to go to college to study business and eventually start my own company. "
            "I have always been interested in entrepreneurship. I work at a coffee shop and "
            "have learned a lot about customer service. I think with the right education "
            "I can achieve my goals. My grades are decent and I am a hard worker. I believe "
            "I would make good use of this scholarship."
        ),
        extracurriculars=["Intramural basketball", "School pep club"],
        work_experience="Barista, part-time (1 year)",
        recommendation_summary=(
            "School counselor provides a brief letter noting Devon 'is a pleasant student "
            "who shows up on time and works well with others.' No specific achievements, "
            "leadership experiences, or academic strengths are cited. Letter appears "
            "template-generated."
        ),
        awards=[],
    ),
]
