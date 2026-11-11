
"""Render evaluation overlays over circuit images."""

from pathlib import Path

from PIL import Image, ImageDraw

from vca.schemas.annotation import AnnotationRecord, BoundingBox

Color = tuple[int, int, int]


def _draw_dashed_rectangle(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[float, float, float, float],
    color: tuple[int, int, int],
    dash_length: int = 6,
    gap_length: int = 4,
    width: int = 2,
) -> None:
    """Draw a dashed rectangle."""
    x1, y1, x2, y2 = bbox

    def draw_dashed_line(
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> None:
        sx, sy = start
        ex, ey = end

        length = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
        if length == 0:
            return

        dx = (ex - sx) / length
        dy = (ey - sy) / length
        position = 0.0

        while position < length:
            segment_end = min(position + dash_length, length)

            draw.line(
                (
                    sx + dx * position,
                    sy + dy * position,
                    sx + dx * segment_end,
                    sy + dy * segment_end,
                ),
                fill=color,
                width=width,
            )

            position += dash_length + gap_length

    draw_dashed_line((x1, y1), (x2, y1))
    draw_dashed_line((x2, y1), (x2, y2))
    draw_dashed_line((x2, y2), (x1, y2))
    draw_dashed_line((x1, y2), (x1, y1))


def render_overlay(
    image_path: str | Path,
    ground_truth_annotations: list[AnnotationRecord],
    predicted_annotations: list[AnnotationRecord],
    output_path: str | Path,
    legend_lines: list[str] | None = None,
    labelled_boxes: list[tuple[BoundingBox, str, Color]] | None = None,
    legend_panel: bool = False,
) -> Path:
    """Render bounding boxes and an optional text legend.

    ``labelled_boxes`` draws extra boxes (e.g. VLM-estimated component
    locations) with a text tag. With ``legend_panel`` the legend goes in a
    white strip below the image instead of covering its top.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as source:
        image = source.convert("RGB").copy()

    line_height = 16
    padding = 6

    if legend_panel and legend_lines:
        panel_height = len(legend_lines) * line_height + 2 * padding
        canvas = Image.new(
            "RGB", (image.width, image.height + panel_height), (255, 255, 255)
        )
        canvas.paste(image, (0, 0))
        draw = ImageDraw.Draw(canvas)
        for index, line in enumerate(legend_lines):
            draw.text(
                (padding, image.height + padding + index * line_height),
                line,
                fill=(0, 0, 0),
            )
        legend_lines = None
        image = canvas

    draw = ImageDraw.Draw(image)

    for bbox, label, color in labelled_boxes or []:
        draw.rectangle(
            (bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height),
            outline=color,
            width=3,
        )
        draw.text((bbox.x + 2, max(bbox.y - line_height, 0)), label, fill=color)

    # Ground-truth boxes: solid green.
    for annotation in ground_truth_annotations:
        bbox = annotation.bbox
        draw.rectangle(
            (
                bbox.x,
                bbox.y,
                bbox.x + bbox.width,
                bbox.y + bbox.height,
            ),
            outline=(0, 255, 0),
            width=2,
        )

    # Predicted boxes: dashed red.
    for annotation in predicted_annotations:
        bbox = annotation.bbox
        _draw_dashed_rectangle(
            draw,
            (
                bbox.x,
                bbox.y,
                bbox.x + bbox.width,
                bbox.y + bbox.height,
            ),
            color=(255, 0, 0),
        )

    # Optional legend for predictions without spatial annotations.
    if legend_lines:
        legend_height = len(legend_lines) * line_height + 2 * padding

        draw.rectangle(
            (
                0,
                0,
                image.width,
                min(legend_height, image.height),
            ),
            fill=(255, 255, 255),
        )

        for index, line in enumerate(legend_lines):
            draw.text(
                (padding, padding + index * line_height),
                line,
                fill=(0, 0, 0),
            )

    image.save(output_path, format="PNG")
    return output_path
