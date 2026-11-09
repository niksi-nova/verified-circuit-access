
"""Property-based tests for taxonomy lookup completeness."""

from hypothesis import given, settings
from hypothesis import strategies as st

from vca.schemas.taxonomy import TaxonomyEntry, TaxonomyStore


@st.composite
def taxonomy_stores(draw):
    """Generate taxonomy stores with unique source labels."""

    source_labels = draw(
        st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
                min_size=1,
                max_size=16,
            ),
            min_size=0,
            max_size=30,
            unique_by=str.lower,
        )
    )

    entries = []

    for source_label in source_labels:
        canonical_name = draw(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
                min_size=1,
                max_size=20,
            )
        )

        canonical_id = draw(
            st.integers(min_value=0, max_value=1000)
        )

        entries.append(
            TaxonomyEntry(
                dataset_name="generated-dataset",
                source_label=source_label,
                canonical_name=canonical_name,
                canonical_id=canonical_id,
            )
        )

    return TaxonomyStore(entries=entries)


# Feature: m1-data-audit-baseline, Property 2: Taxonomy lookup completeness
@given(store=taxonomy_stores())
@settings(max_examples=100)
def test_taxonomy_lookup_returns_recorded_mapping(
    store: TaxonomyStore,
) -> None:
    """Every registered source label resolves to its recorded mapping."""

    for entry in store.entries:
        result = store.get_canonical(
            entry.dataset_name,
            entry.source_label,
        )

        assert result == (
            entry.canonical_name,
            entry.canonical_id,
        )


@given(store=taxonomy_stores())
@settings(max_examples=100)
def test_taxonomy_lookup_is_case_insensitive(
    store: TaxonomyStore,
) -> None:
    """Changing source-label casing does not change its mapping."""

    for entry in store.entries:
        result = store.get_canonical(
            entry.dataset_name,
            entry.source_label.swapcase(),
        )

        assert result == (
            entry.canonical_name,
            entry.canonical_id,
        )
