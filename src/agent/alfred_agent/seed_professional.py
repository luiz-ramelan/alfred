import os
import google.cloud.firestore
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


WORK_CONTACTS = [
    # --- Colleagues (Wayne Enterprises) ---
    {
        "name": "Lucius Fox",
        "category": "colleague",
        "role": "CEO, Wayne Enterprises (Applied Sciences)",
        "organization": "Wayne Enterprises",
        "activity": "Runs day-to-day operations and supplies the Master's specialized equipment.",
        "notes": "Trusted with the Master's full confidence.",
    },
    {
        "name": "Tim Drake",
        "category": "colleague",
        "role": "Board member / strategic intern",
        "organization": "Wayne Enterprises",
        "activity": "Special projects and long-term strategy.",
        "notes": "Family.",
    },
    {
        "name": "Tam Fox",
        "category": "colleague",
        "role": "Executive assistant to the CEO",
        "organization": "Wayne Enterprises",
        "activity": "Schedule liaison; coordinates with Lucius's office.",
        "notes": "",
    },

    # --- Business partners ---
    {
        "name": "Oliver Queen",
        "category": "business_partner",
        "role": "CEO",
        "organization": "Queen Industries",
        "activity": "Joint philanthropic ventures and R&D investment.",
        "notes": "Personal acquaintance of the Master.",
    },
    {
        "name": "Ted Kord",
        "category": "business_partner",
        "role": "CEO",
        "organization": "Kord Omniversal Research and Development",
        "activity": "R&D collaborations on advanced engineering.",
        "notes": "",
    },
    {
        "name": "Simon Stagg",
        "category": "business_partner",
        "role": "CEO",
        "organization": "Stagg Industries",
        "activity": "Competitive bidding on metropolitan contracts.",
        "notes": "Treat with caution; reputation for sharp practice.",
    },
    {
        "name": "Bruno Manheim",
        "category": "business_partner",
        "role": "Front executive (Intergang affiliated)",
        "organization": "Various front companies",
        "activity": "Approaches under guise of legitimate business.",
        "notes": "Flagged adversarial. Decline meetings.",
    },

    # --- Personnel (private staff and confidants) ---
    {
        "name": "Leslie Thompkins",
        "category": "personnel",
        "role": "Family physician",
        "organization": "Park Row Clinic",
        "activity": "Discreet medical care for the household.",
        "notes": "Long-standing trust; on-call for emergencies.",
    },
    {
        "name": "Barbara Gordon",
        "category": "personnel",
        "role": "Research and IT consultant",
        "organization": "Independent",
        "activity": "Information research and secure communications.",
        "notes": "Need-to-know. Family ally.",
    },
    {
        "name": "Selina Kyle",
        "category": "personnel",
        "role": "Private security advisor",
        "organization": "Independent",
        "activity": "Intermittent consulting on physical-security matters.",
        "notes": "Personal connection to the Master; engagements informal.",
    },
    {
        "name": "Clark Kent",
        "category": "personnel",
        "role": "Press contact",
        "organization": "Daily Planet",
        "activity": "Trusted correspondent for measured public statements.",
        "notes": "",
    },
    {
        "name": "James Gordon",
        "category": "personnel",
        "role": "Police Commissioner",
        "organization": "Gotham City Police Department",
        "activity": "Civic liaison and emergency coordination.",
        "notes": "Direct line for matters of public safety.",
    },
]


def seed_professional():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "alfred-492407")
    db = google.cloud.firestore.Client(project=project_id)

    household_ref = db.collection("households").document("default")
    household_ref.set(
        {
            "work_contacts": WORK_CONTACTS,
            "last_updated": datetime.now(timezone.utc),
        },
        merge=True,
    )
    print(
        f"--- Seeded 'households/default.work_contacts' "
        f"({len(WORK_CONTACTS)} contacts) for project {project_id} ---"
    )


if __name__ == "__main__":
    seed_professional()
