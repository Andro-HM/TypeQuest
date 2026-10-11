
# Define the Classic tiers and their unlocking requirements.
CLASSIC_BLOCKS = (
    {"tier": 1, "first_level": 1, "last_level": 10, "required_stars": 0},
    {"tier": 2, "first_level": 11, "last_level": 20, "required_stars": 23},
)


def get_classic_block_statuses(saved_progress):
    best_stars_by_level = {}

    # Store the best stars earned for each completed level.
    for row in saved_progress:
        best_stars_by_level[row["level_id"]] = row["best_stars"]

    block_statuses = []

    for block in CLASSIC_BLOCKS:
        previous_stars = 0

        # Count the best stars from all levels before this tier.
        for level_id in range(1, block["first_level"]):
            if level_id in best_stars_by_level:
                previous_stars += best_stars_by_level[level_id]

        # Copy the tier details without modifying CLASSIC_BLOCKS.
        block_status = block.copy()
        block_status["current_stars"] = previous_stars
        block_status["unlocked"] = previous_stars >= block["required_stars"]

        block_statuses.append(block_status)

    return block_statuses


def find_classic_block(level_id, block_statuses):
    # Find which tier contains the given level.
    for block in block_statuses:
        if block["first_level"] <= level_id <= block["last_level"]:
            return block

    return None
