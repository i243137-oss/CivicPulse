"""
Idempotent seed script for CivicPulse database.

Loads at least 30 realistic complaints in Urdu-influenced English, spread across
all categories (water, electricity, sanitation, roads, streetlights, other).
Ensures idempotency: running this script multiple times guarantees zero duplicates.
"""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import AsyncSessionLocal
from app.models.complaint import (
    CategoryEnum,
    Complaint,
    PriorityEnum,
    StatusEnum,
)
from app.repositories.complaint_repository import ComplaintRepository

# 35 realistic complaints with Urdu-influenced English
SEED_COMPLAINTS = [
    # Water
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111101"),
        "text": "Water supply line burst near Street 12 since fajr time. Clean drinking water is flooding the street and entering ground floor houses.",
        "location": "Sector G-9/2, Street 12, Islamabad",
        "reporter_contact": "+923005550101",
        "category": CategoryEnum.WATER,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Water pipeline burst causing street flooding since morning.",
        "triaged_by": "rules",
        "triage_latency_ms": 12,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111102"),
        "text": "Severe pani shortage in Block C for three days. CDA water tanker mafia is asking 6000 rupees per tanker. Please restore government tube well.",
        "location": "Sector I-10/4, Block C, Islamabad",
        "reporter_contact": "+923215550102",
        "category": CategoryEnum.WATER,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Severe water shortage in residential block due to tube well failure.",
        "triaged_by": "rules",
        "triage_latency_ms": 15,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111103"),
        "text": "Contaminated ganda pani coming from tap with foul smell and brownish color. Children are falling sick with gastroenteritis.",
        "location": "Dhoke Paracha, Street 4, Rawalpindi",
        "reporter_contact": "+923335550103",
        "category": CategoryEnum.WATER,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Contaminated brown drinking water supply causing health issues.",
        "triaged_by": "rules",
        "triage_latency_ms": 14,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111104"),
        "text": "Water valve leak near commercial market corner. Water is seeping continuously creating dirty mud puddle for pedestrians.",
        "location": "F-6 Super Market, Islamabad",
        "reporter_contact": None,
        "category": CategoryEnum.WATER,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Valve leak fixed and pavement cleaned.",
        "triaged_by": "rules",
        "triage_latency_ms": 10,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111105"),
        "text": "Low water pressure in municipal line during scheduled morning supply hours. Second floor water tanks remain completely empty.",
        "location": "Sector G-11/1, Street 45, Islamabad",
        "reporter_contact": "+923125550105",
        "category": CategoryEnum.WATER,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.OPEN,
        "ai_summary": "Low water pressure during morning hours.",
        "triaged_by": "rules",
        "triage_latency_ms": 9,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111106"),
        "text": "Someone installed an illegal direct suction booster pump on main water line, depriving whole gali of water.",
        "location": "Sector F-10/3, Street 18, Islamabad",
        "reporter_contact": "+923015550106",
        "category": CategoryEnum.WATER,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.REJECTED,
        "ai_summary": "Duplicate complaint already filed under enquiry #429.",
        "triaged_by": "rules",
        "triage_latency_ms": 11,
    },

    # Electricity
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111107"),
        "text": "Main transformer sparking vigorously with loud explosion sound near school gate. Bijli is tripping repeatedly. Huge danger for school children.",
        "location": "Near FG Boys High School, G-7/4, Islamabad",
        "reporter_contact": "+923455550107",
        "category": CategoryEnum.ELECTRICITY,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Dangerous sparking transformer near school gate causing outages.",
        "triaged_by": "rules",
        "triage_latency_ms": 18,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111108"),
        "text": "Naked electric wire hanging very low across the road after yesterday's thunderstorm. It can touch trucks and suzuki vans passing by.",
        "location": "I.J.P Road near New Katarian stop, Rawalpindi",
        "reporter_contact": "+923155550108",
        "category": CategoryEnum.ELECTRICITY,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Low hanging high-voltage wire over busy transit road.",
        "triaged_by": "rules",
        "triage_latency_ms": 16,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111109"),
        "text": "Severe voltage fluctuation in entire street. Voltage drops to 140V then surges to 280V. Refrigerator compressor and microwave already burnt.",
        "location": "Street 9, Sector H-13, Islamabad",
        "reporter_contact": "+923345550109",
        "category": CategoryEnum.ELECTRICITY,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "High voltage fluctuation damaging household appliances.",
        "triaged_by": "rules",
        "triage_latency_ms": 14,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111110"),
        "text": "Electricity meter box on electric pole is completely open with bare wires exposed to rain water.",
        "location": "Sector G-8/1, Street 3, Islamabad",
        "reporter_contact": "+923025550110",
        "category": CategoryEnum.ELECTRICITY,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Exposed meter box secured with weatherproof casing.",
        "triaged_by": "rules",
        "triage_latency_ms": 13,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "text": "Frequent unannounced load shedding for 4 hours daily despite no official maintenance schedule from IESCO.",
        "location": "Sector E-11/2, Islamabad",
        "reporter_contact": None,
        "category": CategoryEnum.ELECTRICITY,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.OPEN,
        "ai_summary": "Unannounced power outages reported in sector E-11.",
        "triaged_by": "rules",
        "triage_latency_ms": 11,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111112"),
        "text": "Phase failure on Lane 4 since asr. Half houses have single phase while AC and water motor cannot run.",
        "location": "Lane 4, Peshawar Road, Rawalpindi",
        "reporter_contact": "+923315550112",
        "category": CategoryEnum.ELECTRICITY,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Single phase outage affecting residential power appliances.",
        "triaged_by": "rules",
        "triage_latency_ms": 12,
    },

    # Sanitation
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111113"),
        "text": "Sewage gutter overflowing right outside Jamia Masjid main gate. Namazis and elderly people cannot reach mosque without stepping in filthy water.",
        "location": "Sector F-8/1, Street 22, Islamabad",
        "reporter_contact": "+923035550113",
        "category": CategoryEnum.SANITATION,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Overflowing sewer line blocking mosque entrance.",
        "triaged_by": "rules",
        "triage_latency_ms": 15,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111114"),
        "text": "Huge heap of kachra (garbage) rotting on vacant plot near bakery. Stray dogs and flies gathering, foul smell spreading into houses.",
        "location": "Sector G-9 Markaz Karachi Company, Islamabad",
        "reporter_contact": "+923225550114",
        "category": CategoryEnum.SANITATION,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Illegal open dumping ground near commercial bakery.",
        "triaged_by": "rules",
        "triage_latency_ms": 13,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111115"),
        "text": "CDA sanitation workers have not visited our gali for over ten days. Dustbins are spilling over onto the road.",
        "location": "Street 15, Sector I-9/4, Islamabad",
        "reporter_contact": "+923445550115",
        "category": CategoryEnum.SANITATION,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Waste collection crew dispatched and bins cleared.",
        "triaged_by": "rules",
        "triage_latency_ms": 10,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111116"),
        "text": "Stormwater nullah blocked with plastic bags and construction debris. Monsoon rain will cause severe urban flooding if not de-silted immediately.",
        "location": "Near Khanna Pul, Express Highway, Rawalpindi",
        "reporter_contact": "+923135550116",
        "category": CategoryEnum.SANITATION,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Storm drain clogged with plastic waste creating flood risk.",
        "triaged_by": "rules",
        "triage_latency_ms": 17,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111117"),
        "text": "Dead animal lying on green belt sidewalk for two days, unbearable bad smell spreading throughout the neighbourhood.",
        "location": "7th Avenue near Sector G-6, Islamabad",
        "reporter_contact": None,
        "category": CategoryEnum.SANITATION,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Municipal waste disposal unit cleared green belt carcass.",
        "triaged_by": "rules",
        "triage_latency_ms": 9,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111118"),
        "text": "Garbage dump container is broken from the bottom so waste falls back onto the road whenever waste vehicle lifts it.",
        "location": "Sector F-11/4, Street 50, Islamabad",
        "reporter_contact": "+923325550118",
        "category": CategoryEnum.SANITATION,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.OPEN,
        "ai_summary": "Damaged municipal waste container requires replacement.",
        "triaged_by": "rules",
        "triage_latency_ms": 10,
    },

    # Roads
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111119"),
        "text": "Massive pothole crater on main road near metro bus pillar 42. Two motorcycle riders fell and got severely injured last night.",
        "location": "Murree Road near Rehmanabad, Rawalpindi",
        "reporter_contact": "+923055550119",
        "category": CategoryEnum.ROADS,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Dangerous deep road pothole causing motorcycle accidents.",
        "triaged_by": "rules",
        "triage_latency_ms": 16,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111120"),
        "text": "Open manhole without dhakkan (cover) in middle of dark street. Someone placed a tree branch as warning, very dangerous for pedestrians.",
        "location": "Sector G-10/3, Street 72, Islamabad",
        "reporter_contact": "+923235550120",
        "category": CategoryEnum.ROADS,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Uncovered sewer manhole on active transit street.",
        "triaged_by": "rules",
        "triage_latency_ms": 14,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111121"),
        "text": "Road dug up by gas company 3 months ago but never carpeted with asphalt. Loose gravel is flying into car windscreens and causing dust.",
        "location": "Sector F-7/1, Nazimuddin Road, Islamabad",
        "reporter_contact": "+923425550121",
        "category": CategoryEnum.ROADS,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.OPEN,
        "ai_summary": "Unrepaired utility trench leaving loose gravel on road.",
        "triaged_by": "rules",
        "triage_latency_ms": 11,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111122"),
        "text": "Illegal concrete speed breaker built by local resident without permission. It is so high that car bumpers scrape even at zero speed.",
        "location": "Street 8, Sector H-8/1, Islamabad",
        "reporter_contact": None,
        "category": CategoryEnum.ROADS,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Unauthorized oversized speed breaker removed by CDA road maintenance.",
        "triaged_by": "rules",
        "triage_latency_ms": 8,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111123"),
        "text": "Footpath completely encroached by shopkeepers placing merchandise and iron tables. Pedestrians forced to walk on busy main road.",
        "location": "Aabpara Market main strip, Sector G-6, Islamabad",
        "reporter_contact": "+923145550123",
        "category": CategoryEnum.ROADS,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.OPEN,
        "ai_summary": "Footpath encroached by commercial vendors forcing road walking.",
        "triaged_by": "rules",
        "triage_latency_ms": 12,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111124"),
        "text": "Road side retaining wall collapsing into the service lane after heavy rains.",
        "location": "Kashmir Highway near G-11 interchange, Islamabad",
        "reporter_contact": "+923355550124",
        "category": CategoryEnum.ROADS,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Retaining wall degradation along highway service lane.",
        "triaged_by": "rules",
        "triage_latency_ms": 13,
    },

    # Streetlights
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111125"),
        "text": "All streetlights on Street 7 not working for past 3 weeks. Pura mohalla andhera hai (entire area is dark) leading to mobile snatching incidents.",
        "location": "Sector I-10/2, Street 7, Islamabad",
        "reporter_contact": "+923065550125",
        "category": CategoryEnum.STREETLIGHTS,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Dark streetlights enabling street crime and theft.",
        "triaged_by": "rules",
        "triage_latency_ms": 15,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111126"),
        "text": "Streetlight pole damaged in car collision and leaning dangerously at 45 degrees towards high-tension overhead wire.",
        "location": "Corner of Street 34, Sector F-6/1, Islamabad",
        "reporter_contact": "+923245550126",
        "category": CategoryEnum.STREETLIGHTS,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Tilted metal pole at risk of contacting electrical lines.",
        "triaged_by": "rules",
        "triage_latency_ms": 14,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111127"),
        "text": "Streetlights remain switched ON during broad daylight all day long, wasting government electricity while nighttime timer is broken.",
        "location": "Sector G-10 Markaz outer perimeter, Islamabad",
        "reporter_contact": None,
        "category": CategoryEnum.STREETLIGHTS,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Faulty timer switch replaced, automatic day-night cycling restored.",
        "triaged_by": "rules",
        "triage_latency_ms": 9,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111128"),
        "text": "Three LED streetlight fixtures flickering continuously like strobe lights throughout the night, disturbing residents sleep.",
        "location": "Sector F-10/2, Street 19, Islamabad",
        "reporter_contact": "+923435550128",
        "category": CategoryEnum.STREETLIGHTS,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.OPEN,
        "ai_summary": "Malfunctioning flickering LED streetlight lamps.",
        "triaged_by": "rules",
        "triage_latency_ms": 10,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111129"),
        "text": "Request to install streetlight on newly paved blind curve corner near community park for safety of women and children.",
        "location": "Sector G-11/4 near Fatima Jinnah Park gate, Islamabad",
        "reporter_contact": "+923115550129",
        "category": CategoryEnum.STREETLIGHTS,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.REJECTED,
        "ai_summary": "Capital development scheme required; referred to annual infrastructure budget.",
        "triaged_by": "rules",
        "triage_latency_ms": 12,
    },

    # Other
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111130"),
        "text": "Pack of aggressive stray dogs attacking school children and morning walkers near public park jogging track.",
        "location": "Kachnar Park, Sector I-8/3, Islamabad",
        "reporter_contact": "+923365550130",
        "category": CategoryEnum.OTHER,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Stray dog pack posing immediate danger to park visitors.",
        "triaged_by": "rules",
        "triage_latency_ms": 13,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111131"),
        "text": "Illegal tree cutting along CDA green belt at night by private timber contractors without municipal permits.",
        "location": "Margalla Road near Sector F-8, Islamabad",
        "reporter_contact": "+923075550131",
        "category": CategoryEnum.OTHER,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.IN_PROGRESS,
        "ai_summary": "Unauthorized deforestation reported on CDA protected green belt.",
        "triaged_by": "rules",
        "triage_latency_ms": 11,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111132"),
        "text": "Severe noise pollution from illegal banquet marquee loud speakers playing loud music past 2:00 AM midnight.",
        "location": "Club Road near Rawal Lake, Islamabad",
        "reporter_contact": "+923255550132",
        "category": CategoryEnum.OTHER,
        "priority": PriorityEnum.NORMAL,
        "status": StatusEnum.OPEN,
        "ai_summary": "Violation of sound ordinance by commercial marquee.",
        "triaged_by": "rules",
        "triage_latency_ms": 10,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111133"),
        "text": "Public park children swings and slides are broken with rusted sharp iron edges sticking out.",
        "location": "Sector G-8/4 Children Park, Islamabad",
        "reporter_contact": None,
        "category": CategoryEnum.OTHER,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Playground equipment repaired and painted by horticulture directorate.",
        "triaged_by": "rules",
        "triage_latency_ms": 8,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111134"),
        "text": "Private commercial advertising banners nailed directly into trunk of heritage trees along Blue Area boulevard.",
        "location": "Jinnah Avenue, Blue Area, Islamabad",
        "reporter_contact": "+923415550134",
        "category": CategoryEnum.OTHER,
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.RESOLVED,
        "ai_summary": "Illegal advertising banners removed from green belt trees.",
        "triaged_by": "rules",
        "triage_latency_ms": 7,
    },
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111135"),
        "text": "Stagnant rainwater pool in under-construction plaza basement breeding millions of dengue mosquitoes.",
        "location": "Sector E-11/3 Markaz, Islamabad",
        "reporter_contact": "+923165550135",
        "category": CategoryEnum.OTHER,
        "priority": PriorityEnum.HIGH,
        "status": StatusEnum.OPEN,
        "ai_summary": "Dengue mosquito breeding site in stagnant plaza basement.",
        "triaged_by": "rules",
        "triage_latency_ms": 12,
    },
]


