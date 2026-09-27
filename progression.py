CLASSIC_BLOCKS = (
    {"tier": 1, "first_level": 1, "last_level": 10, "required_stars": 0},
    {"tier": 2, "first_level": 11, "last_level": 20, "required_stars": 23},
)


def get_classic_block_statuses(saved_progress):
    best_stars_by_level = {
        row["level_id"]: row["best_stars"] for row in saved_progress
    }
    block_statuses = []

    for block in CLASSIC_BLOCKS:
        previous_stars = sum(
            best_stars_by_level.get(level_id, 0)
            for level_id in range(1, block["first_level"])
        )
        block_statuses.append({
            **block,
            "current_stars": previous_stars,
            "unlocked": previous_stars >= block["required_stars"],
        })

    return block_statuses


def find_classic_block(level_id, block_statuses):
    for block in block_statuses:
        if block["first_level"] <= level_id <= block["last_level"]:
            return block
    return None
