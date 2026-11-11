import re

from pydantic import BaseModel, Field, field_validator, model_validator

from vca.schemas.annotation import BoundingBox

TERMINAL_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class Terminal(BaseModel):
    """A named terminal belonging to a component."""

    name: str

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, value: str) -> str:
        if not TERMINAL_PATTERN.fullmatch(value):
            raise ValueError(
                f"Terminal name {value!r} must contain only "
                "alphanumeric characters, hyphens, or underscores."
            )
        return value


class Component(BaseModel):
    """A circuit component with a unique identifier.

    ``bbox`` is optional pixel-space location (COCO [x, y, w, h]). Golden
    Image2Net netlists have none; predictors may supply one so that errors
    can be drawn on the image and, in M2, tied to detections.
    """

    id: str
    canonical_category: str
    terminals: list[Terminal] = Field(min_length=1)
    bbox: BoundingBox | None = None

    @model_validator(mode="after")
    def validate_unique_terminal_names(self):
        names = [terminal.name for terminal in self.terminals]

        if len(names) != len(set(names)):
            raise ValueError(
                f"Component {self.id!r} contains duplicate terminal names."
            )

        return self


class NetEndpoint(BaseModel):
    """A reference to one terminal of a component."""

    component_id: str
    terminal_name: str


class Net(BaseModel):
    """An electrical net connecting component terminals."""

    name: str
    endpoints: list[NetEndpoint] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_endpoints(self):
        endpoint_pairs = [
            (endpoint.component_id, endpoint.terminal_name)
            for endpoint in self.endpoints
        ]

        if len(endpoint_pairs) != len(set(endpoint_pairs)):
            raise ValueError(
                f"Net {self.name!r} contains duplicate endpoints."
            )

        return self


class Netlist(BaseModel):
    """A complete circuit netlist."""

    schema_version: str = "1.0.0"
    components: list[Component]
    nets: list[Net]

    @model_validator(mode="after")
    def validate_net_references(self):
        component_terminals = {
            component.id: {
                terminal.name for terminal in component.terminals
            }
            for component in self.components
        }

        endpoint_to_net = {}

        for net in self.nets:
            for endpoint in net.endpoints:
                component_id = endpoint.component_id
                terminal_name = endpoint.terminal_name

                if component_id not in component_terminals:
                    raise ValueError(
                        f"Net {net.name!r} references unknown component "
                        f"{component_id!r}."
                    )

                if terminal_name not in component_terminals[component_id]:
                    raise ValueError(
                        f"Net {net.name!r} references unknown terminal "
                        f"{terminal_name!r} on component {component_id!r}."
                    )

                endpoint_key = (component_id, terminal_name)

                if endpoint_key in endpoint_to_net:
                    previous_net = endpoint_to_net[endpoint_key]

                    raise ValueError(
                        f"Endpoint {endpoint_key!r} appears in both "
                        f"net {previous_net!r} and net {net.name!r}."
                    )

                endpoint_to_net[endpoint_key] = net.name

        return self

    @model_validator(mode="after")
    def validate_unique_component_ids(self):
        component_ids = [component.id for component in self.components]

        if len(component_ids) != len(set(component_ids)):
            seen = set()

            for component in self.components:
                if component.id in seen:
                    raise ValueError(
                        f"Duplicate component identifier: {component.id!r}."
                    )
                seen.add(component.id)

        return self

    @model_validator(mode="after")
    def validate_unique_net_names(self):
        net_names = [net.name for net in self.nets]

        if len(net_names) != len(set(net_names)):
            seen = set()

            for net in self.nets:
                if net.name in seen:
                    raise ValueError(f"Duplicate net name: {net.name!r}.")
                seen.add(net.name)

        return self