"""SQLAlchemy ORM models for the kit-hub database.

All tables use string primary keys (UUIDs) for uniformity.  The full
``RecipeCore`` Pydantic model is stored serialised as JSON in the
``recipe_json`` column.  Metadata columns (``name``, ``source``,
``meal_course``) are denormalised for efficient querying without
deserialising JSON.

Tables:
    recipes: One row per recipe; holds metadata + full JSON blob.
    tags: Global tag registry; keyed by tag name.
    recipe_tags: Many-to-many link between recipes and tags.
    authors: Content creators (Instagram profiles, etc.).
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class RecipeRow(Base):
    """Persistent recipe record.

    The ``recipe_json`` column holds a serialised ``RecipeCore`` model.
    Use ``RecipeCore.model_validate_json(row.recipe_json)`` to reconstruct it.

    Attributes:
        id: UUID string primary key.
        name: Recipe name - denormalised from ``RecipeCore`` for querying.
        source: ``RecipeSource`` value (``"instagram"``, ``"voice_note"``,
            ``"manual"``).
        source_id: Platform-specific identifier (IG shortcode, note ID, or
            empty string for manual entries).
        meal_course: Italian meal-course classification.  ``None`` when not
            yet classified.
        recipe_json: Full ``RecipeCore`` serialised as a JSON string.
        user_id: Owner identifier.  ``None`` for anonymous / public recipes.
        is_public: Whether the recipe is visible to all users.
        sort_index: Lower values appear first in the cook-soon queue.
        created_at: UTC timestamp of first insertion.
        updated_at: UTC timestamp of most recent update.
        tags: Related ``RecipeTagRow`` instances (eager-loaded on access).
    """

    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    meal_course: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recipe_json: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    tags: Mapped[list[RecipeTagRow]] = relationship(
        "RecipeTagRow",
        back_populates="recipe",
        cascade="all, delete-orphan",
    )


class TagRow(Base):
    """Global tag registry.

    Tags are shared across recipes.  The tag name is its own primary key
    since names are short, lowercase identifiers that rarely change.

    Attributes:
        name: Unique lowercase tag label (primary key).
        usefulness: Non-negative integer ranking how useful this tag is
            for discovery.  Higher is more useful.
    """

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    usefulness: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe_tags: Mapped[list[RecipeTagRow]] = relationship(
        "RecipeTagRow",
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class RecipeTagRow(Base):
    """Many-to-many link between recipes and tags.

    Carries confidence and provenance metadata for each assignment.

    Attributes:
        recipe_id: Foreign key referencing ``recipes.id``.
        tag_name: Foreign key referencing ``tags.name``.
        confidence: Confidence score in ``[0.0, 1.0]``.
        origin: ``"ai"`` for ``TagExtractor`` output or ``"manual"`` for
            user-applied tags.
    """

    __tablename__ = "recipe_tags"
    __table_args__ = (UniqueConstraint("recipe_id", "tag_name", name="uq_recipe_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recipes.id"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(
        String(128), ForeignKey("tags.name"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")

    recipe: Mapped[RecipeRow] = relationship("RecipeRow", back_populates="tags")
    tag: Mapped[TagRow] = relationship("TagRow", back_populates="recipe_tags")


class AuthorRow(Base):
    """Content creator profile.

    Stores author information gathered during IG ingestion.  The
    ``platform_id`` field holds the platform-native user ID so
    authors can be looked up without re-fetching their profile.

    Attributes:
        id: UUID string primary key.
        username: Platform username (e.g. IG handle without ``@``).
        full_name: Display name.
        biography: Profile bio text.
        page_link: URL to the author's profile page.  ``None`` when not
            available.
        platform: Platform name (e.g. ``"instagram"``).
        platform_id: Platform-native user identifier.
    """

    __tablename__ = "authors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    biography: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(256), nullable=False)
