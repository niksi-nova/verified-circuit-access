# Curriculum schematic annotation

Choose figures from school and college textbooks that you are allowed to use for
private evaluation. Sample several books, topics, and diagram styles. Start
with a single legible schematic per image. Include series and parallel circuits,
bridges, and amplifier circuits when the symbols are in the supported taxonomy.
Keep a fixed evaluation list before running the pipeline. Keep near-duplicates
and alternative editions of the same drawing together.

Record the textbook, edition, page, figure number, and any crop or quality notes
in the private manifest. Use a neutral ID such as `fig-0001` for filenames.
Keep the original figure, annotations, and manifest in `data/private/`.
These figures are evaluation-only. Do not commit, publish, upload to external
services, or use them for training or threshold selection.

## Draw component boxes

1. Open the cropped image in Labelme using
   [the label list](annotation-kit/labelme-labels.txt). Leave embedded image
   data off when saving. Use two-corner rectangles close around each symbol.
2. Give every electrical component a unique positive integer group ID.
   Group ID `1` corresponds to `C1` in the netlist. Use reading order to assign
   IDs and keep them stable after review.
3. Use the canonical netlist category from the label list. Label a battery
   `voltage` and a differential-input, single-output amplifier `diff-amp`. Mark `ground`, `vdd`, `port`,
   `antenna`, and `cross-line-curved` when present as context boxes. Context
   boxes use no group ID. Rails and ports describe connectivity and do not
   become electrical components in this kit.
4. Exclude diagram titles, wire segments, value text, stray marks, and legends
   from component boxes. Set aside ambiguous scans, pictorial wiring, and
   figures containing electrical components outside the supported taxonomy.
   Record the reason privately.

## Record nets

Copy the [empty netlist template](annotation-kit/netlist.template.json). Add
each boxed electrical component using its matching `C` ID and canonical
category. Use the terminal names in
[the shared port table](../src/vca/schemas/ports.py). Keep the printed symbol
orientation in mind when assigning polarity and transistor terminals.

Follow every uninterrupted conductor and connected junction. Give it one
unique net name such as `N1`. Use `GND` or `VDD` when marked, with unique names
for separate rails. Crossings without junctions are separate conductors.
List each connected terminal once using its `component_id` and
`terminal_name`. Leave visibly unconnected terminals out of all nets.
Use an independent second pass to check junctions, crossings, and terminal
assignments. Do not infer connections from a circuit's expected function.

See the [folder layout](annotation-kit/README.md) for the validation and
evaluation commands.
