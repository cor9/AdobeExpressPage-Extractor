"""Vimeo -> Bunny Stream video map for the archived Child Actor 101 Adobe Express pages.

Every Corey-owned Vimeo embed on a legacy Adobe page was migrated to Bunny Stream. This file records,
per legacy Vimeo id, what the extractor should do with that embed:

  bunny(...)           mapped to a Bunny video (player URL built from the Bunny library id + guid).
                       review=True marks a medium-confidence match that should be double-checked.
  external_vimeo(...)  a third-party Vimeo video that is still live; the original embed is kept.
  missing(...)         no confident match yet; the page keeps a neutral "Video coming soon" placeholder
                       in the exact original position. `candidates` are hints for whoever identifies it.

Ids that are not listed here are treated as missing. To fill a placeholder, replace its `missing(...)`
entry with `bunny(guid, title)` and re-run the extractor for the pages that contain it.
(Originally produced by the Vimeo -> Bunny recovery audit; HIGH / MEDIUM / LOW sections below.)
"""

# --- Vimeo -> Bunny mapping (from recovery audit) ---------------------------

S2_POOL = (
    "Unverified collection candidates: Calendar (b59870ff-3eb4-4e3b-9563-1efeef1062ff), "
    "Casting Snafus (7f569a6b-8f87-4ccc-a250-2f09a93aedbf), "
    "Equipment Review (7bcd3991-6e37-4a61-86cb-25e0abc220cb), "
    "Plan B (73f63b46-d716-42ee-8b70-df2348e8408b), "
    "Producer Hat (0caf5463-c3d9-4d4b-a332-1c29d4a5ded7), "
    "The Test (1705e2e7-907c-468d-8241-5b63b9b3cc08), "
    "Mr Rogers (ed3ea1af-ac78-4c13-b063-c876cf0a5348), "
    "The 80-20 Rule (bf11ebe6-d5ac-4cde-a0cb-fa1675aa3cfa), "
    "Untitled (5) (f5b0854e-6c52-44f3-ae0d-ab13c364d774), "
    "Untitled (6) (a855464e-d499-4221-98fa-dd884df2146d), "
    "Welcome to Mini Film School (2b5436fd-2083-4b52-84ff-34c52d8307a3), "
    "Da Crew (e75d57f3-78d6-4185-b2e8-7b7b7c9fff78)."
)


def bunny(guid, title, review=False):
    video = {"kind": "bunny", "guid": guid, "title": title}
    if review:
        video["needsReview"] = True
        video["note"] = "Mapped from legacy Vimeo embed with medium confidence. Verify this is the intended lesson video."
    return video


def missing(vimeo_id, note, candidates=None):
    video = {"kind": "missing", "legacyVimeoId": vimeo_id, "note": note}
    if candidates:
        video["candidates"] = candidates
    return video


def vimeo_title(vimeo_id):
    """Title of a video in Corey's Vimeo library export (vimeo_library.csv), or None. Use it to match ids to Bunny titles."""
    import csv, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vimeo_library.csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["Video ID"] == vimeo_id:
                return f'{row["Video Title"]} ({row["Duration"]}s)'
    return None


def youtube(youtube_id, title):
    """A Vimeo embed that was replaced by a YouTube video (rendered as a plain YouTube embed)."""
    return {"kind": "youtube", "id": youtube_id, "title": title}


def external_vimeo(vimeo_id, title):
    return {"kind": "vimeo", "vimeoId": vimeo_id, "title": title, "thirdParty": True,
            "note": "Third-party reference video preserved from the legacy course. Still live on Vimeo."}


# YouTube embeds on the original pages that were taken down and replaced: old id -> new id.
YOUTUBE_REPLACEMENTS = {
    "b8ppTuW6jkU": "VqpSLp9H-DY",  # Plan & Prep It, Grip video (after the Craft Services video)
}

