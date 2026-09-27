import math


WINDOW_CHARACTERS = 60
CHUNKS_PER_TIER = 20


def scroll_distance_seconds(elapsed_seconds):
    # Integrating the speed formula avoids frame-rate-dependent distance.
    if elapsed_seconds <= 300:
        return 1.5 * elapsed_seconds + elapsed_seconds ** 2 / 240
    return 825 + 4 * (elapsed_seconds - 300)


def time_for_distance_seconds(distance):
    if distance <= 825:
        return (-360 + math.sqrt(129600 + 960 * distance)) / 2
    return 300 + (distance - 825) / 4


def tier_for_elapsed_ms(elapsed_ms):
    return min(5, int(elapsed_ms // 60000) + 1)


def damage_threshold(stage):
    return max(1, 6 - stage)


def is_printable_character(value):
    return (
        isinstance(value, str)
        and len(value) == 1
        and value.isprintable()
        and ord(value) <= 65535
    )


def reconstruct_survival_target(chunks, chunk_ids):
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    if not isinstance(chunk_ids, list) or not chunk_ids:
        raise ValueError("Provide the ordered Survival chunk IDs.")

    texts = []
    previous_tier = 1
    previous_id = None
    seen_in_cycle = set()
    for chunk_id in chunk_ids:
        if type(chunk_id) is not int or chunk_id not in chunk_by_id:
            raise ValueError("Invalid Survival chunk ID.")
        chunk = chunk_by_id[chunk_id]
        tier = chunk["tier"]
        if not texts and tier != 1:
            raise ValueError("Survival chunks must start in Tier 1.")
        if tier < previous_tier or tier > previous_tier + 1:
            raise ValueError("Invalid Survival tier order.")
        if tier != previous_tier:
            previous_tier = tier
            seen_in_cycle.clear()
            previous_id = None
        elif len(seen_in_cycle) == CHUNKS_PER_TIER:
            seen_in_cycle.clear()
            if previous_id == chunk_id:
                raise ValueError("A chunk repeated across cycles.")
        if chunk_id in seen_in_cycle:
            raise ValueError("A chunk repeated before its tier cycle ended.")
        seen_in_cycle.add(chunk_id)
        previous_id = chunk_id
        texts.append(chunk["text"])

    return " ".join(texts), previous_tier


def recompute_survival_result(chunks, chunk_ids, finalized_entries, active_buffer):
    # Each entry corresponds to one immutable target position. None means
    # that position crossed the boundary without an entered character.
    if not isinstance(finalized_entries, list) or not finalized_entries:
        raise ValueError("Provide finalized Survival positions.")
    if any(entry is not None and not is_printable_character(entry)
           for entry in finalized_entries):
        raise ValueError("Invalid finalized Survival entry.")
    if not isinstance(active_buffer, str) or len(active_buffer) > WINDOW_CHARACTERS:
        raise ValueError("Invalid active Survival buffer.")
    if any(not is_printable_character(character) for character in active_buffer):
        raise ValueError("Invalid active Survival character.")

    target, highest_chunk_tier = reconstruct_survival_target(chunks, chunk_ids)
    if len(target) < len(finalized_entries) + len(active_buffer):
        raise ValueError("The official Survival target is too short.")

    half_heart_units = 6
    damage_counter = 0
    damage_stage = 0
    finalized_entered = 0
    correct_positions = 0
    death_elapsed_ms = None

    # Replay each boundary at its own active timestamp. A delayed browser
    # callback cannot move mistakes into a later damage stage.
    for index, entry in enumerate(finalized_entries):
        crossing_ms = time_for_distance_seconds(index + 1) * 1000
        stage = int(crossing_ms // 60000)
        if stage != damage_stage:
            damage_stage = stage
            damage_counter = 0

        if entry is not None:
            finalized_entered += 1
        if entry is not None and entry == target[index]:
            correct_positions += 1
        else:
            damage_counter += 1
            if damage_counter >= damage_threshold(stage):
                half_heart_units -= 1
                damage_counter = 0

        if half_heart_units == 0:
            if index != len(finalized_entries) - 1:
                raise ValueError("Survival history continues after death.")
            death_elapsed_ms = crossing_ms
            break

    if death_elapsed_ms is None:
        raise ValueError("Survival history does not end in death.")
    if highest_chunk_tier > tier_for_elapsed_ms(death_elapsed_ms):
        raise ValueError("Survival chunks include a future tier.")

    for offset, character in enumerate(active_buffer):
        if character == target[len(finalized_entries) + offset]:
            correct_positions += 1

    retained_characters = finalized_entered + len(active_buffer)
    opportunity_positions = len(finalized_entries) + len(active_buffer)
    raw_wpm = retained_characters / 5 / (death_elapsed_ms / 60000)
    accuracy = correct_positions / opportunity_positions
    net_wpm = raw_wpm * accuracy
    if not all(math.isfinite(value) for value in (raw_wpm, accuracy, net_wpm)):
        raise ValueError("Survival metrics are not finite.")

    return {
        "active_elapsed_ms": death_elapsed_ms,
        "retained_characters": retained_characters,
        "correct_positions": correct_positions,
        "opportunity_positions": opportunity_positions,
        "raw_wpm": raw_wpm,
        "accuracy": accuracy,
        "net_wpm": net_wpm,
        "tier_reached": tier_for_elapsed_ms(death_elapsed_ms),
        "half_heart_units": half_heart_units,
    }
