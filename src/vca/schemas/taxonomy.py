
import json
from pathlib import Path

from pydantic import BaseModel, Field


class TaxonomyEntry(BaseModel):
    """Mapping from a dataset label to a canonical component class."""

    dataset_name: str
    source_label: str
    canonical_name: str
    canonical_id: int = Field(ge=0)
    equivalence_note: str = ""


class UnmappedEntry(BaseModel):
    """A source label that has not yet been mapped."""

    dataset_name: str
    source_label: str


class TaxonomyStore(BaseModel):
    """Stores canonical mappings and unmapped source labels."""

    entries: list[TaxonomyEntry]
    unmapped_labels: list[UnmappedEntry] = Field(default_factory=list)

    def get_canonical(
        self,
        dataset_name: str,
        source_label: str,
    ) -> tuple[str, int]:
        """Return the canonical category using case-insensitive lookup."""
        normalized_label = source_label.strip().lower()

        for entry in self.entries:
            if (
                entry.dataset_name == dataset_name
                and entry.source_label.lower() == normalized_label
            ):
                return entry.canonical_name, entry.canonical_id

        return "unknown", 0


def _load_taxonomy() -> TaxonomyStore:
    """Load taxonomy data from the adjacent JSON file."""
    taxonomy_path = Path(__file__).with_name("taxonomy.json")

    with taxonomy_path.open(encoding="utf-8") as file:
        data = json.load(file)

    return TaxonomyStore.model_validate(data)


TAXONOMY = _load_taxonomy()
