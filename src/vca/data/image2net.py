import json
from pathlib import Path

from vca.schemas.annotation import AnnotationRecord, BoundingBox
from vca.schemas.netlist import (
    Component,
    Net,
    NetEndpoint,
    Netlist,
    Terminal,
)
from vca.schemas.taxonomy import TAXONOMY


def load_labelme_json(path: Path) -> list[AnnotationRecord]:
    """Parse an Image2Net Labelme JSON annotation file."""
    path = Path(path)

    try:
        with path.open(encoding="utf-8") as file:
            content = file.read()

        if not content.strip():
            return []

        data = json.loads(content)

    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc

    required_fields = ["shapes", "imageWidth", "imageHeight"]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"{path}: missing field '{field}'")

    for field in ["imageWidth", "imageHeight"]:
        value = data[field]
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"{path}: field '{field}' must be a positive integer"
            )

    if not isinstance(data["shapes"], list):
        raise ValueError(f"{path}: field 'shapes' must be a list")

    annotations = []

    for index, shape in enumerate(data["shapes"], start=1):
        if not isinstance(shape, dict):
            raise ValueError(
                f"{path}: shape {index} must be an object"
            )

        for field in ["label", "points"]:
            if field not in shape:
                raise ValueError(
                    f"{path}: shape {index} missing field '{field}'"
                )

        label = shape["label"]
        points = shape["points"]

        if not isinstance(label, str):
            raise ValueError(
                f"{path}: shape {index} field 'label' must be a string"
            )

        if (
            not isinstance(points, list)
            or len(points) != 2
            or any(not isinstance(point, list) or len(point) != 2
                   for point in points)
        ):
            raise ValueError(
                f"{path}: shape {index} field 'points' "
                "must contain two [x, y] points"
            )

        try:
            x1, y1 = points[0]
            x2, y2 = points[1]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{path}: shape {index} has invalid 'points'"
            ) from exc

        x = min(x1, x2)
        y = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)

        _, category_id = TAXONOMY.get_canonical("Image2Net", label)

        annotations.append(
            AnnotationRecord(
                id=index,
                image_id=1,
                category_id=category_id,
                bbox=BoundingBox(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                ),
                segmentation=[],
                orientation=None,
                source_label=label,
                dataset_id="Image2Net",
            )
        )

    return annotations

def load_yolo_obb(
    path: Path,
    image_width: int,
    image_height: int,
) -> list[AnnotationRecord]:
    """Parse normalized YOLO OBB annotations into COCO-style annotations."""
    path = Path(path)

    if image_width <= 0 or image_height <= 0:
        raise ValueError(
            f"{path}: image_width and image_height must be positive"
        )

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{path}: unable to read file") from exc

    if not content.strip():
        return []

    annotations = []

    for row_index, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue

        values = line.split()

        if len(values) != 9:
            raise ValueError(
                f"{path}: row {row_index} must contain 9 values"
            )

        try:
            class_id = int(values[0])
            coordinates = [float(value) for value in values[1:]]
        except ValueError as exc:
            raise ValueError(
                f"{path}: row {row_index} contains invalid values"
            ) from exc

        if class_id < 0:
            raise ValueError(
                f"{path}: row {row_index} field 'class_id' must be non-negative"
            )

        for value in coordinates:
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{path}: row {row_index} coordinate {value} "
                    "is outside [0, 1]"
                )

        points = [
            (coordinates[i] * image_width, coordinates[i + 1] * image_height)
            for i in range(0, 8, 2)
        ]

        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]

        x_min = min(x_values)
        y_min = min(y_values)
        x_max = max(x_values)
        y_max = max(y_values)

        # Class ID mapping is unconfirmed; preserve it as a source label.
        source_label = f"class_{class_id}"

        annotations.append(
            AnnotationRecord(
                id=len(annotations) + 1,
                image_id=1,
                category_id=0,
                bbox=BoundingBox(
                    x=x_min,
                    y=y_min,
                    width=x_max - x_min,
                    height=y_max - y_min,
                ),
                segmentation=[
                    [coordinate for point in points for coordinate in point]
                ],
                orientation=None,
                source_label=source_label,
                dataset_id="Image2Net",
            )
        )

    return annotations

def load_validation_netlist(path: Path) -> list[Netlist]:
    """Load Image2Net validation netlists from JSON."""
    path = Path(path)

    try:
        content = path.read_text(encoding="utf-8")

        if not content.strip():
            return []

        data = json.loads(content)

    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc
    except OSError as exc:
        raise ValueError(f"{path}: unable to read file") from exc

    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        raise ValueError(
            f"{path}: root must be an object or a list of circuits"
        )

    netlists = []

    for circuit_index, circuit in enumerate(data, start=1):
        if not isinstance(circuit, dict):
            raise ValueError(
                f"{path}: circuit {circuit_index} must be an object"
            )

        if "ckt_netlist" not in circuit:
            raise ValueError(
                f"{path}: circuit {circuit_index} missing field 'ckt_netlist'"
            )

        raw_components = circuit["ckt_netlist"]

        if not isinstance(raw_components, list):
            raise ValueError(
                f"{path}: circuit {circuit_index} field "
                "'ckt_netlist' must be a list"
            )

        components = []
        net_endpoints = {}

        for component_index, raw_component in enumerate(
            raw_components, start=1
        ):
            if not isinstance(raw_component, dict):
                raise ValueError(
                    f"{path}: circuit {circuit_index}, component "
                    f"{component_index} must be an object"
                )

            for field in ["component_type", "port_connection"]:
                if field not in raw_component:
                    raise ValueError(
                        f"{path}: circuit {circuit_index}, component "
                        f"{component_index} missing field '{field}'"
                    )

            component_type = raw_component["component_type"]
            port_connection = raw_component["port_connection"]

            if not isinstance(component_type, str):
                raise ValueError(
                    f"{path}: circuit {circuit_index}, component "
                    f"{component_index} field 'component_type' "
                    "must be a string"
                )

            if (
                not isinstance(port_connection, dict)
                or not port_connection
            ):
                raise ValueError(
                    f"{path}: circuit {circuit_index}, component "
                    f"{component_index} field 'port_connection' "
                    "must be a non-empty object"
                )

            component_id = f"C{component_index}"

            terminals = []
            for terminal_name, net_name in port_connection.items():
                if not isinstance(terminal_name, str):
                    raise ValueError(
                        f"{path}: terminal name must be a string"
                    )

                if not isinstance(net_name, str) or not net_name:
                    raise ValueError(
                        f"{path}: circuit {circuit_index}, component "
                        f"{component_index} has invalid net name"
                    )

                terminals.append(Terminal(name=terminal_name))

                net_endpoints.setdefault(net_name, []).append(
                    NetEndpoint(
                        component_id=component_id,
                        terminal_name=terminal_name,
                    )
                )

            canonical_category, _ = TAXONOMY.get_canonical(
                "Image2Net", component_type
            )

            components.append(
                Component(
                    id=component_id,
                    canonical_category=canonical_category,
                    terminals=terminals,
                )
            )

        nets = [
            Net(name=net_name, endpoints=endpoints)
            for net_name, endpoints in net_endpoints.items()
        ]

        try:
            netlists.append(
                Netlist(
                    components=components,
                    nets=nets,
                )
            )
        except ValueError as exc:
            raise ValueError(
                f"{path}: invalid netlist in circuit {circuit_index}: {exc}"
            ) from exc

    return netlists