VIMEO_MAP = {
    # --- HIGH confidence ---
    "379943966": bunny("f642726e-8dc1-412e-9d97-f0ba82548121", "NO EXCUSES! Demo Clip Course for Actor's"),
    "377213706": bunny("3d6315f4-a7f5-482e-9937-b9a79a543b83", "Paying Homage"),
    "377218287": bunny("99cad305-1d4a-41eb-b9e2-40203a2b8b47", "Mission For You"),
    "377218581": bunny("2e57a4c2-a5ed-4e8b-ae0e-89c8e5e004bb", "Fences"),
    "377218336": bunny("ef3f1d7e-1cf5-44ec-9a17-d6e549c4d005", "Don't be scared"),
    "288832063": {"kind": "bunny", "guid": "893a07b7-0282-4740-baa0-16e7966fb3f4", "title": "Beautiful Scar",
                  "note": "Verified via live Vimeo oEmbed (title 'Beautiful Scar'). Lives in the main Bunny library, outside the No Excuses! collection."},
    "387346357": bunny("2db093b6-05c7-419a-b65c-57b097abb8af", "Intro Two"),
    "387349950": bunny("5199be9f-8ade-4fd7-99da-c04766a72770", "Sound is HUGE"),
    "387392930": bunny("14128357-4e1f-49a8-b8b9-7059a429badb", "My lighting obsession"),
    "387395199": bunny("08d45d8d-b3da-4e5e-addb-81aa05a010eb", "Shot by shot"),
    "387609679": bunny("2ecc9825-90cb-496f-8760-2357d94b2188", "Chill Pill"),
    "387615832": bunny("c0b67795-97c0-411b-83a3-0b25997d1b1f", "Check the gate"),
    "391173336": bunny("452637f1-69f2-4f2f-85f8-4c2d23f28919", "Editing intro"),
    "391763750": bunny("e2c4531b-5651-423e-bdc4-4a5866104e10", "Walk through an Edit"),
    "390130720": bunny("3205b169-cf47-42b7-9ee6-807175b8fadc", "Q&A with Film Editor - Kasey Atkins"),
    "391178618": bunny("c715830e-8708-468e-b404-73a2b5cb7fcb", "Score"),
    "391183772": bunny("f4b38625-9437-4095-bc70-153ae32ec756", "Edit wrap"),
    "396112238": bunny("715876c7-ae22-4e13-8293-7613804c0130", "Welcome, Welcome"),
    "392546804": {"kind": "bunny", "guid": "ca3cb3c4-aea2-455c-8b26-490b28013684",
                  "title": "The role of the reader - Parent Self Tape course for Child Actor 101",
                  "note": "Bunny copy is the full 69-minute parent-course session; the legacy page described 'excerpts'."},
    # --- MEDIUM confidence (include, flagged needsReview) ---
    "377218490": bunny("bf11ebe6-d5ac-4cde-a0cb-fa1675aa3cfa", "The 80/20 Rule"),  # Vimeo title confirmed via vimeo_library.csv
    "387349854": bunny("591fc3a7-f974-4ab1-8ca0-09a4d7e59629", "Let There Be Light", review=True),
    "387501390": bunny("d0a15047-7b7c-4995-8f9a-984170135d60", "Learn from my Mistakes", review=True),
    "387353415": bunny("2b5436fd-2083-4b52-84ff-34c52d8307a3", "Welcome to Mini Film School"),  # Vimeo title confirmed via vimeo_library.csv
    "393058496": bunny("435006c3-5890-4e01-8b65-81ad43b099d6", "Parent Coaching Tips", review=True),
    "334221482": bunny("d75ef465-5688-4d80-8ea2-59c595e44df3", "What is a Slate Shot-", review=True),
    # --- External third-party Vimeo, still live ---
    "71838170": external_vimeo("71838170", "Who's Who on a Movie Crew (Vimeo Video School, 2013)"),
    "143619334": external_vimeo("143619334", "Why Props Matter (Rishi Kaneria, 2015)"),
    # Vimeo title is "Mikey, Likes It!" (vimeo_library.csv). Earlier guess of Bunny "Research" was wrong.
    "377218224": missing("377218224", "Write It opening video; Vimeo title 'Mikey, Likes It!' (79s). Needs its Bunny match."),
    # --- Supplied by Corey (formerly unmatched placeholders) ---
    "377218725": bunny("ed3ea1af-ac78-4c13-b063-c876cf0a5348", "Corey Ralston bio"),  # supplied by Corey
    "387252761": bunny("a855464e-d499-4221-98fa-dd884df2146d", "Why are Clips soo Important?"),  # supplied by Corey
    "377218442": bunny("f4819274-3445-4552-875a-d2e72ba0cf72", "Genres & Types"),  # supplied by Corey
    "324792551": youtube("q4j0btglDCM", "Re-worked Shameless Scene"),  # supplied by Corey (Vimeo/Bunny copy taken down)
    "371529420": bunny("367dd260-f086-4534-a4b0-e06273c9c568", "Two Actor Clip"),  # supplied by Corey
    "344516472": bunny("6193ad09-46a1-4315-9cbe-4876b55c8147", "Three Shot Example"),  # supplied by Corey
    "377218960": bunny("95d84379-5f4a-4719-b58f-4c81068bcea8", "The Style (tone)"),  # supplied by Corey
    "377219246": bunny("893a07b7-0282-4740-baa0-16e7966fb3f4", "Beautiful Scar"),  # Mono-Clip; supplied by Corey (same video as Beautiful Scar above)
    "387357732": bunny("b59870ff-3eb4-4e3b-9563-1efeef1062ff", "Welcome Back 2"),  # supplied by Corey
    "387347988": bunny("7f569a6b-8f87-4ccc-a250-2f09a93aedbf", "Welcome Back 3"),  # supplied by Corey
    "387348581": bunny("f4c48c85-90e1-4bf4-ba79-3d28b067a23c", "Welcome Back 4"),  # supplied by Corey
    "387350883": bunny("e75d57f3-78d6-4185-b2e8-7b7b7c9fff78", "Plan & Prep closing 1"),  # supplied by Corey
    "387350986": bunny("fe7bb938-4235-4a64-b399-73d3dd8f8fe2", "Plan & Prep closing 2"),  # supplied by Corey
    "387352092": bunny("3ae82d41-3502-4076-b81d-a136e539bd62", "Plan & Prep closing 3"),  # supplied by Corey
    "387351912": bunny("73f63b46-d716-42ee-8b70-df2348e8408b", "Plan & Prep closing 4"),  # supplied by Corey
    "387352511": bunny("0caf5463-c3d9-4d4b-a332-1c29d4a5ded7", "Plan & Prep closing 5"),  # supplied by Corey
    "387612134": bunny("2ecc9825-90cb-496f-8760-2357d94b2188", "Take a Chill Pill"),  # supplied by Corey
    "390282478": bunny("88c59b5d-ae82-443c-bc8e-98a74f358c68", "Overlays & labeling"),  # supplied by Corey
    "391760430": youtube("AP23350iWzM", "Corey's Enlight overview"),  # supplied by Corey
    "396114925": bunny("b2d1c50a-4c38-498a-832c-b0fa0b227898", "A very important message from Corey"),  # supplied by Corey
    "359315033": youtube("zAFzZ6O2iOA", "Vimeo video hosting"),  # supplied by Corey
    "396116394": bunny("7f0d7d40-7914-4b7c-beb2-72e809a9ffa7", "And That is... A Wrap!"),  # supplied by Corey
    "336444157": youtube("cJ1zhq3yNBM", "Dacre Montgomery Stranger Things audition"),  # supplied by Corey
    "395384847": bunny("24a86371-7d6a-455f-ac0d-1b40b2d5991f", "Nicholas's black-and-white self tape"),  # supplied by Corey
}
