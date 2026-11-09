from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """COCO-style [x, y, width, height] in pixel coordinates."""

    x: float
    y: float
    width: float
    height: float


class AnnotationRecord(BaseModel):
    """Annotation for a circuit component."""

    id: int = Field(ge=1)
    image_id: int = Field(ge=1)
    category_id: int = Field(ge=0)
    bbox: BoundingBox
    segmentation: list[list[float]] = Field(default_factory=list)
    orientation: float | None = Field(default=None, ge=0.0, lt=360.0)
    source_label: str
    dataset_id: str


class ImageRecord(BaseModel):
    """Metadata for a circuit image."""

    id: int = Field(ge=1)
    file_name: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class CategoryRecord(BaseModel):
    """Component category."""

    id: int = Field(ge=0)
    name: str


class COCODataset(BaseModel):
    """COCO-style dataset containing images, annotations, and categories."""

    images: list[ImageRecord]
    annotations: list[AnnotationRecord]
    categories: list[CategoryRecord]