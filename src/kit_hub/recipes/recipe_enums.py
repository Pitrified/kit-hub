"""Recipe domain enumerations.

This module defines the shared enum types used across the recipe data model.
All enums use ``StrEnum`` so they serialise to plain strings in JSON output
and compare equal to their string values.

Enums:
    StepType: Distinguishes text instructions from image placeholders.
    RecipeSource: Records how a recipe entered the system.
    MealCourse: Italian meal-course taxonomy used in the cookbook project.
"""

from enum import StrEnum


class StepType(StrEnum):
    """Preparation step content type.

    Attributes:
        TEXT: A plain-text instruction string.
        IMAGE: A placeholder for an image step (future use).
    """

    TEXT = "text"
    IMAGE = "image"


class RecipeSource(StrEnum):
    """Origin channel through which a recipe entered the system.

    Attributes:
        INSTAGRAM: Downloaded from an Instagram post.
        WEB_RECIPE: Scraped from a known recipe website.
        WEB_GENERIC: Scraped from a generic web page.
        VOICE_NOTE: Transcribed from a live voice session.
        MANUAL: Entered by the user directly.
    """

    INSTAGRAM = "instagram"
    WEB_RECIPE = "web_recipe"
    WEB_GENERIC = "web_generic"
    VOICE_NOTE = "voice_note"
    MANUAL = "manual"


class MealCourse(StrEnum):
    """Italian meal-course taxonomy.

    These map to the category buckets used in the cookbook project.

    Attributes:
        PANI: Breads and doughs.
        ANTIPASTI: Starters and appetisers.
        PRIMI: First courses (pasta, risotto, soups).
        SECONDI: Main courses (meat, fish).
        FRITTI: Fried dishes.
        CONTORNI: Side dishes.
        DOLCI: Desserts and sweets.
        ALCOL: Alcoholic drinks and cocktails.
    """

    PANI = "pani"
    ANTIPASTI = "antipasti"
    PRIMI = "primi"
    SECONDI = "secondi"
    FRITTI = "fritti"
    CONTORNI = "contorni"
    DOLCI = "dolci"
    ALCOL = "alcol"
