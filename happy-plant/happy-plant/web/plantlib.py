"""Plant library (Pro lookup) and care tips. Temps in °F; light 0-3; moisture 0-4."""

LIB = {
    "dill": {"air": [60, 75], "soil": [55, 70], "light": [2, 3], "moist": [2, 3], "about": "Feathery herb for pickles, fish and salads. Likes cool air, full sun and soil that never dries out."},
    "basil": {"air": [65, 85], "soil": [60, 78], "light": [2, 3], "moist": [2, 3], "about": "Warm-weather herb. Hates cold nights below 50°F. Pinch the tops to keep it bushy."},
    "mint": {"air": [55, 80], "soil": [50, 75], "light": [1, 3], "moist": [2, 3], "about": "Nearly unkillable. Spreads fast, so keep it in its own pot. Loves damp soil."},
    "tomato": {"air": [65, 85], "soil": [60, 80], "light": [3, 3], "moist": [2, 3], "about": "Needs full sun and steady water. Uneven watering splits the fruit."},
    "parsley": {"air": [50, 75], "soil": [50, 70], "light": [1, 3], "moist": [2, 3], "about": "Slow to sprout, then easy. Cool temps and even moisture."},
    "cilantro": {"air": [50, 75], "soil": [50, 68], "light": [2, 3], "moist": [2, 3], "about": "Bolts in heat. Grows best in spring and fall. Keep soil moist."},
    "rosemary": {"air": [55, 85], "soil": [55, 80], "light": [2, 3], "moist": [1, 2], "about": "Mediterranean. Full sun, let the soil dry between waterings. Overwatering is the usual killer."},
    "monstera": {"air": [65, 85], "soil": [60, 80], "light": [1, 2], "moist": [1, 2], "about": "Bright indirect light. Let the top inch of soil dry. Wipe the leaves now and then."},
    "pothos": {"air": [60, 85], "soil": [60, 80], "light": [0, 2], "moist": [1, 2], "about": "Tolerates low light. Water when the soil is dry an inch down. Vines can go for years."},
    "snake plant": {"air": [60, 85], "soil": [60, 80], "light": [0, 3], "moist": [0, 1], "about": "Thrives on neglect. Water every 2–4 weeks. Rot is the only real risk."},
    "succulent": {"air": [60, 85], "soil": [60, 80], "light": [2, 3], "moist": [0, 1], "about": "Bright light and dry soil. Water deeply, then wait until bone dry."},
    "fern": {"air": [60, 75], "soil": [58, 72], "light": [0, 1], "moist": [2, 3], "about": "Shade and humidity. Soil should stay moist but never soggy."},
    "orchid": {"air": [65, 80], "soil": [62, 78], "light": [1, 2], "moist": [1, 2], "about": "Bright indirect light. Water about weekly, let it drain fully."},
    "lavender": {"air": [60, 85], "soil": [58, 80], "light": [3, 3], "moist": [0, 1], "about": "Full sun, dry feet. Too much water or shade and it sulks."},
}


def find(name):
    k = (name or "").strip().lower()
    return LIB.get(k) or LIB.get(k.rstrip("s"))


def tips_for(name, wants, unit):
    def t(f):
        return f"{round((f - 32) * 5 / 9)}°C" if unit == "C" else f"{round(f)}°F"

    tips = []
    hit = find(name)
    if hit:
        tips.append({"b": f"About {name}", "s": hit["about"]})
    tips.append({"b": "Water", "s": "Likes to dry out. Water deeply, then wait until the soil reads Parched before the next one."
                 if wants["moist"][0] <= 1 else "Keep the soil at Just right. Water when it reads Thirsty, before Parched."})
    if wants["light"][1] == 3:
        light = f"Wants real sun. A south or west window, or outside once nights stay above {t(wants['air'][0])}."
    elif wants["light"][0] == 0:
        light = "Fine in shade. Keep it out of direct afternoon sun, which reads Blazing and scorches the leaves."
    else:
        light = "Bright but filtered. An east window or a few feet back from a south one."
    tips.append({"b": "Light", "s": light})
    tips.append({"b": "Cold", "s": f"Below {t(wants['air'][0])} it suffers. Move it somewhere warmer before a cold night."})
    tips.append({"b": "Heat", "s": f"Above {t(wants['air'][1])} the soil dries twice as fast. Expect Thirsty readings sooner on hot days."})
    return tips