async def seed_database() -> tuple[int, int]:
    """
    Seed database idempotently.
    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        repository = ComplaintRepository(session)

        for item in SEED_COMPLAINTS:
            item_id: uuid.UUID = item["id"] if isinstance(item["id"], uuid.UUID) else uuid.UUID(str(item["id"]))
            item_text: str = str(item["text"])
            # Check for existing record by deterministic UUID or text to maintain idempotency
            already_exists = await repository.exists_by_id(item_id)
            if not already_exists:
                already_exists = await repository.exists_by_text(item_text)

            if already_exists:
                skipped += 1
                continue

            complaint = Complaint(
                id=item["id"],
                text=item["text"],
                location=item["location"],
                reporter_contact=item["reporter_contact"],
                category=item["category"],
                priority=item["priority"],
                status=item["status"],
                ai_summary=item["ai_summary"],
                triaged_by=item["triaged_by"],
                triage_latency_ms=item["triage_latency_ms"],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(complaint)
            inserted += 1

        if inserted > 0:
            await session.commit()

    return inserted, skipped


def main() -> None:
    """Entry point for CLI seeding."""
    print("🌱 Starting CivicPulse idempotent database seed...")
    inserted, skipped = asyncio.run(seed_database())
    print(f"✅ Seeding finished: {inserted} inserted, {skipped} skipped (already present).")
    print(f"📊 Total complaints in dataset: {len(SEED_COMPLAINTS)}")


if __name__ == "__main__":
    main()
