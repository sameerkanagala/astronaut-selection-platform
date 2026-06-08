"""
Fictional astronaut candidate profiles for the Agentic AI Candidate Selection POC.
All names, data, and profiles are entirely fabricated for demonstration purposes.
Domain: Interstellar Exploration Agency (IEA) — Group 7 Candidate Class
"""
from .models import Application

APPLICATIONS = [

    Application(
        id="IEA-001",
        name="Dr. Sarah Chen",
        age=37,
        nationality="American",
        stem_field="Aerospace Engineering",
        candidate_level="Group 7 Finalist",
        military_background=True,
        flight_hours=2450,
        advanced_degrees=2,
        physical_fitness_score=94.0,
        medical_clearance="Full",
        specializations=["EVA Operations", "Propulsion Systems", "Navigation"],
        prior_missions=1,
        awards=["Distinguished Flying Cross", "NASA Group Achievement Award"],
        personal_statement=(
            "After twelve years as a test pilot and two as a flight instructor, I applied to the IEA "
            "because I believe the next chapter of human exploration demands people who can operate "
            "at the intersection of engineering precision and adaptive decision-making under uncertainty. "
            "My doctoral research on cryogenic fuel systems directly supports long-duration mission architecture. "
            "I thrive in high-stakes, time-compressed environments — not despite the pressure, but because "
            "clear thinking under pressure is a skill I have spent a career deliberately building. "
            "I am ready for this mission."
        ),
        psychological_profile=(
            "Candidate demonstrates exceptional stress tolerance and disciplined problem decomposition. "
            "Group simulation performance ranked in the top 5% of cohort. Strong situational awareness. "
            "Collaborative leadership style; observed de-escalating crew tension effectively in scenario 4."
        ),
    ),

    Application(
        id="IEA-002",
        name="Marcus Webb",
        age=34,
        nationality="British",
        stem_field="Geology & Planetary Science",
        candidate_level="Group 7 Candidate",
        military_background=False,
        flight_hours=820,
        advanced_degrees=2,
        physical_fitness_score=78.5,
        medical_clearance="Full",
        specializations=["Sample Collection", "Remote Sensing"],
        prior_missions=0,
        awards=["Royal Geographical Society Research Prize"],
        personal_statement=(
            "My fieldwork in volcanic rift zones and sub-Arctic permafrost has given me experience that "
            "translates directly to planetary surface operations. I understand isolation, equipment failure, "
            "and working in hostile environments with limited resupply. I am a scientist who learned to fly "
            "because I wanted to go where the best samples are. Space is where the best samples are."
        ),
        psychological_profile=(
            "Candidate is intellectually driven and highly motivated. Performs well on independent tasks. "
            "Some hesitation observed in collaborative pressure scenarios — recommends additional crew "
            "resource management training before mission assignment."
        ),
    ),

    Application(
        id="IEA-003",
        name="Dr. Elena Vasquez",
        age=41,
        nationality="Mexican",
        stem_field="Emergency Medicine & Human Physiology",
        candidate_level="Group 7 Candidate",
        military_background=False,
        flight_hours=310,
        advanced_degrees=2,
        physical_fitness_score=81.0,
        medical_clearance="Full",
        specializations=["Medical Operations", "Life Support Systems"],
        prior_missions=0,
        awards=["WHO Global Health Leadership Award", "Medecins Sans Frontieres Service Medal"],
        personal_statement=(
            "I have performed surgery in a field hospital during a category 5 hurricane and managed "
            "a disease outbreak in a remote mountain community with no external communication for 11 days. "
            "The physical and psychological demands of space medicine are not abstractions to me — they are "
            "engineering problems I have been solving under pressure my entire career. I bring skills no "
            "amount of simulation can replicate. I also intend to get my flight hours up."
        ),
        psychological_profile=(
            "Outstanding composure under ambiguity. Demonstrates rare ability to communicate calm confidence "
            "to a team while managing complex parallel tasks. Essay quality high — coherent, specific, "
            "and honest about limitations. Strong crew medicine candidate."
        ),
    ),

    Application(
        id="IEA-004",
        name="James Okafor",
        age=38,
        nationality="Nigerian-American",
        stem_field="Robotics & Systems Engineering",
        candidate_level="Group 7 Candidate",
        military_background=True,
        flight_hours=1650,
        advanced_degrees=1,
        physical_fitness_score=88.0,
        medical_clearance="Full",
        specializations=["Robotic Arm Operations", "EVA Operations", "Systems Repair"],
        prior_missions=0,
        awards=["Air Force Commendation Medal", "IEEE Young Engineer Award"],
        personal_statement=(
            "I spent six years maintaining and piloting aircraft in environments where a mechanical fault "
            "meant lives lost, and five years after that building the robotic systems that inspect the places "
            "humans cannot safely reach. I have spent my career solving problems at the boundary of "
            "human and machine capability. That boundary is exactly where space operations live."
        ),
        psychological_profile=(
            "Technically confident, methodical under pressure. Excels in structured problem-solving scenarios. "
            "Leadership scores above cohort average. Adapts well to ambiguity when given initial parameters. "
            "Recommended for technical mission roles."
        ),
    ),

    Application(
        id="IEA-005",
        name="Dr. Priya Sharma",
        age=44,
        nationality="Indian",
        stem_field="Astrophysics",
        candidate_level="Group 7 Candidate",
        military_background=False,
        flight_hours=180,
        advanced_degrees=3,
        physical_fitness_score=72.0,
        medical_clearance="Conditional",
        specializations=["Telescope Operations", "Data Analysis"],
        prior_missions=0,
        awards=["Kavli Prize in Astrophysics", "ISRO Distinguished Scientist Award"],
        personal_statement=(
            "I have dedicated 20 years to understanding the universe from the ground. I want to understand "
            "it from space. My conditional medical clearance relates to a fully managed thyroid condition "
            "that has not affected my performance in any simulation or physical assessment. I acknowledge "
            "the flight hours gap and have enrolled in an accelerated programme. I bring scientific "
            "capability that is genuinely rare in this candidate class."
        ),
        psychological_profile=(
            "Highly motivated, exceptional scientific credentials. Realistic and self-aware about gaps. "
            "Psychological resilience scores strong despite limited operational background. "
            "Conditional clearance and low flight hours are the primary risk factors for this cycle."
        ),
    ),

    Application(
        id="IEA-006",
        name="Tom Briggs",
        age=39,
        nationality="Australian",
        stem_field="Aeronautical Engineering",
        candidate_level="Group 7 Candidate",
        military_background=True,
        flight_hours=3280,
        advanced_degrees=1,
        physical_fitness_score=96.5,
        medical_clearance="Full",
        specializations=["Test Flight Operations", "Emergency Procedures"],
        prior_missions=0,
        awards=["Chief of Air Force Commendation", "RAAF Test Pilot of the Year"],
        personal_statement=(
            "I fly. That is what I do. I have 3,280 hours across 34 aircraft types including "
            "experimental platforms that have never entered production. I have ejected once and "
            "landed a single-engine aircraft with total hydraulic failure twice. I know what calm "
            "looks like in a cockpit when everything is wrong. I want to bring that to space."
        ),
        psychological_profile=(
            "Peak physical and operational readiness. Personal statement is brief and functional — "
            "reflects operational rather than reflective personality type. Low verbosity in written "
            "assessments does not reflect low depth; interview scores were among the highest in the cohort. "
            "Recommend structured crew dynamics pairing."
        ),
    ),

    Application(
        id="IEA-007",
        name="Yuki Tanaka",
        age=36,
        nationality="Japanese",
        stem_field="Materials Science & Structural Engineering",
        candidate_level="Group 7 Candidate",
        military_background=False,
        flight_hours=590,
        advanced_degrees=2,
        physical_fitness_score=83.0,
        medical_clearance="Full",
        specializations=["Structural Analysis", "EVA Operations"],
        prior_missions=0,
        awards=["JAXA Technical Excellence Award"],
        personal_statement=(
            "I have spent eight years designing materials that fail gracefully — that absorb damage and "
            "maintain structural integrity at the margins of tolerance. I think about systems at the "
            "point where they break. That mindset is, I believe, exactly what is needed in a mission "
            "environment where there is no maintenance depot and no second chance. I am also completing "
            "an accelerated flight programme and expect to reach 1,000 hours within 14 months."
        ),
        psychological_profile=(
            "Methodical, precise, and deeply knowledgeable in structural failure analysis. Simulation "
            "performance strong in technical scenarios. Flight hours are below mission threshold but "
            "candidate is actively addressing this. Psychological profile: calm, steady, "
            "low emotional volatility under sustained pressure."
        ),
    ),

    Application(
        id="IEA-008",
        name="Carlos Mendez",
        age=42,
        nationality="Colombian-American",
        stem_field="Naval Aviation & Oceanography",
        candidate_level="Group 7 Finalist",
        military_background=True,
        flight_hours=1920,
        advanced_degrees=1,
        physical_fitness_score=91.0,
        medical_clearance="Full",
        specializations=["Navigation", "EVA Operations", "Emergency Procedures"],
        prior_missions=2,
        awards=["Navy Cross", "Defense Superior Service Medal", "IEA Service Commendation"],
        personal_statement=(
            "I have served two tours aboard aircraft carriers, flown combat missions over three continents, "
            "and spent 186 days on the International Space Station during Expedition 64. Space is not "
            "new to me — but what I want to do next is. I am applying for the deep-space programme "
            "because I believe the skills I built in the most demanding environments on Earth and in "
            "low Earth orbit have prepared me to go further. I am ready."
        ),
        psychological_profile=(
            "Exceptional operational track record. Prior mission performance scored in the 97th percentile "
            "for crew adaptability and technical execution. Strong leadership presence. A natural anchor "
            "for crew cohesion on long-duration missions. High-confidence selection."
        ),
    ),

    Application(
        id="IEA-009",
        name="Dr. Aisha Nkosi",
        age=40,
        nationality="South African",
        stem_field="Neuroscience & Cognitive Systems",
        candidate_level="Group 7 Candidate",
        military_background=False,
        flight_hours=145,
        advanced_degrees=2,
        physical_fitness_score=76.0,
        medical_clearance="Full",
        specializations=["Human Factors", "Cognitive Performance Monitoring"],
        prior_missions=1,
        awards=["South African Science and Technology Award", "IEA Payload Specialist Commendation"],
        personal_statement=(
            "My prior mission as payload specialist taught me that the difference between a good crew "
            "and a great crew is not technical — it is cognitive. I study how human decision-making "
            "degrades under isolation, fatigue, and high stakes, and I know how to design interventions "
            "that preserve it. I am applying for a mission role because I want to apply that science "
            "from inside the system, not from a control room 400 kilometres below it."
        ),
        psychological_profile=(
            "Unique profile: low flight hours but genuine prior mission experience as payload specialist. "
            "Cognitive performance research background adds rare crew-level value. Psychological "
            "assessment scores in the 91st percentile. Flight hours remain the primary gap for "
            "a mission-critical seat; strong candidate for science crew roles."
        ),
    ),

    Application(
        id="IEA-010",
        name="Rachel Kim",
        age=33,
        nationality="Korean-American",
        stem_field="Systems Engineering & Computer Science",
        candidate_level="Group 7 Candidate",
        military_background=True,
        flight_hours=1120,
        advanced_degrees=1,
        physical_fitness_score=86.0,
        medical_clearance="Full",
        specializations=["Flight Software", "Systems Integration", "Navigation"],
        prior_missions=0,
        awards=["Air Force Achievement Medal"],
        personal_statement=(
            "I spent four years writing the flight software that keeps aircraft stable when the pilot "
            "cannot. Then I flew those aircraft to understand what I had built from the other side of the "
            "glass. I think in systems — how components interact, where dependencies create fragility, "
            "and how to design resilience into architectures that cannot be patched mid-flight. "
            "That is exactly the mindset a spacecraft needs."
        ),
        psychological_profile=(
            "Technically strong, growth-oriented mindset. Scores well on adaptive reasoning tasks. "
            "Personal statement is clear and grounded — does not oversell. Physical and technical "
            "credentials are solid for this stage. A well-rounded candidate at the early career point "
            "of the experience curve."
        ),
    ),
]
